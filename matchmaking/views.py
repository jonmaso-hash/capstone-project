import math
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import PermissionDenied
from stream_chat import StreamChat

# Consolidated Structural Business Models
from .models import Application, InvestorApplication, Connection, MatchFeedback

# AI Vector Pipeline & Rule-Based Match Core Engine
from matchmaking.services.ai_engine import generate_profile_embedding, calculate_similarity
from .logic import calculate_rule_based_score, get_blended_match

logger = logging.getLogger(__name__)

# ==========================================
# CUSTOM SECURITY DECORATORS
# ==========================================

def founder_required(view_func):
    """
    Decorator for views that checks if the logged-in user contains
    a valid founder badge/profile application record.
    """
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if getattr(request.user, 'is_founder', False) or hasattr(request.user, 'match_founder_profile'):
            return view_func(request, *args, **kwargs)
        
        raise PermissionDenied("Access restricted. Only registered founders can access this matchmaking workspace.")
    return _wrapped_view


# ==========================================
# HELPER DATA GENERATOR
# ==========================================

def _generate_explanatory_insights(ai_score, rule_score, application, investor):
    """
    Helper function to generate a rich structural breakdown payload 
    for the frontend Explanatory AI Insights panel.
    """
    sector_str = getattr(application, 'sector', '') or ''
    focus_str = getattr(investor, 'investment_focus', '') or ''
    stage_str = getattr(application, 'stage', '') or ''
    mandate_stage_str = getattr(investor, 'investment_stage', '') or ''

    sector_match = "Match" if sector_str.lower() in focus_str.lower() else "Neutral"
    stage_match = "Excellent" if stage_str.lower() == mandate_stage_str.lower() else "Partial"
    
    return {
        'match_percentage': int(round(ai_score)),
        'summary': f"Blended alignment index of {round(ai_score)}% via semantic matching vectors and core business constraint validation rules.",
        'pillars': [
            {'title': 'Market Alignment', 'score': sector_match, 'desc': f"Evaluated startup vertical '{sector_str}' against targeted investment focus criteria."},
            {'title': 'Funding Stage', 'score': stage_match, 'desc': f"Startup asset operational tier '{stage_str}' benchmarked to allocator mandate level."},
            {'title': 'Structural Rules', 'score': 'Passed' if rule_score > 60 else 'Review', 'desc': f"Rule compliance engine score marked at a baseline index of {round(rule_score)} points."}
        ]
    }


# ==========================================
# MATCHMAKING CORE VIEWS
# ==========================================

@login_required
def investor_dashboard(request):
    """
    Blended Matchmaking Dashboard: Ranks founders based on AI + Rules.
    Features an advanced keyword-matching fallback system and detailed AI explanations.
    """
    investor_profile = getattr(request.user, 'match_investor_profile', None)
    
    if not investor_profile:
        messages.info(request, "Please complete your investor profile to view matches.")
        return redirect('accounts:investor_form')

    # Lazy-generation framework utilizing the unified vector pipeline
    if not investor_profile.focus_vector and investor_profile.investment_focus:
        try:
            vector_array = generate_profile_embedding(investor_profile.investment_focus)
            if vector_array:
                investor_profile.focus_vector = vector_array
                investor_profile.save()
        except Exception as e:
            logger.error(f"Failed to generate investor focus vector: {str(e)}")
            investor_profile.focus_vector = None

    match_results = []
    requested_ids = Connection.objects.filter(investor=investor_profile).values_list('founder_id', flat=True)

    # Keyword semantic fallback framework if vectors are missing
    if not investor_profile.focus_vector and investor_profile.investment_focus:
        search_terms = [term.strip() for term in investor_profile.investment_focus.replace(',', ' ').split() if len(term.strip()) > 2]
        query = Q()
        for term in search_terms:
            query |= Q(sector__icontains=term) | Q(description__icontains=term) | Q(company_name__icontains=term)
        
        founders = Application.objects.filter(query | Q(stage__icontains=investor_profile.investment_stage)).select_related('user')
    else:
        founders = Application.objects.all().select_related('user')
    
    for founder in founders:
        # Prevent runtime failures from dropping the startup out of the loop completely
        if not founder.description_vector and founder.description:
            try:
                vector_array = generate_profile_embedding(founder.description)
                if vector_array:
                    founder.description_vector = vector_array
                    founder.save()
            except Exception as e:
                logger.warning(f"Failed lazy-generation embedding for founder application {founder.id}: {str(e)}")

        if investor_profile.focus_vector and founder.description_vector:
            try:
                raw_ai_similarity = calculate_similarity(investor_profile.focus_vector, founder.description_vector)
                ai_score = max(0.0, min(100.0, raw_ai_similarity * 100))
            except Exception:
                ai_score = 50.0
        else:
            ai_score = 50.0

        rule_score = calculate_rule_based_score(application=founder, investor=investor_profile)
        final_score = get_blended_match(ai_score, rule_score, application=founder, investor=investor_profile)
        
        if final_score > 10:
            match_results.append({
                'founder': founder,
                'ai_score': round(ai_score, 1),
                'rule_score': round(rule_score, 1),
                'final_score': round(final_score, 1),
                'already_requested': founder.id in requested_ids,
                'ai_insights': _generate_explanatory_insights(ai_score, rule_score, founder, investor_profile)
            })
    
    match_results = sorted(match_results, key=lambda x: x['final_score'], reverse=True)

    return render(request, 'matchmaking/investor_dashboard.html', {
        'matches': match_results,
        'investor': investor_profile,
    })


@login_required
def founder_dashboard(request):
    """
    Founder-facing dashboard: View matching investors ranked by a blended 
    AI + Rule algorithm, and manage incoming handshake requests.
    """
    application = getattr(request.user, 'match_founder_profile', None)
    
    if not application:
        messages.info(request, "Complete your founder profile to see investor matches.")
        return redirect('accounts:seeking_investment')

    # Lazy-generation engine using unified vectorization pipeline
    if not application.description_vector and application.description:
        try:
            vector_array = generate_profile_embedding(application.description)
            if vector_array:
                application.description_vector = vector_array
                application.save()
        except Exception as e:
            logger.warning(f"Failed lazy-generation embedding for founder application {application.id}: {str(e)}")

    # Extract pending inbound handshake records optimized via select_related
    pending_requests = Connection.objects.filter(
        founder=application, 
        status='PENDING'
    ).select_related('investor__user')

    # Query allocators (pulling related user records to eliminate N+1 data hits)
    investors = InvestorApplication.objects.all().select_related('user')
    match_results = []
    
    for investor in investors:
        if application.description_vector and investor.focus_vector:
            try:
                raw_ai_similarity = calculate_similarity(application.description_vector, investor.focus_vector)
                ai_score = max(0.0, min(100.0, raw_ai_similarity * 100))
            except Exception:
                ai_score = 50.0
        else:
            ai_score = 50.0

        rule_score = calculate_rule_based_score(application=application, investor=investor)
        final_score = get_blended_match(ai_score, rule_score, application=application, investor=investor)
        
        if final_score > 15:
            match_results.append({
                'investor': investor,
                'final_score': round(final_score, 1),
                'rule_match': rule_score >= 80,
                'ai_insights': _generate_explanatory_insights(ai_score, rule_score, application, investor)
            })
    
    match_results = sorted(match_results, key=lambda x: x['final_score'], reverse=True)

    return render(request, 'matchmaking/founder_dashboard.html', {
        'matches': match_results,
        'application': application,
        'pending_requests': pending_requests
    })


@login_required
@founder_required
def founder_matchmaker(request):
    """
    Dedicated dashboard for founders to see which specific investors 
    have explicitly 'liked' or upvoted their startup profile card.
    """
    founder_app = get_object_or_404(Application, user=request.user)
    
    likes = MatchFeedback.objects.filter(
        application=founder_app,
        vote=1
    ).select_related('investor__user')
    
    interested_investors = [like.investor for like in likes]
    
    return render(request, 'matchmaking/founder_matchmaker.html', {
        'founder_app': founder_app,
        'interested_investors': interested_investors,
    })


def founder_bulletin_board(request):
    """
    Queries verified startup Application profiles to display on the Interlink Foundry bulletin board.
    Calculates dynamic AI match scores and explicit breakdown data blocks if an authenticated investor is browsing.
    Supports GET request parameters for industry filtering tags.
    """
    pitches_queryset = Application.objects.all().select_related('user')
    
    # Process sector query string parameters safely
    selected_sector = request.GET.get('sector', '').strip()
    if selected_sector:
        pitches_queryset = pitches_queryset.filter(sector__iexact=selected_sector)

    investor_profile = None
    if request.user.is_authenticated:
        investor_profile = getattr(request.user, 'match_investor_profile', None)

    pitches = []
    for pitch in pitches_queryset:
        ai_insights_data = None
        
        if investor_profile and investor_profile.focus_vector and pitch.description_vector:
            try:
                raw_similarity = calculate_similarity(investor_profile.focus_vector, pitch.description_vector)
                ai_score = max(0.0, min(100.0, raw_similarity * 100))
                match_percentage = int(round(ai_score))
                
                # Dynamic validation via rule engine instead of a static score fallback
                rule_score = calculate_rule_based_score(application=pitch, investor=investor_profile)
                ai_insights_data = _generate_explanatory_insights(ai_score, rule_score, pitch, investor_profile)
            except Exception:
                match_percentage = 75
        else:
            match_percentage = 75
            
        pitch.match_percentage = match_percentage
        pitch.ai_insights = ai_insights_data
        pitches.append(pitch)
        
    if investor_profile and investor_profile.focus_vector:
        pitches = sorted(pitches, key=lambda x: x.match_percentage, reverse=True)

    return render(request, 'matchmaking/bulletin_board.html', {
        'pitches': pitches,
        'selected_sector': selected_sector,
    })


# ==========================================
# INTERACTION & TRANSACTION HANDLERS
# ==========================================

@login_required
@require_POST
def request_intro(request, application_id, investor_id):
    """
    The Intro Workflow: Creates a Connection record and dispatches an alert to the broker.
    Ensures safe alignment with requested URL parameter structures.
    """
    founder_app = get_object_or_404(Application, id=application_id)
    investor_profile = getattr(request.user, 'match_investor_profile', None)

    # Secure verification step: validate route scope parameters safely
    if not investor_profile or str(investor_profile.id) != str(investor_id):
        messages.error(request, "Authorization mismatched. Access to introduction workflow denied.")
        return redirect('matchmaking:investor_dashboard')

    connection, created = Connection.objects.get_or_create(
        investor=investor_profile,
        founder=founder_app
    )

    if created:
        subject = f"[Handshake Alert] Intro Request: {investor_profile.company_name or 'Private Investor'} -> {founder_app.company_name}"
        email_body = (
            f"Broker Lead Notification:\n\n"
            f"Investor: {getattr(investor_profile, 'full_name', 'Anonymous Portfolio Manager')} ({investor_profile.company_name or 'Private Partner'})\n"
            f"Founder Startup Target: {founder_app.company_name}\n\n"
            f"Mandate Target Stage: {investor_profile.investment_stage}\n"
            f"Action Required: Navigate to the admin workspace to process and approve this platform handshake."
        )
        
        send_mail(
            subject=subject,
            message=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL)],
            fail_silently=True
        )
        messages.success(request, f"Intro request sent for {founder_app.company_name}! Our team will facilitate the connection.")
    else:
        messages.info(request, "You have already requested an introduction to this founder.")

    return redirect('matchmaking:investor_dashboard')


@login_required
@require_POST
def record_vote(request):
    """
    Captures platform interaction metadata (Thumbs Up / Down) to optimize data value metrics.
    """
    application_id = request.POST.get('application_id')
    vote_value = request.POST.get('vote')
    
    investor_profile = getattr(request.user, 'match_investor_profile', None)
    if not investor_profile or not application_id:
        return redirect('matchmaking:investor_dashboard')
        
    founder_app = get_object_or_404(Application, id=application_id)
    numerical_vote = 1 if vote_value == 'up' else -1

    MatchFeedback.objects.update_or_create(
        user=request.user,
        application=founder_app,
        investor=investor_profile,
        defaults={'vote': numerical_vote}
    )

    messages.success(request, "Feedback recorded. We're tuning your algorithm!")
    return redirect(request.META.get('HTTP_REFERER', 'matchmaking:investor_dashboard'))


@login_required
def initiate_direct_chat(request, target_user_id):
    """
    Instantly opens or creates a direct message thread between two users
    to maximize site interaction, similar to a matchmaking or social platform.
    """
    target_user = get_object_or_404(User, id=target_user_id)
    current_user_id = str(request.user.id)
    target_id_str = str(target_user.id)
    
    # Prevent users from messaging themselves
    if current_user_id == target_id_str:
        return redirect('matchmaking:diligence_chat')

    # Initialize Stream Client
    client = StreamChat(api_key=settings.STREAM_API_KEY, api_secret=settings.STREAM_API_SECRET)
    
    # Ensure both users exist in the chat network database
    client.upsert_users([
        {'id': current_user_id, 'name': request.user.username},
        {'id': target_id_str, 'name': target_user.username}
    ])

    # Generate a unique, deterministic ID for this pair
    sorted_ids = sorted([int(current_user_id), int(target_id_str)])
    channel_id = f"chat_{sorted_ids[0]}_and_{sorted_ids[1]}"

    # Initialize a standard peer-to-peer messaging channel
    channel = client.channel("messaging", channel_id)
    
    # Create the room instantly
    channel.create(
        members=[current_user_id, target_id_str],
        data={
            "name": f"{target_user.username}",
        }
    )

    return redirect('matchmaking:diligence_chat')


@login_required
def deal_room_workspace(request):
    """
    Renders the secure main Deal Room Workspace template.
    The real-time token fetching is handled downstream by accounts:stream_token.
    """
    return render(request, 'matchmaking/chat.html')

def global_search(request):
    # Your search view code here...
    pass