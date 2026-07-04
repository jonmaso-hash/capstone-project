import json
import logging
from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

# Core Matchmaking Engine Models
from matchmaking.services.ai_engine import calculate_zelda_advantage
from matchmaking.utils import clean_financial_input
from matchmaking.models import Application, InvestorApplication, Connection, Follow

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

def signup_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile", username=request.user.username)
        
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, f"Welcome to Interlink Foundry, {user.username}!")
            
            # Route to appropriate onboarding based on selected role
            role = request.POST.get('role', '')
            if role == 'founder':
                return redirect('usersettings:edit_founder_profile')
            elif role == 'investor':
                return redirect('usersettings:edit_investor_profile')
            elif role == 'seller':
                return redirect('usersettings:edit_seller_profile')
            elif role == 'buyer':
                return redirect('usersettings:edit_buyer_profile')
            else:
                return redirect("accounts:profile", username=user.username)
    else:
        form = UserCreationForm()
    return render(request, "accounts/signup.html", {"form": form})


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

    profile_view_count = None
    if application:
        from matchmaking.models import InvestorInterestEvent
        profile_view_count = InvestorInterestEvent.objects.filter(founder=application, event_type='view').count()
    elif seller_application:
        from matchmaking.models import AcquisitionInterestEvent
        profile_view_count = AcquisitionInterestEvent.objects.filter(seller=seller_application, event_type='view').count()

    context = {
        "profile_user": viewed_user,
        "application": application,
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