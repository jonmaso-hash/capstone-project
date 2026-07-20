import json
import logging
from datetime import timedelta
from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.cache import cache
from django.core.mail import send_mail
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

# Core Matchmaking Engine Models
from matchmaking.services.ai_engine import calculate_zelda_advantage
from matchmaking.utils import clean_financial_input
from matchmaking.models import (
    Application, InvestorApplication, SellerApplication, BuyerApplication, Connection, Follow,
    log_page_event, BusinessEmailVerification, company_matches_email_domain, _resolve_company_name,
)

# External/Third-Party Apps
from stream_chat import StreamChat

logger = logging.getLogger(__name__)

# Dynamic lookups prevent NameError failures if optional external apps aren't active
JobListing = None
if apps.is_installed('jobs'):
    try:
        from jobs.models import JobListing
    except ImportError:
        pass

Article = None
if apps.is_installed('blog'):
    try:
        from blog.models import Article
    except ImportError:
        pass


# =====================================================================
# AUTHENTICATION ENGINE VIEWS
# =====================================================================

# Shared by signup_view (password signup) and choose_role (social-login
# completion step) — the one place that maps a role choice to its onboarding URL.
ROLE_PROFILE_URLS = {
    'founder': 'usersettings:edit_founder_profile',
    'investor': 'usersettings:edit_investor_profile',
    'seller': 'usersettings:edit_seller_profile',
    'buyer': 'usersettings:edit_buyer_profile',
}


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile", username=request.user.username)

    # Referral loop (growth app) — a link like /accounts/signup/?ref=CODE
    # stashes the code in session here at GET-time, so it survives through
    # to whichever role-profile form actually creates the new profile
    # (usersettings' edit_*_profile views consume it there).
    ref_code = request.GET.get('ref')
    if ref_code:
        request.session['pending_referral_code'] = ref_code

    if request.method == "POST":
        role = request.POST.get('role', '')
        if role not in ROLE_PROFILE_URLS:
            messages.error(request, "Please pick Founder, Investor, Seller, or Buyer before creating your account.")
            return redirect('accounts:signup')

        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            log_page_event(request, 'signup_completed', role=role, user=user)
            messages.success(request, f"Welcome to Interlink Foundry, {user.username}!")
            return redirect(ROLE_PROFILE_URLS[role])
    else:
        form = UserCreationForm()
        log_page_event(request, 'signup_started')
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def post_login_router(request):
    """
    LOGIN_REDIRECT_URL target for every login — password or social. An
    existing user with a role already picked goes straight to their
    dashboard; a brand-new social-login user (who never went through
    signup_view's role cards) lands on choose_role instead.
    """
    if getattr(request.user, 'match_founder_profile', None):
        return redirect('matchmaking:founder_dashboard')
    if getattr(request.user, 'match_investor_profile', None):
        return redirect('matchmaking:investor_dashboard')
    if getattr(request.user, 'match_seller_profile', None):
        return redirect('matchmaking:seller_dashboard')
    if getattr(request.user, 'match_buyer_profile', None):
        return redirect('matchmaking:buyer_dashboard')
    return redirect('accounts:choose_role')


@login_required
def choose_role(request):
    """
    Role-picker for users who are already authenticated but have no
    Founder/Investor/Seller/Buyer profile yet — the social-login equivalent
    of signup_view's role cards, minus the username/password fields since
    the account already exists.
    """
    if request.method == "POST":
        role = request.POST.get('role', '')
        if role not in ROLE_PROFILE_URLS:
            messages.error(request, "Please pick Founder, Investor, Seller, or Buyer to continue.")
            return redirect('accounts:choose_role')
        return redirect(ROLE_PROFILE_URLS[role])
    return render(request, "accounts/choose_role.html")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile", username=request.user.username)

    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect("accounts:profile", username=request.user.username)
    else:
        form = AuthenticationForm()
    return render(request, "accounts/login.html", {"form": form})


# =====================================================================
# USER PROFILE DISPATCH LAYER
# =====================================================================

@login_required
def profile(request, username=None, pk=None):
    """
    Renders user profile, calculates follow status, and fetches connections.
    """
    User = get_user_model()
    
    # 1. Resolve User
    if pk:
        viewed_user = get_object_or_404(User, pk=pk)
        return redirect("accounts:profile", username=viewed_user.username)
    viewed_user = get_object_or_404(User, username=username)

    # 2. Data Retrieval
    application = getattr(viewed_user, "match_founder_profile", None)
    investor_application = getattr(viewed_user, "match_investor_profile", None)
    seller_application = getattr(viewed_user, "match_seller_profile", None)
    buyer_application = getattr(viewed_user, "match_buyer_profile", None)

    dm_enabled = False
    if application and application.allow_direct_messages:
        dm_enabled = True
    elif investor_application and investor_application.allow_direct_messages:
        dm_enabled = True

    # Fetch optional modules safely
    user_jobs = []
    if JobListing:
        user_jobs = JobListing.objects.filter(poster=viewed_user).order_by('-created_at')

    user_articles = []
    if Article:
        user_articles = Article.objects.filter(author=viewed_user).order_by('-created_on')

    # 3. Follow System
    is_following = False
    mutual_connections = User.objects.none()
    if request.user.is_authenticated:
        is_following = Follow.objects.filter(follower=request.user, following=viewed_user).exists()
        if viewed_user != request.user:
            viewer_following_ids = Follow.objects.filter(follower=request.user).values_list('following_id', flat=True)
            owner_following_ids = Follow.objects.filter(follower=viewed_user).values_list('following_id', flat=True)
            mutual_ids = set(viewer_following_ids) & set(owner_following_ids)
            mutual_connections = User.objects.filter(id__in=mutual_ids)

    following_list = Follow.objects.filter(follower=viewed_user).select_related("following")

    founder_milestones = application.milestones.all()[:10] if application else []

    # 3b. Profile Visibility — owner's own choices on which sections show to others
    show_contact_info = True
    if viewed_user != request.user:
        from usersettings.models import UserSettings
        viewed_user_settings = UserSettings.for_user(viewed_user)
        if not viewed_user_settings.show_job_postings:
            user_jobs = []
        if not viewed_user_settings.show_articles:
            user_articles = []
        if not viewed_user_settings.show_business_connections:
            following_list = Follow.objects.none()
        if not viewed_user_settings.show_milestones:
            founder_milestones = []
        show_contact_info = viewed_user_settings.show_contact_info

    # 4. Privacy Gatekeeper — matchmaking.Application has no allowed_viewers
    # whitelist (that field only exists on the legacy accounts models and is
    # never populated anywhere), so a private profile is owner-only for now.
    # Mirrors the founder-only gate exactly: seller listings get the same
    # owner-only treatment as founder profiles; buyer/investor mandates do
    # not (their privacy only affects matching/discovery, not the page itself).
    if viewed_user != request.user and application and getattr(application, "is_private", False):
        return render(request, "accounts/profile_private.html", {"profile_user": viewed_user})
    if viewed_user != request.user and seller_application and getattr(seller_application, "is_private", False):
        return render(request, "accounts/profile_private.html", {"profile_user": viewed_user})

    # 5. Zelda Advantage Engine
    zelda_score, founder_data_json = None, None
    if application:
        has_advantage_access = (viewed_user == request.user)
        if not has_advantage_access:
            viewer_investor = getattr(request.user, "match_investor_profile", None)
            if viewer_investor and Connection.objects.filter(investor=viewer_investor, founder=application, status="ACCEPTED").exists():
                has_advantage_access = True
        
        if has_advantage_access:
            zelda_score = calculate_zelda_advantage(application)
            founder_data_json = json.dumps({
                "revenue": float(clean_financial_input(application.current_revenue) or 0),
                "ask": float(clean_financial_input(application.raising_amount) or 0),
                "burn": float(clean_financial_input(application.monthly_burn_rate) or 1),
                "team_size": int(clean_financial_input(application.team_size) or 1),
                "years": int(clean_financial_input(application.years_in_business) or 0),
            })
    viewer_is_investor = (
    getattr(request.user, 'accounts_investor_profile', None) is not None or
    getattr(request.user, 'match_investor_profile', None) is not None
    ) if request.user.is_authenticated else False

    viewer_is_buyer = (
        getattr(request.user, 'match_buyer_profile', None) is not None
    ) if request.user.is_authenticated else False

    # Silent outcome tracking — investor viewing a founder's profile
    if viewer_is_investor and application and viewed_user != request.user:
        from matchmaking.models import log_investor_event
        log_investor_event(request.user, application, 'view')

    # Same pattern for the Business Marketplace — a buyer viewing a seller listing
    if viewer_is_buyer and seller_application and viewed_user != request.user:
        from matchmaking.models import log_buyer_event
        log_buyer_event(request.user, seller_application, 'view')

    # Unified view log — founder/seller view counts still come from the event
    # tables above (they predate this model and already have history), but
    # investor/buyer had no view tracking at all until now, and nothing
    # anywhere tracked time-on-page, so ProfileView is logged for every role.
    if request.user.is_authenticated and viewed_user != request.user:
        from matchmaking.models import ProfileView
        if not request.session.session_key:
            request.session.create()
        ProfileView.objects.create(
            viewed_user=viewed_user, viewer=request.user, session_key=request.session.session_key,
        )

    profile_view_count = None
    if application:
        from matchmaking.models import InvestorInterestEvent
        profile_view_count = InvestorInterestEvent.objects.filter(founder=application, event_type='view').count()
    elif seller_application:
        from matchmaking.models import AcquisitionInterestEvent
        profile_view_count = AcquisitionInterestEvent.objects.filter(seller=seller_application, event_type='view').count()
    elif investor_application or buyer_application:
        from matchmaking.models import ProfileView
        profile_view_count = ProfileView.objects.filter(viewed_user=viewed_user).count()

    # Owner always sees their own count; other visitors only see it if the
    # profile owner has left "Show Profile View Count" enabled in Settings.
    if profile_view_count is not None and viewed_user != request.user:
        from usersettings.models import UserSettings
        if not UserSettings.for_user(viewed_user).show_profile_view_count:
            profile_view_count = None

    # IC Memo entry point — founder-only, gated the same way the memo view
    # itself is gated (owner, staff, or an accepted-connection investor).
    ic_memo_document_id = None
    if application:
        from zelda_api.ic_memo import can_view_ic_memo
        if can_view_ic_memo(request.user, application):
            from zelda_api.vector_models import DocumentSource
            pitch_deck_doc = DocumentSource.objects.filter(
                uploaded_by=viewed_user, document_type='pitch_deck', status='analyzed'
            ).order_by('-created_at').first()
            if pitch_deck_doc:
                ic_memo_document_id = pitch_deck_doc.id

    # Privacy-preserving trust badges — thresholded booleans only, never the
    # underlying view/analyze counts. See matchmaking/growth_metrics.py::get_profile_trust_badges.
    from matchmaking.growth_metrics import get_profile_trust_badges
    profile_trust_badges = get_profile_trust_badges(application)

    # Data Room entry point — same gate as the data room page itself
    # (owner, staff, or an accepted-connection investor); titles are visible
    # from there, actual downloads need a separate founder-approved request.
    from matchmaking.models import can_view_data_room
    can_view_founder_data_room = can_view_data_room(request.user, application) if application else False

    # Verification History — the trust trend across every Truth Delta run
    # for this founder/seller's documents over time (e.g. "accurate across
    # three fundraising rounds"), not just the latest single-document
    # score. Same viewer gate as the underlying single-document Truth
    # Delta page itself (any investor/buyer, or the owner) — deliberately
    # NOT connection-gated like IC Memo, since aggregating something
    # already viewable one document at a time isn't a bigger disclosure
    # than an investor just opening each document's page individually.
    verification_history = []
    verification_reports_count = 0
    verification_unlocked = False
    if application or seller_application:
        can_view_verification_history = (
            viewed_user == request.user or viewer_is_investor or viewer_is_buyer or request.user.is_staff
        )
        if can_view_verification_history:
            from zelda_api.truth_delta_models import TruthDeltaReport, diff_verification_reports
            from zelda_api.truth_delta_models import ClaimedDatapoint

            base_reports_qs = TruthDeltaReport.objects.filter(document__uploaded_by=viewed_user)
            verification_reports_count = base_reports_qs.count()
            # Truth Delta content is Premium — same founder/seller-controlled
            # asset model as the IC Memo: gated on the document owner's own
            # Premium, not the viewer's, so it's free for any investor/buyer
            # who can already see this page once the owner unlocks it.
            verification_unlocked = bool(
                request.user.is_staff
                or (application and application.is_premium)
                or (seller_application and seller_application.is_premium)
            )

            if verification_unlocked:
                category_labels = dict(ClaimedDatapoint.CATEGORY_CHOICES)

                def _display_category(code):
                    return category_labels.get(code, code.replace('_', ' ').title())

                verification_history = list(
                    base_reports_qs.select_related('document').order_by('-created_at')[:20]
                )
                # Attach non-persisted .trend/.stats to each report — in-memory
                # only, computed fresh from `details` every request rather than
                # stored, so there's no risk of it drifting stale. Category
                # codes are mapped to their display labels here (view/template
                # concern) — diff_verification_reports itself stays in terms
                # of raw category codes, which is what its own tests assert on.
                for i, report in enumerate(verification_history):
                    report.stats = report.verifiability_stats()
                    trend = (
                        diff_verification_reports(report, verification_history[i + 1])
                        if i + 1 < len(verification_history) else None
                    )
                    report.trend = trend and {
                        'newly_verified': [_display_category(c) for c in trend['newly_verified']],
                        'lost_verification': [_display_category(c) for c in trend['lost_verification']],
                    }

    context = {
        "profile_user": viewed_user,
        "application": application,
        "ic_memo_document_id": ic_memo_document_id,
        "profile_trust_badges": profile_trust_badges,
        "can_view_founder_data_room": can_view_founder_data_room,
        "verification_history": verification_history,
        "verification_reports_count": verification_reports_count,
        "verification_unlocked": verification_unlocked,
        "investor_application": investor_application,
        "seller_application": seller_application,
        "buyer_application": buyer_application,
        "zelda_score": zelda_score,
        "founder_data_json": founder_data_json,
        "is_following": is_following,
        "following_list": following_list,
        "user_articles": user_articles,
        "user_jobs": user_jobs,
        "dm_enabled": dm_enabled,
        "viewer_is_investor": viewer_is_investor,
        "viewer_is_buyer": viewer_is_buyer,
        "profile_view_count": profile_view_count,
        "show_contact_info": show_contact_info,
        "mutual_connections": mutual_connections,
        "founder_milestones": founder_milestones,

    }

    return render(request, "accounts/profile.html", context)

@login_required
def redirect_to_own_profile(request):
    return redirect("accounts:profile", username=request.user.username)


def _build_insights_engine_context(events, role, role_profile):
    """
    Assembles every Premium-gated matchmaking.insights_engine computation
    for the profile_analysis view — kept out of the view body so the free
    branch never pays for these extra queries. `role` picks the
    founder/seller-specific breakdown (get_investor_focus_breakdown vs.
    get_buyer_deal_structure_breakdown); everything else is symmetric
    between the two interest-event models.
    """
    from matchmaking.insights_engine import (
        get_funnel_stats, get_conversion_rates, get_trending_stats, get_multi_metric_trends,
        get_engagement_score, get_strengths_and_improvements, get_interest_timeline,
        get_ai_insights, get_opportunity_alerts, get_recommendations,
        get_investor_focus_breakdown, get_buyer_deal_structure_breakdown,
    )

    funnel_stats = get_funnel_stats(events)
    trending_stats = get_trending_stats(events)
    engagement_score = get_engagement_score(funnel_stats, role_profile)
    context = {
        'funnel_stats': funnel_stats,
        'conversion_rates': get_conversion_rates(funnel_stats),
        'trending_stats': trending_stats,
        'multi_metric_trends': get_multi_metric_trends(events),
        'engagement_score': engagement_score,
        'strengths_and_improvements': get_strengths_and_improvements(engagement_score, role_profile),
        'interest_timeline': get_interest_timeline(events),
        'ai_insights': get_ai_insights(funnel_stats, trending_stats),
        'opportunity_alerts': get_opportunity_alerts(funnel_stats, trending_stats, events, role_profile),
        'recommendations': get_recommendations(funnel_stats, role_profile),
    }
    if role == 'founder':
        context['focus_breakdown'] = get_investor_focus_breakdown(events)
    elif role == 'seller':
        context['focus_breakdown'] = get_buyer_deal_structure_breakdown(events)
    return context


@login_required
def profile_analysis(request, username):
    """
    The private analytics home for all four account types — merges what
    used to be founder-only "Deck Analytics" with profile-view tracking,
    pitch video retention, blog/job/messaging metrics, and role-specific
    deal outcomes. Strictly owner-only, unlike the old deck_analytics view
    which also let staff peek.
    """
    viewed_user = get_object_or_404(get_user_model(), username=username)
    if request.user != viewed_user:
        messages.error(request, "You can only view your own Profile Analysis.")
        return redirect('accounts:profile', username=viewed_user.username)

    application = getattr(viewed_user, "match_founder_profile", None)
    investor_application = getattr(viewed_user, "match_investor_profile", None)
    seller_application = getattr(viewed_user, "match_seller_profile", None)
    buyer_application = getattr(viewed_user, "match_buyer_profile", None)

    from matchmaking.models import (
        ProfileView, PitchVideoView,
        InvestorInterestEvent, AcquisitionInterestEvent, MessageThread,
        Connection, AcquisitionConnection,
    )

    now = timezone.now()
    time_buckets_def = [
        ('last_hour', now - timedelta(hours=1)),
        ('last_day', now - timedelta(days=1)),
        ('last_month', now - timedelta(days=30)),
        ('last_year', now - timedelta(days=365)),
    ]

    # --- Profile Views: founder/seller keep their existing, longer-lived
    # event tables; investor/buyer only ever had ProfileView to draw from. ---
    if application:
        view_qs = InvestorInterestEvent.objects.filter(founder=application, event_type='view')
    elif seller_application:
        view_qs = AcquisitionInterestEvent.objects.filter(seller=seller_application, event_type='view')
    else:
        view_qs = ProfileView.objects.filter(viewed_user=viewed_user)

    total_views = view_qs.count()
    view_buckets = {label: view_qs.filter(created_at__gte=cutoff).count() for label, cutoff in time_buckets_def}
    view_buckets['all_time'] = total_views

    avg_duration_seconds = ProfileView.objects.filter(
        viewed_user=viewed_user, duration_seconds__isnull=False
    ).aggregate(avg=Avg('duration_seconds'))['avg']

    # --- Pitch Deck Analytics (founder, has deck) — shared with the IC memo
    # generator via matchmaking.growth_metrics.get_deck_engagement_stats so
    # the two surfaces can never disagree on the numbers. ---
    from matchmaking.growth_metrics import get_deck_engagement_stats
    deck_stats = get_deck_engagement_stats(application)

    # --- Pitch Video Analytics (founder, has video) ---
    video_stats = None
    if application and application.pitch_video:
        video_sessions = PitchVideoView.objects.filter(founder=application)
        video_total_sessions = video_sessions.count()
        retention_pct = None
        if video_total_sessions:
            ratios = [
                row.max_watched_seconds / row.video_duration_seconds
                for row in video_sessions if row.video_duration_seconds > 0
            ]
            if ratios:
                retention_pct = round(100 * sum(ratios) / len(ratios), 1)
        video_stats = {'total_sessions': video_total_sessions, 'retention_pct': retention_pct}

    # --- Video -> Profile Conversion Funnel (Pitch Videos section) ---
    pitch_video_funnel = None
    from matchmaking.growth_metrics import get_pitch_video_funnel
    if application and application.pitch_video:
        pitch_video_funnel = get_pitch_video_funnel(application, 'founder')
    elif seller_application and seller_application.pitch_video:
        pitch_video_funnel = get_pitch_video_funnel(seller_application, 'seller')

    # --- Blog Performance ---
    blog_stats = None
    if Article:
        from blog.models import Comment
        user_articles_qs = Article.objects.filter(author=viewed_user)
        if user_articles_qs.exists():
            top_comment = (
                Comment.objects.filter(article__author=viewed_user)
                .annotate(like_count=Count('likes'))
                .order_by('-like_count', '-created_on')
                .first()
            )
            blog_stats = {
                'total_likes': sum(a.total_likes() for a in user_articles_qs),
                'total_article_views': sum(a.views for a in user_articles_qs),
                'top_article': user_articles_qs.order_by('-views').first(),
                'top_comment': top_comment if top_comment and top_comment.like_count > 0 else None,
            }

    # --- Job Postings ---
    job_stats = None
    if JobListing:
        user_jobs_qs = JobListing.objects.filter(poster=viewed_user)
        if user_jobs_qs.exists():
            job_stats = {
                'listings': user_jobs_qs.order_by('-click_count'),
                'total_clicks': sum(j.click_count for j in user_jobs_qs),
            }

    # --- Messaging ---
    messaged_count = MessageThread.objects.filter(Q(user_a=viewed_user) | Q(user_b=viewed_user)).count()

    # --- Deal Outcomes ---
    founders_funded = Connection.objects.filter(investor=investor_application, status='FUNDED').count() if investor_application else None
    deals_closed = AcquisitionConnection.objects.filter(buyer=buyer_application, status='CLOSED').count() if buyer_application else None

    # --- Engagement Summary — already-logged event types nobody surfaces
    # today. Founder/seller see engagement targeting them; investor/buyer
    # see their own outbound activity (they're the actor, not the target). ---
    engagement = None
    is_premium_insights = False
    insights_engine_context = {}
    free_intro_requests = None
    free_thumbs_up = None
    if application:
        events = InvestorInterestEvent.objects.filter(founder=application)
        engagement = {
            'Intro Requests Received': events.filter(event_type='intro_request').count(),
            'Thumbs Up Received': events.filter(event_type='thumbs_up').count(),
            'Memo Views': events.filter(event_type='memo_view').count(),
            'Truth Delta Views': events.filter(event_type='truth_delta_view').count(),
            'Times Analyzed': events.filter(event_type='analyze').count(),
        }
        is_premium_insights = application.is_premium
        free_intro_requests = engagement['Intro Requests Received']
        free_thumbs_up = engagement['Thumbs Up Received']
        if is_premium_insights:
            insights_engine_context = _build_insights_engine_context(events, role='founder', role_profile=application)
    elif seller_application:
        events = AcquisitionInterestEvent.objects.filter(seller=seller_application)
        engagement = {
            'Intro Requests Received': events.filter(event_type='intro_request').count(),
            'Thumbs Up Received': events.filter(event_type='thumbs_up').count(),
            'Memo Views': events.filter(event_type='memo_view').count(),
            'Truth Delta Views': events.filter(event_type='truth_delta_view').count(),
            'Times Analyzed': events.filter(event_type='analyze').count(),
        }
        is_premium_insights = seller_application.is_premium
        free_intro_requests = engagement['Intro Requests Received']
        free_thumbs_up = engagement['Thumbs Up Received']
        if is_premium_insights:
            insights_engine_context = _build_insights_engine_context(events, role='seller', role_profile=seller_application)
    elif investor_application:
        events = InvestorInterestEvent.objects.filter(investor=viewed_user)
        engagement = {
            'Intro Requests Sent': events.filter(event_type='intro_request').count(),
            'Thumbs Up Given': events.filter(event_type='thumbs_up').count(),
            'Analyses Run': events.filter(event_type='analyze').count(),
        }
    elif buyer_application:
        events = AcquisitionInterestEvent.objects.filter(buyer=viewed_user)
        engagement = {
            'Intro Requests Sent': events.filter(event_type='intro_request').count(),
            'Thumbs Up Given': events.filter(event_type='thumbs_up').count(),
            'Analyses Run': events.filter(event_type='analyze').count(),
        }

    context = {
        'profile_user': viewed_user,
        'application': application,
        'investor_application': investor_application,
        'seller_application': seller_application,
        'buyer_application': buyer_application,
        'has_analytics_paywall': bool(application or seller_application),
        'is_premium_insights': is_premium_insights,
        'show_full_engagement_summary': is_premium_insights or not (application or seller_application),
        'free_intro_requests': free_intro_requests,
        'free_thumbs_up': free_thumbs_up,
        **insights_engine_context,
        'total_views': total_views,
        'view_buckets': view_buckets,
        'avg_duration_seconds': round(avg_duration_seconds, 1) if avg_duration_seconds else None,
        'deck_stats': deck_stats,
        'video_stats': video_stats,
        'pitch_video_funnel': pitch_video_funnel,
        'blog_stats': blog_stats,
        'job_stats': job_stats,
        'messaged_count': messaged_count,
        'founders_funded': founders_funded,
        'deals_closed': deals_closed,
        'engagement': engagement,
    }
    return render(request, 'accounts/profile_analysis.html', context)


# =====================================================================
# EXTERNAL INTEGRATIONS & REALTIME CHAT COMMUNICATIONS (APIs)
# =====================================================================

@login_required
def get_stream_token(request):
    try:
        api_key = getattr(settings, 'STREAM_API_KEY', None)
        api_secret = getattr(settings, 'STREAM_API_SECRET', None)
        
        if not api_key or not api_secret:
            return JsonResponse({
                'error': 'Configuration Error',
                'details': 'STREAM_API_KEY or STREAM_API_SECRET missing from settings.py or environment configuration.'
            }, status=500)
            
        client = StreamChat(api_key=api_key, api_secret=api_secret)
        
        # IMPORTANT: Use the user's integer ID as a string, because JS passes integer targetIDs
        user_id = str(request.user.id)
        username = request.user.username
        
        # 1. Create the token
        token = client.create_token(user_id)
        
        # 2. CRITICAL FIX: Upsert the user into Stream's database immediately
        client.upsert_user({"id": user_id, "name": username})
        
        return JsonResponse({
            'api_key': api_key,
            'token': token,
            'user_id': user_id,
            'username': username
        })
        
    except Exception as e:
        logger.exception("Stream Token Generation & Upsert Failed")
        return JsonResponse({'error': 'Internal Server Error', 'details': str(e)}, status=500)


# =====================================================================
# AI ASSISTANCE CANVAS VIEW
# =====================================================================

@login_required
def ai_search_page(request):
    return render(request, "accounts/ai_search.html")


@require_POST
@login_required
def account_search_api(request):
    try:
        data = json.loads(request.body)
        query_param = data.get('q', '').strip()
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not query_param:
        return JsonResponse({"results": []})

    search_query = (
        Q(company_name__icontains=query_param) | 
        Q(sector__icontains=query_param) |
        Q(description__icontains=query_param)
    )

    # 🔒 FILTER BOUNDARIES: Enforces public alignment unless the request belongs to the owner
    results_queryset = Application.objects.filter(search_query).filter(
        Q(is_private=False) | Q(user=request.user)
    )[:10]

    serialized_results = [
        {
            "title": app.company_name or "Untitled Application",
            "snippet": f"Sector: {app.sector} | Stage: {getattr(app, 'stage', '')}",
            "url": reverse("accounts:profile", kwargs={"username": app.user.username})
        }
        for app in results_queryset
    ]

    return JsonResponse({"status": "success", "results": serialized_results})


# =====================================================================
# PRIVACY MANAGEMENT LAYER (AJAX ENDPOINT)
# =====================================================================

@login_required
@require_POST
def toggle_privacy_view(request):
    try:
        data = json.loads(request.body)
        is_private_state = bool(data.get('is_private', False))
        
        founder_profile = Application.objects.filter(user=request.user).first()
        if founder_profile:
            founder_profile.is_private = is_private_state
            founder_profile.save(update_fields=['is_private'])

        investor_profile = InvestorApplication.objects.filter(user=request.user).first()
        if investor_profile:
            investor_profile.is_private = is_private_state
            investor_profile.save(update_fields=['is_private'])

        return JsonResponse({"status": "success", "is_private": is_private_state})
    except Exception as e:
        logger.exception("AJAX privacy toggle update failed.")
        return JsonResponse({"status": "error", "message": str(e)}, status=400)
    
@login_required
def zelda_dashboard_view(request):
    # 1. Use the exact same lookup method as your profile view
    application = getattr(request.user, "match_founder_profile", None)
    
    # 2. If it is STILL None, the database record genuinely doesn't exist for this user.
    if not application:
        messages.warning(request, "Please initialize your founder profile to access the Zelda Dashboard.")
        return redirect('usersettings:edit_founder_profile')
    
    # 3. Safely pass the data to the template
    context = {
        'application': application,
        'founder_data_json': json.dumps({
            'revenue': float(application.current_revenue or 0),
            'ask': float(application.raising_amount or 0),
            'burn': float(application.monthly_burn_rate or 1),
            'team': int(application.team_size or 1)
        })
    }
    return render(request, "accounts/zelda_dashboard.html", context)

@login_required
def update_criteria(request):
    if request.method == "POST":
        app = Application.objects.get(user=request.user)
        
        # Update inputs
        app.current_revenue = request.POST.get('revenue')
        app.monthly_burn_rate = request.POST.get('burn')
        app.team_size = request.POST.get('team')
        app.save()
        
        # Run the engine
        calculate_zelda_advantage(app)
        
        # Return JSON instead of redirecting
        return JsonResponse({
            'status': 'success',
            'zelda_score': app.zelda_score,
            'runway_months': float(app.runway_months)
        })
        
@login_required
@require_POST
def toggle_dm_view(request):
    try:
        data = json.loads(request.body)
        is_enabled = bool(data.get('dm_enabled', False))
        
        founder_profile = Application.objects.filter(user=request.user).first()
        if founder_profile:
            founder_profile.allow_direct_messages = is_enabled
            founder_profile.save(update_fields=['allow_direct_messages'])

        investor_profile = InvestorApplication.objects.filter(user=request.user).first()
        if investor_profile:
            investor_profile.allow_direct_messages = is_enabled
            investor_profile.save(update_fields=['allow_direct_messages'])

        return JsonResponse({"status": "success", "dm_enabled": is_enabled})
    except Exception as e:
        logger.exception("AJAX DM toggle update failed.")
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


ROLE_PROFILE_ATTRS = (
    ('match_founder_profile', 'Founder'),
    ('match_investor_profile', 'Investor'),
    ('match_seller_profile', 'Seller'),
    ('match_buyer_profile', 'Buyer'),
)

BUSINESS_VERIFICATION_RESEND_COOLDOWN = 60  # seconds


@login_required
def business_verification(request):
    """
    Self-serve business-email verification for the existing per-role
    'Verified' badge. Renders current status: already verified, a pending
    code awaiting entry, locked out (too many wrong attempts), or the
    initial request-email form.
    """
    already_verified = any(
        getattr(request.user, attr, None) and getattr(request.user, attr).is_verified
        for attr, _ in ROLE_PROFILE_ATTRS
    )
    resolved_company_name = _resolve_company_name(request.user)
    current_verification = BusinessEmailVerification.objects.filter(user=request.user).first()

    return render(request, "accounts/business_verification.html", {
        "already_verified": already_verified,
        "resolved_company_name": resolved_company_name,
        "current_verification": current_verification,
    })


@login_required
@require_POST
def business_verification_request(request):
    business_email = (request.POST.get("business_email") or "").strip()

    if not business_email or "@" not in business_email:
        messages.error(request, "Enter a valid business email address.")
        return redirect("accounts:business_verification")

    resolved_company_name = _resolve_company_name(request.user)
    if not resolved_company_name:
        messages.error(request, "We couldn't find a company name on your account to verify against.")
        return redirect("accounts:business_verification")

    if not company_matches_email_domain(resolved_company_name, business_email):
        messages.error(request, "That email domain doesn't match your company name.")
        return redirect("accounts:business_verification")

    cooldown_key = f"business_verify_cooldown:{request.user.id}"
    if cache.get(cooldown_key):
        messages.error(request, "Please wait a bit before requesting another code.")
        return redirect("accounts:business_verification")

    verification = BusinessEmailVerification.objects.create(
        user=request.user, business_email=business_email,
    )
    cache.set(cooldown_key, True, timeout=BUSINESS_VERIFICATION_RESEND_COOLDOWN)

    try:
        send_mail(
            subject="Your Interlink Foundry verification code",
            message=(
                f"Your Interlink Foundry business verification code is: {verification.code}\n\n"
                f"This code expires in 30 minutes. If you didn't request this, you can safely ignore this email."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[business_email],
            fail_silently=True,
        )
        messages.success(request, f"A verification code was sent to {business_email}.")
    except Exception:
        messages.warning(request, "Code created, but the email failed to send.")

    return redirect("accounts:business_verification")


@login_required
@require_POST
def business_verification_confirm(request):
    submitted_code = (request.POST.get("code") or "").strip()
    verification = BusinessEmailVerification.objects.filter(user=request.user, status="PENDING").first()

    if not verification:
        messages.error(request, "Request a verification code first.")
        return redirect("accounts:business_verification")

    if timezone.now() > verification.expires_at:
        verification.status = "EXPIRED"
        verification.save(update_fields=["status"])
        messages.error(request, "That code has expired. Request a new one.")
        return redirect("accounts:business_verification")

    if submitted_code != verification.code:
        verification.attempts += 1
        if verification.attempts >= BusinessEmailVerification.MAX_ATTEMPTS:
            verification.status = "LOCKED"
            verification.save(update_fields=["attempts", "status"])
            messages.error(request, "Too many incorrect attempts. Request a new code.")
        else:
            verification.save(update_fields=["attempts"])
            messages.error(request, "That code is incorrect.")
        return redirect("accounts:business_verification")

    verification.status = "VERIFIED"
    verification.verified_at = timezone.now()
    verification.save(update_fields=["status", "verified_at"])

    verified_roles = []
    for attr, label in ROLE_PROFILE_ATTRS:
        profile = getattr(request.user, attr, None)
        if profile:
            profile.is_verified = True
            profile.save(update_fields=["is_verified"])
            verified_roles.append(label)

    if verified_roles:
        messages.success(request, f"You're now a verified {'/'.join(verified_roles)}!")
    else:
        messages.success(request, "Your business email is verified.")

    return redirect("accounts:business_verification")