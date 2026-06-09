import json
import logging
import jwt

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from rest_framework.response import Response
from rest_framework.views import APIView
from stream_chat import StreamChat
from .utils import clean_financial_input
from .models import Application
from django.http import FileResponse, Http404

# Internal Services & Models
from matchmaking.models import Application, Connection, InvestorApplication, MatchFeedback, ConnectionRequest
from matchmaking.services.ai_engine import calculate_similarity, generate_profile_embedding
from matchmaking.utils import calculate_rule_based_score, get_blended_match, clean_financial_input
from .tasks import crawl_startup_data_task

logger = logging.getLogger(__name__)

def connection_action_view(request):
    """
    Handles PENDING -> ACCEPTED/DECLINED transitions for connection requests.
    Supports asynchronous frontend triggers.
    """
    try:
        data = json.loads(request.body)
        request_id = data.get('id')
        action = data.get('action') # Expected: 'ACCEPTED' or 'DECLINED'

        if action not in ['ACCEPTED', 'DECLINED']:
            return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)

        conn_req = get_object_or_404(Connection, id=request_id)        
        # Ensure user has permission to act on this request
        if conn_req.founder.user != request.user and conn_req.investor.user != request.user:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

        conn_req.status = action
        conn_req.save(update_fields=['status'])
        
        return JsonResponse({'status': 'success', 'new_status': action})
    except Exception as e:
        logger.error(f"Connection action error: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


# ==========================================
# CUSTOM SECURITY DECORATORS
# ==========================================

def founder_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if getattr(request.user, 'is_founder', False) or hasattr(request.user, 'match_founder_profile'):
            return view_func(request, *args, **kwargs)
        raise PermissionDenied("Access restricted.")
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
    Filters out private founder profiles explicitly by default.
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

    # Privacy Gatekeeper: Only select records where is_private=False
    if not investor_profile.focus_vector and investor_profile.investment_focus:
        search_terms = [term.strip() for term in investor_profile.investment_focus.replace(',', ' ').split() if len(term.strip()) > 2]
        query = Q()
        for term in search_terms:
            query |= Q(sector__icontains=term) | Q(description__icontains=term) | Q(company_name__icontains=term)
        
        founders = Application.objects.filter(is_private=False).filter(
            query | Q(stage__icontains=investor_profile.investment_stage)
        ).select_related('user')
    else:
        founders = Application.objects.filter(is_private=False).select_related('user')
    
    for founder in founders:
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
@founder_required
def founder_dashboard(request):
    """
    Founder-facing dashboard: View matching investors ranked by a blended 
    AI + Rule algorithm. Filters out private investor mandates explicitly by default.
    """
    application = getattr(request.user, 'match_founder_profile', None) or Application.objects.filter(user=request.user).first()
    
    if not application:
        messages.info(request, "Complete your founder profile to see investor matches.")
        return redirect('accounts:seeking_investment')

    if not application.description_vector and application.description:
        try:
            vector_array = generate_profile_embedding(application.description)
            if vector_array:
                application.description_vector = vector_array
                application.save()
        except Exception as e:
            logger.warning(f"Failed lazy-generation embedding for founder application {application.id}: {str(e)}")

    pending_requests = Connection.objects.filter(
        founder=application, 
        status__iexact='pending'
    ).select_related('investor__user')

    # Privacy Gatekeeper: Only fetch allocators where is_private=False
    investors = InvestorApplication.objects.filter(is_private=False).select_related('user')
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
    Queries verified public startup Application profiles to display on the Interlink Foundry bulletin board.
    """
    # Privacy Gatekeeper: Only pull applications where is_private is explicitly False
    pitches_queryset = Application.objects.filter(is_private=False).select_related('user')
    
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
def submit_founder_application(request):
    """
    Handles the submission of the founder profile form and sanitizes financial inputs
    before hitting the database and vector generation.
    """
    # 1. Get the raw string from the frontend form
    raw_amount = request.POST.get('raising_amount')
    
    # 2. Clean it using your utility function
    clean_amount = clean_financial_input(raw_amount)
    
    # 3. Create or update the application with the safe integer
    application, created = Application.objects.get_or_create(user=request.user)
    application.raising_amount = clean_amount
    
    # NOTE: Add any other fields you are saving from the POST request here 
    # (e.g., application.description = request.POST.get('description'))
    
    application.save()
    
    messages.success(request, "Founder profile successfully updated and indexed.")
    return redirect('matchmaking:founder_dashboard')


@login_required
@require_POST
def request_intro(request, application_id, investor_id):
    """
    The Intro Workflow: Creates a Connection record and dispatches an alert to the broker.
    """
    founder_app = get_object_or_404(Application, id=application_id)
    investor_profile = getattr(request.user, 'match_investor_profile', None)

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
    Instantly opens or creates a direct message thread between two users via Stream Chat.
    """
    target_user = get_object_or_404(User, id=target_user_id)
    current_user_id = str(request.user.id)
    target_id_str = str(target_user.id)
    
    if current_user_id == target_id_str:
        return redirect('matchmaking:diligence_chat')

    client = StreamChat(api_key=settings.STREAM_API_KEY, api_secret=settings.STREAM_API_SECRET)
    
    client.upsert_users([
        {'id': current_user_id, 'name': request.user.username},
        {'id': target_id_str, 'name': target_user.username}
    ])

    sorted_ids = sorted([int(current_user_id), int(target_id_str)])
    channel_id = f"chat_{sorted_ids[0]}_and_{sorted_ids[1]}"

    channel = client.channel("messaging", channel_id)
    channel.create(
        members=[current_user_id, target_id_str],
        data={
            "name": f"{target_user.username}",
        }
    )

    return redirect('matchmaking:diligence_chat')


@login_required
def deal_room_view(request):
    """
    Renders the empty chat shell. The frontend StreamChatController 
    handles all data fetching, authentication, and UI population.
    """
    return render(request, 'matchmaking/chat.html')

def global_search(request):
    """
    Advanced Search & Smart Filtering Engine.
    Excludes private applications strictly down the filtering stream.
    """
    state = request.GET.get('state', '').strip()
    stage = request.GET.get('stage', '').strip()
    max_capital = request.GET.get('capital', '').strip()
    min_revenue = request.GET.get('revenue', '').strip()

    # Privacy Gatekeeper: Public matching index only
    queryset = Application.objects.select_related('user').filter(is_private=False)
    
    if state:
        queryset = queryset.filter(
            Q(description__icontains=state) | Q(extra_info__icontains=state)
        )
    
    if stage:
        queryset = queryset.filter(stage__iexact=stage)
        
    if max_capital and max_capital.isdigit():
        queryset = queryset.filter(raising_amount__lte=int(max_capital))
        
    if min_revenue and min_revenue.isdigit():
        queryset = queryset.filter(current_revenue__gte=int(min_revenue))
        
    return render(request, 'matchmaking/search_results.html', {
        'results': queryset,
        'filters': {
            'state': state,
            'stage': stage,
            'capital': max_capital,
            'revenue': min_revenue
        }
    })


class MemoIntelligenceView(APIView):
    def get(self, request, startup_name):
        founder_app = get_object_or_404(Application, company_name__iexact=startup_name)
        cache_key = f"startup_data_{founder_app.id}"
        
        external_data = cache.get(cache_key)
        
        if external_data is None:
            crawl_startup_data_task.delay(founder_app.id)
            
            return Response({
                "status": "processing",
                "message": "Data is being fetched in the background. Please refresh in a moment."
            })
        
        return Response({
            "startup": founder_app.company_name,
            "data": external_data,
            "cached": True
        })


@login_required
@require_POST
def toggle_privacy_view(request):
    try:
        payload = json.loads(request.body)
        is_private_state = bool(payload.get('is_private', False))
        
        # 1. Update Founder Pitch Application if it exists
        founder_profile = Application.objects.filter(user=request.user).first()
        if founder_profile:
            founder_profile.is_private = is_private_state
            founder_profile.save(update_fields=['is_private'])

        # 2. Update Investor Mandate Profile if it exists
        investor_profile = InvestorApplication.objects.filter(user=request.user).first()
        if investor_profile:
            investor_profile.is_private = is_private_state
            investor_profile.save(update_fields=['is_private'])

        return JsonResponse({"status": "success", "is_private": is_private_state})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)
    
@login_required
def get_stream_token(request):
    """
    Generates a secure token using the official Stream SDK.
    Provides all necessary data for StreamChatController.connect()
    """
    try:
        client = StreamChat(api_key=settings.STREAM_API_KEY, api_secret=settings.STREAM_API_SECRET)
        user_id = str(request.user.id)
        
        # Use Stream's native token generator, not custom JWT
        token = client.create_token(user_id)
        
        return JsonResponse({
            'api_key': settings.STREAM_API_KEY,
            'token': token,
            'user_id': user_id,
            'username': request.user.username
        })
    except Exception as e:
        logger.error(f"Failed to generate Stream Token: {str(e)}")
        return JsonResponse({'error': 'Authentication server error'}, status=500)
    
@login_required
def standalone_memo_view(request, company_slug):
    """
    Renders a secure, institutional-grade evaluation brief for an asset profile.
    Synchronizes with background scrapers if cache records are missing.
    """
    # 1. Reverse the URL slug format back to a standard string lookup
    formatted_name = company_slug.replace('-', ' ')
    founder_app = get_object_or_404(Application, company_name__iexact=formatted_name)
    
    # 2. Security Check: Restrict access to valid investor profiles
    investor_profile = getattr(request.user, 'match_investor_profile', None)
    if not investor_profile and not request.user.is_staff:
        raise PermissionDenied("Access to proprietary asset intelligence reports is restricted.")

    # 3. Synchronize with the Asynchronous Cache/Task Engine
    cache_key = f"startup_data_{founder_app.id}"
    external_data = cache.get(cache_key)
    is_processing = False
    
    if external_data is None:
        # Trigger your background crawler task if cache is cold
        crawl_startup_data_task.delay(founder_app.id)
        is_processing = True

    # 4. Generate alignment calculations if profile metrics are present
    match_percentage = 75
    ai_insights_data = None
    if investor_profile and investor_profile.focus_vector and founder_app.description_vector:
        try:
            raw_similarity = calculate_similarity(investor_profile.focus_vector, founder_app.description_vector)
            ai_score = max(0.0, min(100.0, raw_similarity * 100))
            match_percentage = int(round(ai_score))
            
            rule_score = calculate_rule_based_score(application=founder_app, investor=investor_profile)
            ai_insights_data = _generate_explanatory_insights(ai_score, rule_score, founder_app, investor_profile)
        except Exception:
            pass

    context = {
        'founder_app': founder_app,
        'external_data': external_data,
        'is_processing': is_processing,
        'match_percentage': match_percentage,
        'ai_insights': ai_insights_data,
        'investor': investor_profile
    }
    
    founder_app = get_object_or_404(Application, company_name__iexact=formatted_name)
    investor_profile = getattr(request.user, 'match_investor_profile', None)
    
    # --- PRIVACY GATEKEEPER ---
    zelda_score = None
    has_advantage_access = False

    # Condition 1: The user looking is the Founder who owns the profile
    if request.user == founder_app.user:
        has_advantage_access = True
        
    # Condition 2: The user is an Investor with an ACCEPTED connection
    elif investor_profile:
        has_access = Connection.objects.filter(
            investor=investor_profile,
            founder=founder_app,
            status='ACCEPTED' # Must match exactly how you save it in connection_action_view
        ).exists()
        
        if has_access:
            has_advantage_access = True

    # Only calculate if authorized to save server resources
    if has_advantage_access:
        zelda_score = calculate_zelda_advantage(founder_app)

    context = {
        'founder_app': founder_app,
        'investor': investor_profile,
        'zelda_score': zelda_score, # Passes None if unauthorized
        # ... your other context variables ...
    }
    
    return render(request, 'matchmaking/memo_detail.html', context)

@login_required
@require_POST
def submit_founder_application(request):
    raw_amount = request.POST.get('raising_amount')
    clean_amount = clean_financial_input(raw_amount)
    
    # CORRECT: Use 'Application', not 'FounderApplication'
    application, created = Application.objects.get_or_create(user=request.user)
    application.raising_amount = clean_amount
    
    application.save()
    
    messages.success(request, "Founder profile successfully updated and indexed.")
    return redirect('matchmaking:founder_dashboard')

@login_required
def download_document(request, doc_id):
    doc = get_object_or_404(Document, id=doc_id)
    room = doc.deal_room
    
    # Security Check: Is the user the investor in this connection?
    if request.user == room.connection.investor.user and room.is_active:
        return FileResponse(doc.file.open('rb'), as_attachment=True)
    
    raise Http404("Access Denied")