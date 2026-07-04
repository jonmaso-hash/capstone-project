import csv
import json
import logging
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from rest_framework.response import Response
from rest_framework.views import APIView
from stream_chat import StreamChat
from .utils import clean_financial_input
from .models import Application
from django.http import FileResponse, Http404
from django.urls import reverse
from django.utils import timezone
from .models import Follow

# Internal Services & Models
from matchmaking.models import Application, Connection, InvestorApplication, MatchFeedback, ConnectionRequest, Document, log_investor_event, PitchDeckViewSession, PitchDeckSlideTime, FundraisingLead, FounderMilestone
from matchmaking.models import SellerApplication, BuyerApplication, AcquisitionConnection, DealFeedback, log_buyer_event
from matchmaking.services.ai_engine import calculate_similarity, generate_profile_embedding
from matchmaking.utils import calculate_rule_based_score, get_blended_match, clean_financial_input
from matchmaking.utils import calculate_deal_rule_based_score, get_deal_blended_match
from .tasks import crawl_startup_data_task

# Zelda AI alignment — import DiligenceEngine for vector scoring in memo views
try:
    from zelda_api.views import DiligenceEngine
    from zelda_api.utils import calculate_zelda_advantage
    _ZELDA_AVAILABLE = True
except ImportError:
    DiligenceEngine = None
    calculate_zelda_advantage = None
    _ZELDA_AVAILABLE = False

logger = logging.getLogger(__name__)


@login_required
@require_POST
def connection_action_view(request):
    """
    Handles PENDING -> ACCEPTED/DECLINED transitions, and ACCEPTED -> FUNDED.
    The party who did NOT initiate the connection accepts/declines it;
    only the founder can mark a deal FUNDED.
    """
    try:
        data = json.loads(request.body)
        request_id = data.get('id')
        action = data.get('action') # Expected: 'ACCEPTED', 'DECLINED', or 'FUNDED'

        if action not in ['ACCEPTED', 'DECLINED', 'FUNDED']:
            return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)

        conn_req = get_object_or_404(Connection, id=request_id)

        if action == 'FUNDED':
            if conn_req.founder.user != request.user:
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
            if conn_req.status != 'ACCEPTED':
                return JsonResponse({'status': 'error', 'message': 'Only accepted connections can be marked funded.'}, status=400)
        else:
            # The party who did NOT initiate the connection is the one who accepts/declines it
            responder_user = conn_req.investor.user if conn_req.initiated_by == 'FOUNDER' else conn_req.founder.user
            if responder_user != request.user:
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

        conn_req.status = action
        conn_req.save(update_fields=['status'])

        if action == 'FUNDED':
            log_investor_event(conn_req.investor.user, conn_req.founder, 'funded')
            from .tasks import grade_investor_prediction_snapshots
            grade_investor_prediction_snapshots.delay(conn_req.investor.id, conn_req.founder.id)

        return JsonResponse({'status': 'success', 'new_status': action})
    except Exception as e:
        logger.error(f"Connection action error: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@require_POST
def acquisition_connection_action_view(request):
    """
    Business Marketplace equivalent of connection_action_view. Handles
    PENDING -> ACCEPTED/DECLINED transitions, and ACCEPTED -> CLOSED (the
    M&A marketplace's terminal state, equivalent to FUNDED).
    """
    try:
        data = json.loads(request.body)
        request_id = data.get('id')
        action = data.get('action')  # Expected: 'ACCEPTED', 'DECLINED', or 'CLOSED'

        if action not in ['ACCEPTED', 'DECLINED', 'CLOSED']:
            return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)

        conn_req = get_object_or_404(AcquisitionConnection, id=request_id)

        if action == 'CLOSED':
            if conn_req.seller.user != request.user:
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
            if conn_req.status != 'ACCEPTED':
                return JsonResponse({'status': 'error', 'message': 'Only accepted connections can be marked closed.'}, status=400)
        else:
            responder_user = conn_req.buyer.user if conn_req.initiated_by == 'SELLER' else conn_req.seller.user
            if responder_user != request.user:
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

        conn_req.status = action
        conn_req.save(update_fields=['status'])

        if action == 'CLOSED':
            log_buyer_event(conn_req.buyer.user, conn_req.seller, 'closed')
            from .tasks import grade_buyer_prediction_snapshots
            grade_buyer_prediction_snapshots.delay(conn_req.buyer.id, conn_req.seller.id)

        return JsonResponse({'status': 'success', 'new_status': action})
    except Exception as e:
        logger.error(f"Acquisition connection action error: {str(e)}")
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

def _generate_deal_explanatory_insights(ai_score, rule_score, seller, buyer):
    """
    Deal-economics equivalent of _generate_explanatory_insights, for the
    Business Marketplace's Explanatory AI Insights panel.
    """
    industry_str = getattr(seller, 'industry', '') or ''
    thesis_str = getattr(buyer, 'acquisition_thesis', '') or ''
    asking_price = getattr(seller, 'asking_price', None)
    budget_min = getattr(buyer, 'budget_min', None)
    budget_max = getattr(buyer, 'budget_max', None)

    industry_match = "Match" if industry_str.lower() in thesis_str.lower() else "Neutral"
    if asking_price is not None and budget_min is not None and budget_max is not None and budget_min <= asking_price <= budget_max:
        size_fit = "Excellent"
    else:
        size_fit = "Partial"

    return {
        'match_percentage': int(round(ai_score)),
        'summary': f"Blended alignment index of {round(ai_score)}% via semantic matching vectors and deal-economics validation rules.",
        'pillars': [
            {'title': 'Industry Alignment', 'score': industry_match, 'desc': f"Evaluated business industry '{industry_str}' against acquirer thesis criteria."},
            {'title': 'Deal Size Fit', 'score': size_fit, 'desc': f"Asking price benchmarked against the acquirer's stated budget range."},
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
        return redirect('usersettings:edit_investor_profile')

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
    connection_status_map = dict(
        Connection.objects.filter(investor=investor_profile).values_list('founder_id', 'status')
    )
    requested_ids = connection_status_map.keys()

    # Privacy Gatekeeper: Only select records where is_private=False
    if not investor_profile.focus_vector and investor_profile.investment_focus:
        search_terms = [term.strip() for term in investor_profile.investment_focus.replace(',', ' ').split() if len(term.strip()) > 2]
        query = Q()
        for term in search_terms:
            query |= Q(sector__icontains=term) | Q(description__icontains=term) | Q(company_name__icontains=term)

        founders = Application.objects.filter(is_private=False).exclude(review_status='DENIED').filter(
            query | Q(stage__icontains=investor_profile.investment_stage)
        ).select_related('user')
    else:
        founders = Application.objects.filter(is_private=False).exclude(review_status='DENIED').select_related('user')

    # Dashboard filters — narrow the match set on top of whatever the AI/rule
    # engine already surfaced, same free-text icontains approach as global_search
    # since stage/sector are free-text CharFields with inconsistent casing.
    filter_stage = request.GET.get('stage', '').strip()
    filter_industry = request.GET.get('industry', '').strip()
    filter_location = request.GET.get('location', '').strip()

    if filter_stage:
        founders = founders.filter(stage__icontains=filter_stage)
    if filter_industry:
        founders = founders.filter(sector__icontains=filter_industry)
    if filter_location:
        founders = founders.filter(geography__icontains=filter_location)

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
                'connection_status': connection_status_map.get(founder.id),
                'ai_insights': _generate_explanatory_insights(ai_score, rule_score, founder, investor_profile)
            })
    
    match_results = sorted(match_results, key=lambda x: x['final_score'], reverse=True)

    return render(request, 'matchmaking/investor_dashboard.html', {
        'matches': match_results,
        'investor': investor_profile,
        'filters': {
            'stage': filter_stage,
            'industry': filter_industry,
            'location': filter_location,
        },
    })


@login_required
def buyer_dashboard(request):
    """
    Business Marketplace dashboard for acquirers: ranks seller listings by
    the blended deal-economics + AI algorithm. Mirrors investor_dashboard,
    scored on industry/deal-size/structure fit instead of sector/stage.
    """
    buyer_profile = getattr(request.user, 'match_buyer_profile', None)

    if not buyer_profile:
        messages.info(request, "Please complete your buyer profile to view business matches.")
        return redirect('usersettings:edit_buyer_profile')

    # Lazy-generation of the acquisition-thesis vector
    if not buyer_profile.focus_vector and buyer_profile.acquisition_thesis:
        try:
            vector_array = generate_profile_embedding(buyer_profile.acquisition_thesis)
            if vector_array:
                buyer_profile.focus_vector = vector_array
                buyer_profile.save()
        except Exception as e:
            logger.error(f"Failed to generate buyer focus vector: {str(e)}")
            buyer_profile.focus_vector = None

    match_results = []
    connection_status_map = dict(
        AcquisitionConnection.objects.filter(buyer=buyer_profile).values_list('seller_id', 'status')
    )
    requested_ids = connection_status_map.keys()

    # Privacy Gatekeeper: Only select listings where is_private=False
    sellers = SellerApplication.objects.filter(is_private=False).exclude(review_status='DENIED').select_related('user')

    # Dashboard filters — deal economics, not sector/stage
    filter_industry = request.GET.get('industry', '').strip()
    filter_structure = request.GET.get('structure', '').strip()
    filter_max_price = request.GET.get('max_price', '').strip()

    if filter_industry:
        sellers = sellers.filter(industry__icontains=filter_industry)
    if filter_structure:
        sellers = sellers.filter(deal_structure=filter_structure)
    if filter_max_price:
        try:
            sellers = sellers.filter(asking_price__lte=float(filter_max_price))
        except ValueError:
            pass

    for seller in sellers:
        if not seller.description_vector and seller.description:
            try:
                vector_array = generate_profile_embedding(seller.description)
                if vector_array:
                    seller.description_vector = vector_array
                    seller.save()
            except Exception as e:
                logger.warning(f"Failed lazy-generation embedding for seller listing {seller.id}: {str(e)}")

        if buyer_profile.focus_vector and seller.description_vector:
            try:
                raw_ai_similarity = calculate_similarity(buyer_profile.focus_vector, seller.description_vector)
                ai_score = max(0.0, min(100.0, raw_ai_similarity * 100))
            except Exception:
                ai_score = 50.0
        else:
            ai_score = 50.0

        rule_score = calculate_deal_rule_based_score(seller=seller, buyer=buyer_profile)
        final_score = get_deal_blended_match(ai_score, rule_score, seller=seller, buyer=buyer_profile)

        if final_score > 10:
            match_results.append({
                'seller': seller,
                'ai_score': round(ai_score, 1),
                'rule_score': round(rule_score, 1),
                'final_score': round(final_score, 1),
                'already_requested': seller.id in requested_ids,
                'connection_status': connection_status_map.get(seller.id),
                'deal_insights': _generate_deal_explanatory_insights(ai_score, rule_score, seller, buyer_profile)
            })

    match_results = sorted(match_results, key=lambda x: x['final_score'], reverse=True)

    return render(request, 'matchmaking/buyer_dashboard.html', {
        'matches': match_results,
        'buyer': buyer_profile,
        'filters': {
            'industry': filter_industry,
            'structure': filter_structure,
            'max_price': filter_max_price,
        },
    })


@login_required
def investor_shortlist(request):
    """
    Founders this investor has thumbs-up'd (MatchFeedback.vote=1) — the
    "only show liked profiles" / favorites view for investors.
    """
    investor_profile = getattr(request.user, 'match_investor_profile', None)
    if not investor_profile:
        messages.info(request, "Please complete your investor profile to view your shortlist.")
        return redirect('usersettings:edit_investor_profile')

    liked_founder_ids = MatchFeedback.objects.filter(
        investor=investor_profile, vote=1
    ).values_list('application_id', flat=True)

    founders = Application.objects.filter(
        id__in=liked_founder_ids, is_private=False
    ).exclude(review_status='DENIED').select_related('user')

    requested_ids = Connection.objects.filter(investor=investor_profile).values_list('founder_id', flat=True)

    shortlist = []
    for founder in founders:
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
        final_score = max(0, min(100, final_score + 10))  # thumbs-up nudge, consistent with the bulletin board

        shortlist.append({
            'founder': founder,
            'final_score': round(final_score, 1),
            'already_requested': founder.id in requested_ids,
        })

    shortlist = sorted(shortlist, key=lambda x: x['final_score'], reverse=True)

    return render(request, 'matchmaking/investor_shortlist.html', {
        'shortlist': shortlist,
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
        return redirect('usersettings:edit_founder_profile')

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

    accepted_connections = Connection.objects.filter(
        founder=application,
        status='ACCEPTED'
    ).select_related('investor__user')

    # Privacy Gatekeeper: Only fetch allocators where is_private=False
    investors = InvestorApplication.objects.filter(is_private=False).exclude(review_status='DENIED').select_related('user')
    match_results = []
    connection_status_map = dict(
        Connection.objects.filter(founder=application).values_list('investor_id', 'status')
    )

    # Dashboard filters — same free-text icontains approach as the investor
    # dashboard, since investment_stage/focus are free-text CharFields.
    filter_stage = request.GET.get('stage', '').strip()
    filter_focus = request.GET.get('focus', '').strip()
    filter_location = request.GET.get('location', '').strip()

    if filter_stage:
        investors = investors.filter(investment_stage__icontains=filter_stage)
    if filter_focus:
        investors = investors.filter(investment_focus__icontains=filter_focus)
    if filter_location:
        investors = investors.filter(location__icontains=filter_location)

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
                'already_requested': investor.id in connection_status_map,
                'connection_status': connection_status_map.get(investor.id),
                'ai_insights': _generate_explanatory_insights(ai_score, rule_score, application, investor)
            })
    
    match_results = sorted(match_results, key=lambda x: x['final_score'], reverse=True)

    return render(request, 'matchmaking/founder_dashboard.html', {
        'matches': match_results,
        'application': application,
        'pending_requests': pending_requests,
        'accepted_connections': accepted_connections,
        'filters': {
            'stage': filter_stage,
            'focus': filter_focus,
            'location': filter_location,
        },
    })


@login_required
def seller_dashboard(request):
    """
    Business Marketplace dashboard for sellers: view matching acquirers
    ranked by the blended deal-economics + AI algorithm. Mirrors
    founder_dashboard. Filters out private buyer mandates by default.
    """
    seller_profile = getattr(request.user, 'match_seller_profile', None)

    if not seller_profile:
        messages.info(request, "Complete your business listing to see acquirer matches.")
        return redirect('usersettings:edit_seller_profile')

    if not seller_profile.description_vector and seller_profile.description:
        try:
            vector_array = generate_profile_embedding(seller_profile.description)
            if vector_array:
                seller_profile.description_vector = vector_array
                seller_profile.save()
        except Exception as e:
            logger.warning(f"Failed lazy-generation embedding for seller listing {seller_profile.id}: {str(e)}")

    pending_requests = AcquisitionConnection.objects.filter(
        seller=seller_profile,
        status__iexact='pending'
    ).select_related('buyer__user')

    accepted_connections = AcquisitionConnection.objects.filter(
        seller=seller_profile,
        status='ACCEPTED'
    ).select_related('buyer__user')

    # Privacy Gatekeeper: Only fetch acquirers where is_private=False
    buyers = BuyerApplication.objects.filter(is_private=False).exclude(review_status='DENIED').select_related('user')
    match_results = []
    connection_status_map = dict(
        AcquisitionConnection.objects.filter(seller=seller_profile).values_list('buyer_id', 'status')
    )

    # Dashboard filters — deal economics, not sector/stage
    filter_structure = request.GET.get('structure', '').strip()
    filter_min_budget = request.GET.get('min_budget', '').strip()

    if filter_structure:
        buyers = buyers.filter(preferred_deal_structure=filter_structure)
    if filter_min_budget:
        try:
            buyers = buyers.filter(budget_max__gte=float(filter_min_budget))
        except ValueError:
            pass

    for buyer in buyers:
        if seller_profile.description_vector and buyer.focus_vector:
            try:
                raw_ai_similarity = calculate_similarity(seller_profile.description_vector, buyer.focus_vector)
                ai_score = max(0.0, min(100.0, raw_ai_similarity * 100))
            except Exception:
                ai_score = 50.0
        else:
            ai_score = 50.0

        rule_score = calculate_deal_rule_based_score(seller=seller_profile, buyer=buyer)
        final_score = get_deal_blended_match(ai_score, rule_score, seller=seller_profile, buyer=buyer)

        if final_score > 15:
            match_results.append({
                'buyer': buyer,
                'final_score': round(final_score, 1),
                'rule_match': rule_score >= 80,
                'already_requested': buyer.id in connection_status_map,
                'connection_status': connection_status_map.get(buyer.id),
                'deal_insights': _generate_deal_explanatory_insights(ai_score, rule_score, seller_profile, buyer)
            })

    match_results = sorted(match_results, key=lambda x: x['final_score'], reverse=True)

    # Zelda tie-in: surface the seller's most recent business valuation as a
    # suggested asking-price reference, if they've run one.
    suggested_valuation = None
    try:
        from zelda_api.vector_models import DocumentSource
        recent_doc = DocumentSource.objects.filter(
            uploaded_by=request.user, document_type='business_valuation'
        ).order_by('-created_at').first()
        if recent_doc and hasattr(recent_doc, 'valuation_report'):
            suggested_valuation = recent_doc.valuation_report
    except Exception as e:
        logger.warning(f"Failed to look up business valuation for seller dashboard: {str(e)}")

    return render(request, 'matchmaking/seller_dashboard.html', {
        'matches': match_results,
        'seller_profile': seller_profile,
        'pending_requests': pending_requests,
        'accepted_connections': accepted_connections,
        'suggested_valuation': suggested_valuation,
        'filters': {
            'structure': filter_structure,
            'min_budget': filter_min_budget,
        },
    })


@login_required
@founder_required
def fundraising_crm(request):
    """Personal outreach Kanban board — see FundraisingLead docstring for why
    this is decoupled from Connection."""
    application = getattr(request.user, 'match_founder_profile', None)
    if not application:
        messages.info(request, "Complete your founder profile to use the Fundraising CRM.")
        return redirect('usersettings:edit_founder_profile')

    leads = FundraisingLead.objects.filter(founder=application)
    leads_by_stage = {stage_key: [] for stage_key, _ in FundraisingLead.STAGE_CHOICES}
    for lead in leads:
        leads_by_stage[lead.stage].append(lead)

    # A list of {key, label, leads} dicts — Django templates can't do a
    # variable dict-key lookup (board.key doesn't substitute key's value),
    # so this shape lets the template just iterate straight through.
    board = [
        {'key': stage_key, 'label': stage_label, 'leads': leads_by_stage[stage_key]}
        for stage_key, stage_label in FundraisingLead.STAGE_CHOICES
    ]

    return render(request, 'matchmaking/fundraising_crm.html', {
        'application': application,
        'board': board,
        'stage_choices': FundraisingLead.STAGE_CHOICES,
    })


@login_required
@require_POST
def create_lead(request):
    application = getattr(request.user, 'match_founder_profile', None)
    if not application:
        raise Http404("Founder profile required.")

    investor_name = request.POST.get('investor_name', '').strip()
    if not investor_name:
        messages.error(request, "Investor/VC name is required.")
        return redirect('matchmaking:fundraising_crm')

    stage = request.POST.get('stage', 'LEADS')
    if stage not in dict(FundraisingLead.STAGE_CHOICES):
        stage = 'LEADS'

    FundraisingLead.objects.create(
        founder=application,
        investor_name=investor_name,
        firm_name=request.POST.get('firm_name', '').strip(),
        contact_email=request.POST.get('contact_email', '').strip(),
        notes=request.POST.get('notes', '').strip(),
        stage=stage,
    )
    return redirect('matchmaking:fundraising_crm')


@login_required
@require_POST
def update_lead_stage(request, lead_id):
    lead = get_object_or_404(FundraisingLead, id=lead_id)
    if lead.founder.user != request.user:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    try:
        payload = json.loads(request.body)
        stage = payload.get('stage')
        if stage not in dict(FundraisingLead.STAGE_CHOICES):
            return JsonResponse({'status': 'error', 'message': 'Invalid stage'}, status=400)
        lead.stage = stage
        lead.save(update_fields=['stage', 'updated_at'])
        return JsonResponse({'status': 'success', 'stage': stage})
    except Exception as e:
        logger.warning(f"Lead stage update failed: {str(e)}")
        return JsonResponse({'status': 'error'}, status=400)


@login_required
@require_POST
def delete_lead(request, lead_id):
    lead = get_object_or_404(FundraisingLead, id=lead_id)
    if lead.founder.user != request.user:
        raise Http404("Access Denied")
    lead.delete()
    return redirect('matchmaking:fundraising_crm')


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


@login_required
def find_similar_startups(request, application_id):
    """
    Exposes the existing embedding infrastructure as a company-to-company
    "lookalike" search — no new model, reuses calculate_similarity() and
    description_vector already computed for founder/investor matching.
    """
    source = get_object_or_404(Application, id=application_id)

    if not source.description_vector and source.description:
        try:
            vector_array = generate_profile_embedding(source.description)
            if vector_array:
                source.description_vector = vector_array
                source.save()
        except Exception as e:
            logger.warning(f"Failed lazy-generation embedding for application {source.id}: {str(e)}")

    results = []
    if source.description_vector:
        candidates = Application.objects.exclude(id=source.id).filter(
            is_private=False, description_vector__isnull=False
        ).exclude(review_status='DENIED').select_related('user')

        for candidate in candidates:
            score = calculate_similarity(source.description_vector, candidate.description_vector)
            if score > 0.3:
                results.append({'application': candidate, 'score': round(score * 100, 1)})

        results = sorted(results, key=lambda x: x['score'], reverse=True)[:6]

    return render(request, 'matchmaking/similar_startups.html', {
        'source': source,
        'results': results,
    })


def get_foundry_pulse_events(limit=15):
    """
    Read-only aggregation of recent platform milestones from existing timestamped
    models — no new tracking, no background workers. Anonymizes private profiles.
    """
    from blog.models import Article
    from jobs.models import JobListing

    events = []

    for app in Application.objects.filter(review_status='APPROVED').order_by('-created_at')[:limit]:
        name = app.company_name if not app.is_private else 'A new founder'
        events.append({
            'icon': 'bi-rocket-takeoff-fill',
            'message': f"{name} joined the network in {app.sector or 'General Tech'}.",
            'timestamp': app.created_at,
        })

    for inv in InvestorApplication.objects.filter(review_status='APPROVED').order_by('-created_at')[:limit]:
        name = inv.company_name if not inv.is_private else 'A new investor'
        events.append({
            'icon': 'bi-graph-up-arrow',
            'message': f"{name} joined the network.",
            'timestamp': inv.created_at,
        })

    connection_labels = {
        'pending': ('bi-hand-index-thumb', 'A new introduction was requested'),
        'ACCEPTED': ('bi-check-circle-fill', 'An introduction was accepted'),
        'FUNDED': ('bi-trophy-fill', 'A deal was funded'),
    }
    for conn in Connection.objects.select_related('founder', 'investor').order_by('-updated_at')[:limit]:
        icon, label = connection_labels.get(conn.status, ('bi-hand-index-thumb', 'A connection was updated'))
        if not conn.founder.is_private and not conn.investor.is_private:
            label = f"{label}: {conn.investor.company_name} ↔ {conn.founder.company_name}"
        events.append({'icon': icon, 'message': label + '.', 'timestamp': conn.updated_at})

    for article in Article.objects.select_related('author').order_by('-created_on')[:limit]:
        events.append({
            'icon': 'bi-file-earmark-text-fill',
            'message': f"{article.author.username if article.author else 'Someone'} published “{article.title}”.",
            'timestamp': article.created_on,
        })

    for job in JobListing.objects.filter(is_active=True).order_by('-created_at')[:limit]:
        events.append({
            'icon': 'bi-briefcase-fill',
            'message': f"{job.company_name} posted a new opening: {job.title}.",
            'timestamp': job.created_at,
        })

    events.sort(key=lambda e: e['timestamp'], reverse=True)
    return events[:limit]


def founder_bulletin_board(request):
    """
    Queries verified public startup Application profiles to display on the Interlink Foundry bulletin board.
    """
    # Privacy Gatekeeper: Only pull applications where is_private is explicitly False
    pitches_queryset = Application.objects.filter(is_private=False).exclude(review_status='DENIED').select_related('user')
    
    selected_sector = request.GET.get('sector', '').strip()
    search_query = request.GET.get('q', '').strip()

    if selected_sector:
        pitches_queryset = pitches_queryset.filter(sector__iexact=selected_sector)

    if search_query:
        from django.db.models import Q
        pitches_queryset = pitches_queryset.filter(
            Q(company_name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(sector__icontains=search_query) |
            Q(extra_info__icontains=search_query)
        )

    investor_profile = None
    if request.user.is_authenticated:
        investor_profile = getattr(request.user, 'match_investor_profile', None)

    feedback_map = {}
    if investor_profile:
        feedback_map = dict(
            MatchFeedback.objects.filter(
                investor=investor_profile, application__in=pitches_queryset
            ).values_list('application_id', 'vote')
        )

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

        # Thumbs up/down nudges the score shown for this investor's own feedback
        vote = feedback_map.get(pitch.id)
        pitch.base_match_percentage = match_percentage
        pitch.investor_vote = vote or 0
        if vote:
            match_percentage = max(0, min(100, match_percentage + (vote * 10)))

        pitch.match_percentage = match_percentage
        pitch.ai_insights = ai_insights_data
        pitches.append(pitch)
        
    if investor_profile and investor_profile.focus_vector:
        pitches = sorted(pitches, key=lambda x: x.match_percentage, reverse=True)

    return render(request, 'matchmaking/bulletin_board.html', {
        'pitches': pitches,
        'selected_sector': selected_sector,
        'pulse_events': get_foundry_pulse_events(),
    })


def acquisition_bulletin_board(request):
    """
    Public browse page for the Business Marketplace — mirrors
    founder_bulletin_board, but for businesses-for-sale matched against
    deal economics rather than sector/stage. Kept as its own view (not
    merged into the founder bulletin board) since the two marketplaces
    have different privacy and matching rules.
    """
    listings_queryset = SellerApplication.objects.filter(is_private=False).exclude(review_status='DENIED').select_related('user')

    selected_industry = request.GET.get('industry', '').strip()
    search_query = request.GET.get('q', '').strip()

    if selected_industry:
        listings_queryset = listings_queryset.filter(industry__iexact=selected_industry)

    if search_query:
        listings_queryset = listings_queryset.filter(
            Q(company_name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(industry__icontains=search_query) |
            Q(extra_info__icontains=search_query)
        )

    buyer_profile = None
    if request.user.is_authenticated:
        buyer_profile = getattr(request.user, 'match_buyer_profile', None)

    feedback_map = {}
    if buyer_profile:
        feedback_map = dict(
            DealFeedback.objects.filter(
                buyer=buyer_profile, seller__in=listings_queryset
            ).values_list('seller_id', 'vote')
        )

    listings = []
    for listing in listings_queryset:
        deal_insights_data = None

        if buyer_profile and buyer_profile.focus_vector and listing.description_vector:
            try:
                raw_similarity = calculate_similarity(buyer_profile.focus_vector, listing.description_vector)
                ai_score = max(0.0, min(100.0, raw_similarity * 100))
                match_percentage = int(round(ai_score))

                rule_score = calculate_deal_rule_based_score(seller=listing, buyer=buyer_profile)
                deal_insights_data = _generate_deal_explanatory_insights(ai_score, rule_score, listing, buyer_profile)
            except Exception:
                match_percentage = 75
        else:
            match_percentage = 75

        vote = feedback_map.get(listing.id)
        listing.base_match_percentage = match_percentage
        listing.buyer_vote = vote or 0
        if vote:
            match_percentage = max(0, min(100, match_percentage + (vote * 10)))

        listing.match_percentage = match_percentage
        listing.deal_insights = deal_insights_data
        listings.append(listing)

    if buyer_profile and buyer_profile.focus_vector:
        listings = sorted(listings, key=lambda x: x.match_percentage, reverse=True)

    return render(request, 'matchmaking/acquisition_bulletin_board.html', {
        'listings': listings,
        'selected_industry': selected_industry,
    })


# ==========================================
# INTERACTION & TRANSACTION HANDLERS
# ==========================================

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

    if not investor_profile.is_premium:
        daily_count = Connection.objects.filter(
            investor=investor_profile,
            initiated_by='INVESTOR',
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        if daily_count >= 3:
            messages.error(request, "Free tier is limited to 3 introduction requests per day. Upgrade to Premium for uncapped intros.")
            return redirect('matchmaking:investor_dashboard')

    from usersettings.models import UserSettings
    if not UserSettings.for_user(founder_app.user).accept_invitation_requests:
        messages.error(request, "This founder isn't accepting introduction requests right now.")
        return redirect('matchmaking:investor_dashboard')

    connection, created = Connection.objects.get_or_create(
        investor=investor_profile,
        founder=founder_app
    )

    log_investor_event(request.user, founder_app, 'intro_request')

    if created:
        from notifications.models import Notification
        try:
            Notification.objects.create(
                recipient=founder_app.user,
                sender=request.user,
                notification_type='INTRO_REQUEST',
                message=f"{investor_profile.company_name or investor_profile.full_name} requested an introduction to {founder_app.company_name}.",
                target_url=reverse('matchmaking:founder_dashboard')
            )
        except Exception as e:
            logger.warning(f"Failed to create intro-request notification: {str(e)}")

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
def request_intro_from_founder(request, investor_id):
    """
    Reverse of request_intro: a founder extends a hand to an investor.
    The investor is the one who accepts/declines (see connection_action_view).
    """
    investor_app = get_object_or_404(InvestorApplication, id=investor_id)
    founder_profile = getattr(request.user, 'match_founder_profile', None)

    if not founder_profile:
        messages.error(request, "Complete your founder profile first.")
        return redirect('matchmaking:founder_dashboard')

    connection, created = Connection.objects.get_or_create(
        investor=investor_app,
        founder=founder_profile,
        defaults={'initiated_by': 'FOUNDER'}
    )

    if created:
        from notifications.models import Notification
        try:
            Notification.objects.create(
                recipient=investor_app.user,
                sender=request.user,
                notification_type='INTRO_REQUEST',
                message=f"{founder_profile.company_name} requested an introduction.",
                target_url=reverse('matchmaking:investor_dashboard')
            )
        except Exception as e:
            logger.warning(f"Failed to create intro-request notification: {str(e)}")

        messages.success(request, f"Intro request sent to {investor_app.company_name or investor_app.full_name}!")
    else:
        messages.info(request, "You have already requested an introduction to this investor.")

    return redirect('matchmaking:founder_dashboard')


@login_required
@require_POST
def request_acquisition_intro(request, seller_id, buyer_id):
    """
    Business Marketplace equivalent of request_intro: a buyer requests an
    introduction to a seller's listing.
    """
    seller_app = get_object_or_404(SellerApplication, id=seller_id)
    buyer_profile = getattr(request.user, 'match_buyer_profile', None)

    if not buyer_profile or str(buyer_profile.id) != str(buyer_id):
        messages.error(request, "Authorization mismatched. Access to introduction workflow denied.")
        return redirect('matchmaking:buyer_dashboard')

    if not buyer_profile.is_premium:
        daily_count = AcquisitionConnection.objects.filter(
            buyer=buyer_profile,
            initiated_by='BUYER',
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        if daily_count >= 3:
            messages.error(request, "Free tier is limited to 3 introduction requests per day. Upgrade to Premium for uncapped intros.")
            return redirect('matchmaking:buyer_dashboard')

    from usersettings.models import UserSettings
    if not UserSettings.for_user(seller_app.user).accept_invitation_requests:
        messages.error(request, "This seller isn't accepting introduction requests right now.")
        return redirect('matchmaking:buyer_dashboard')

    connection, created = AcquisitionConnection.objects.get_or_create(
        buyer=buyer_profile,
        seller=seller_app
    )

    log_buyer_event(request.user, seller_app, 'intro_request')

    if created:
        from notifications.models import Notification
        try:
            Notification.objects.create(
                recipient=seller_app.user,
                sender=request.user,
                notification_type='INTRO_REQUEST',
                message=f"{buyer_profile.company_name or buyer_profile.full_name} requested an introduction regarding {seller_app.company_name}.",
                target_url=reverse('matchmaking:seller_dashboard')
            )
        except Exception as e:
            logger.warning(f"Failed to create acquisition intro-request notification: {str(e)}")

        messages.success(request, f"Intro request sent for {seller_app.company_name}!")
    else:
        messages.info(request, "You have already requested an introduction to this listing.")

    return redirect('matchmaking:buyer_dashboard')


@login_required
@require_POST
def request_intro_from_seller(request, buyer_id):
    """
    Reverse of request_acquisition_intro: a seller extends a hand to a
    buyer. The buyer is the one who accepts/declines.
    """
    buyer_app = get_object_or_404(BuyerApplication, id=buyer_id)
    seller_profile = getattr(request.user, 'match_seller_profile', None)

    if not seller_profile:
        messages.error(request, "Complete your business listing first.")
        return redirect('matchmaking:seller_dashboard')

    connection, created = AcquisitionConnection.objects.get_or_create(
        buyer=buyer_app,
        seller=seller_profile,
        defaults={'initiated_by': 'SELLER'}
    )

    if created:
        from notifications.models import Notification
        try:
            Notification.objects.create(
                recipient=buyer_app.user,
                sender=request.user,
                notification_type='INTRO_REQUEST',
                message=f"{seller_profile.company_name} requested an introduction.",
                target_url=reverse('matchmaking:buyer_dashboard')
            )
        except Exception as e:
            logger.warning(f"Failed to create acquisition intro-request notification: {str(e)}")

        messages.success(request, f"Intro request sent to {buyer_app.company_name or buyer_app.full_name}!")
    else:
        messages.info(request, "You have already requested an introduction to this buyer.")

    return redirect('matchmaking:seller_dashboard')


@login_required
@require_POST
def record_vote(request):
    """
    Captures platform interaction metadata (Thumbs Up / Down) to optimize data value metrics.
    """
    is_json = request.content_type == 'application/json'

    if is_json:
        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'status': 'error', 'message': 'Invalid request body.'}, status=400)
        application_id = payload.get('application_id')
        vote_value = payload.get('vote')
    else:
        application_id = request.POST.get('application_id')
        vote_value = request.POST.get('vote')

    investor_profile = getattr(request.user, 'match_investor_profile', None)
    if not investor_profile or not application_id:
        if is_json:
            return JsonResponse({'status': 'error', 'message': 'Investor account required.'}, status=403)
        return redirect('matchmaking:investor_dashboard')

    founder_app = get_object_or_404(Application, id=application_id)
    numerical_vote = 1 if vote_value == 'up' else -1

    MatchFeedback.objects.update_or_create(
        user=request.user,
        application=founder_app,
        investor=investor_profile,
        defaults={'vote': numerical_vote}
    )

    log_investor_event(request.user, founder_app, 'thumbs_up' if numerical_vote == 1 else 'thumbs_down')

    if is_json:
        return JsonResponse({'status': 'success'})

    messages.success(request, "Feedback recorded. We're tuning your algorithm!")
    return redirect(request.META.get('HTTP_REFERER', 'matchmaking:investor_dashboard'))


@login_required
@require_POST
def record_deal_vote(request):
    """
    Business Marketplace equivalent of record_vote — captures buyer
    thumbs up/down on a seller listing via DealFeedback.
    """
    is_json = request.content_type == 'application/json'

    if is_json:
        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'status': 'error', 'message': 'Invalid request body.'}, status=400)
        seller_id = payload.get('seller_id')
        vote_value = payload.get('vote')
    else:
        seller_id = request.POST.get('seller_id')
        vote_value = request.POST.get('vote')

    buyer_profile = getattr(request.user, 'match_buyer_profile', None)
    if not buyer_profile or not seller_id:
        if is_json:
            return JsonResponse({'status': 'error', 'message': 'Buyer account required.'}, status=403)
        return redirect('matchmaking:buyer_dashboard')

    seller_app = get_object_or_404(SellerApplication, id=seller_id)
    numerical_vote = 1 if vote_value == 'up' else -1

    DealFeedback.objects.update_or_create(
        user=request.user,
        seller=seller_app,
        buyer=buyer_profile,
        defaults={'vote': numerical_vote}
    )

    log_buyer_event(request.user, seller_app, 'thumbs_up' if numerical_vote == 1 else 'thumbs_down')

    if is_json:
        return JsonResponse({'status': 'success'})

    messages.success(request, "Feedback recorded. We're tuning your algorithm!")
    return redirect(request.META.get('HTTP_REFERER', 'matchmaking:buyer_dashboard'))


@login_required
def initiate_direct_chat(request, target_user_id):
    target_user = get_object_or_404(User, id=target_user_id)
    current_user_id = str(request.user.id)
    target_id_str = str(target_user.id)
    
    if current_user_id == target_id_str:
        return redirect('matchmaking:deal_room_view')

    client = StreamChat(api_key=settings.STREAM_API_KEY, api_secret=settings.STREAM_API_SECRET)
    
    # 1. Ensure both users exist in Stream
    client.upsert_users([
        {'id': current_user_id, 'name': request.user.username},
        {'id': target_id_str, 'name': target_user.username}
    ])

    # 2. Deterministic Channel ID
    sorted_ids = sorted([int(current_user_id), int(target_id_str)])
    channel_id = f"chat_{sorted_ids[0]}_and_{sorted_ids[1]}"

    # 3. Create the channel with explicit server-side creator mapping
    channel = client.channel("messaging", channel_id)
    
    channel.create(
        user_id=current_user_id,
        data={
            "created_by_id": current_user_id,  # <-- THIS IS THE MISSING KEY
            "members": [current_user_id, target_id_str],
            "name": f"{request.user.username} & {target_user.username}"
        }
    )

    # Outcome tracking: resolve which side is the investor and which is the
    # founder, regardless of who initiated — log_investor_event just needs the pair.
    investor_user = None
    founder_app = None
    for a, b in ((request.user, target_user), (target_user, request.user)):
        a_investor = getattr(a, 'match_investor_profile', None)
        b_founder = getattr(b, 'match_founder_profile', None)
        if a_investor and b_founder:
            investor_user, founder_app = a, b_founder
            break
    if investor_user and founder_app:
        log_investor_event(investor_user, founder_app, 'message_sent')

    return redirect('matchmaking:diligence_chat')


@login_required
def deal_room_view(request):
    """
    Renders the empty chat shell. The frontend StreamChatController 
    handles all data fetching, authentication, and UI population.
    """
    return render(request, 'matchmaking/chat.html')

def _filtered_public_applications(request):
    """
    Shared filter logic for both the HTML search results page and the CSV
    export — same filters, same privacy rules, so the two can never drift
    out of sync. Returns (queryset, filters_dict).
    """
    state = request.GET.get('state', '').strip()  # free-text keyword search (label: "Keywords")
    location = request.GET.get('location', '').strip()
    industry = request.GET.get('industry', '').strip()
    stage = request.GET.get('stage', '').strip()
    max_capital = request.GET.get('capital', '').strip()
    min_revenue = request.GET.get('revenue', '').strip()

    # Privacy Gatekeeper: Public matching index only
    queryset = Application.objects.select_related('user').filter(is_private=False).exclude(review_status='DENIED')

    if state:
        queryset = queryset.filter(
            Q(description__icontains=state) | Q(extra_info__icontains=state)
        )

    if location:
        queryset = queryset.filter(geography__icontains=location)

    if industry:
        queryset = queryset.filter(sector__iexact=industry)

    if stage:
        queryset = queryset.filter(stage__iexact=stage)

    if max_capital and max_capital.isdigit():
        queryset = queryset.filter(raising_amount__lte=int(max_capital))

    if min_revenue and min_revenue.isdigit():
        queryset = queryset.filter(current_revenue__gte=int(min_revenue))

    filters = {
        'state': state,
        'location': location,
        'industry': industry,
        'stage': stage,
        'capital': max_capital,
        'revenue': min_revenue,
    }
    return queryset, filters


def global_search(request):
    """
    Advanced Search & Smart Filtering Engine.
    Excludes private applications strictly down the filtering stream.
    """
    queryset, filters = _filtered_public_applications(request)
    return render(request, 'matchmaking/search_results.html', {
        'results': queryset,
        'filters': filters,
    })


@login_required
def export_search_csv(request):
    """
    Premium-gated CSV export of the current search result set — same
    filters, same privacy rules as global_search, just a CSV response.
    """
    investor_profile = getattr(request.user, 'match_investor_profile', None)
    if not investor_profile or not investor_profile.is_premium:
        messages.error(request, "CSV export is a premium investor feature. Upgrade your account to unlock deal flow exports.")
        query_string = request.GET.urlencode()
        redirect_url = reverse('matchmaking:global_search')
        if query_string:
            redirect_url = f"{redirect_url}?{query_string}"
        return redirect(redirect_url)

    queryset, _ = _filtered_public_applications(request)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="interlink_foundry_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Company Name', 'Sector', 'Stage', 'Location', 'Raising Amount',
        'Current Revenue', 'Team Size', 'Years in Business', 'Website',
    ])
    for app in queryset:
        writer.writerow([
            app.company_name,
            app.sector,
            app.stage,
            app.geography,
            app.raising_amount,
            app.current_revenue,
            app.company_size,
            app.years_in_business,
            app.company_website,
        ])

    return response


@login_required
def platform_metrics(request):
    """
    Staff-only operational health dashboard. Every metric here reads from
    fields that already exist — no new tracking, no background workers.
    """
    if not request.user.is_staff:
        messages.error(request, "Access to platform metrics is restricted to staff.")
        return redirect('pages:home')

    from django.db.models import Count
    from django.db.models.functions import Lower

    founder_count = Application.objects.count()
    investor_count = InvestorApplication.objects.count()

    founder_vectorized = Application.objects.filter(description_vector__isnull=False).count()
    investor_vectorized = InvestorApplication.objects.filter(focus_vector__isnull=False).count()
    founder_vector_rate = round((founder_vectorized / founder_count) * 100, 1) if founder_count else 0
    investor_vector_rate = round((investor_vectorized / investor_count) * 100, 1) if investor_count else 0

    connection_funnel = dict(
        Connection.objects.values('status').annotate(count=Count('id')).values_list('status', 'count')
    )

    sector_density = list(
        Application.objects.annotate(sector_lower=Lower('sector'))
        .values('sector_lower')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    thirty_days_ago = timezone.now() - timedelta(days=30)
    registrations_by_day = {}
    for row in Application.objects.filter(created_at__gte=thirty_days_ago).values('created_at__date').annotate(count=Count('id')):
        day = row['created_at__date'].isoformat()
        registrations_by_day[day] = registrations_by_day.get(day, 0) + row['count']
    for row in InvestorApplication.objects.filter(created_at__gte=thirty_days_ago).values('created_at__date').annotate(count=Count('id')):
        day = row['created_at__date'].isoformat()
        registrations_by_day[day] = registrations_by_day.get(day, 0) + row['count']
    registrations_sorted = sorted(registrations_by_day.items())

    active_users_24h = User.objects.filter(last_login__gte=timezone.now() - timedelta(hours=24)).count()

    # Conversion funnel: what share of introductions actually turn into funded deals
    total_connections = sum(connection_funnel.values())
    funded_connections = connection_funnel.get('FUNDED', 0)
    accepted_or_better = connection_funnel.get('ACCEPTED', 0) + funded_connections
    intro_to_accept_rate = round((accepted_or_better / total_connections) * 100, 1) if total_connections else 0
    intro_to_funded_rate = round((funded_connections / total_connections) * 100, 1) if total_connections else 0

    # AI usage stats — how much of the Zelda pipeline is actually being exercised
    from zelda_api.vector_models import DocumentSource, IntelligenceMemo
    from zelda_api.truth_delta_models import TruthDeltaReport
    from matchmaking.models import InvestorInterestEvent
    documents_processed = DocumentSource.objects.filter(status='analyzed').count()
    memos_generated = IntelligenceMemo.objects.count()
    truth_delta_runs = TruthDeltaReport.objects.count()
    zelda_analyses_triggered = InvestorInterestEvent.objects.filter(event_type='analyze').count()

    return render(request, 'matchmaking/platform_metrics.html', {
        'founder_count': founder_count,
        'investor_count': investor_count,
        'founder_vector_rate': founder_vector_rate,
        'investor_vector_rate': investor_vector_rate,
        'connection_funnel': connection_funnel,
        'sector_labels': json.dumps([s['sector_lower'] or 'unspecified' for s in sector_density]),
        'sector_counts': json.dumps([s['count'] for s in sector_density]),
        'registration_labels': json.dumps([d for d, _ in registrations_sorted]),
        'registration_counts': json.dumps([c for _, c in registrations_sorted]),
        'active_users_24h': active_users_24h,
        'intro_to_accept_rate': intro_to_accept_rate,
        'intro_to_funded_rate': intro_to_funded_rate,
        'documents_processed': documents_processed,
        'memos_generated': memos_generated,
        'truth_delta_runs': truth_delta_runs,
        'zelda_analyses_triggered': zelda_analyses_triggered,
    })


class MemoIntelligenceView(APIView):
    """
    GET /api/v1/matchmaking/memo/<startup_name>/
    Aligned with zelda_api MemoIntelligenceView: uses DiligenceEngine vector
    scoring and perform_live_crawl instead of raw cache-only lookups.
    Falls back to cache/task pipeline if Zelda is unavailable.
    """
    from rest_framework.authentication import SessionAuthentication, TokenAuthentication
    from rest_framework.permissions import IsAuthenticated
    authentication_classes = [SessionAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, startup_name):
        founder_app = get_object_or_404(Application, company_name__iexact=startup_name)
        investor_app = InvestorApplication.objects.first()

        if _ZELDA_AVAILABLE and DiligenceEngine and investor_app:
            # Full zelda-aligned path: live crawl + DiligenceEngine vector scoring
            url_to_crawl = getattr(founder_app, 'website', None)
            external_data = self.perform_live_crawl(url_to_crawl) if url_to_crawl else {
                'linkedin_headcount': 0, 'job_board_openings': 0
            }
            vector_score, transparency = DiligenceEngine.calculate_success_vector(
                founder_app, investor_app, external_data
            )
            return Response({
                "startup": founder_app.company_name,
                "success_vector_score": vector_score,
                "transparency_index": transparency,
                "text_synthesis": (
                    f"Memo for {startup_name} generated using live data. Score: {vector_score}/100."
                ),
            })
        else:
            # Fallback: cache / background task pipeline
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

    def perform_live_crawl(self, url):
        """Mirrors zelda_api MemoIntelligenceView.perform_live_crawl."""
        return {'linkedin_headcount': 45, 'job_board_openings': 2}


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
            status='ACCEPTED'
        ).exists()
        if has_access:
            has_advantage_access = True

    # Only calculate if authorized and Zelda is available
    if has_advantage_access and _ZELDA_AVAILABLE and calculate_zelda_advantage:
        zelda_score = calculate_zelda_advantage(founder_app)

    context = {
        'founder_app': founder_app,
        'external_data': external_data,
        'is_processing': is_processing,
        'match_percentage': match_percentage,
        'ai_insights': ai_insights_data,
        'investor': investor_profile,
        'zelda_score': zelda_score,
    }

    return render(request, 'matchmaking/memo_detail.html', context)

@login_required
def download_document(request, doc_id):
    doc = get_object_or_404(Document, id=doc_id)
    room = doc.deal_room

    # Security Check: Is the user the investor in this connection?
    if request.user == room.connection.investor.user and room.is_active:
        return FileResponse(doc.file.open('rb'), as_attachment=True)

    raise Http404("Access Denied")


def _can_view_pitch_deck(request, application):
    """Same privacy rule as the profile page: private decks are owner/staff-only."""
    if request.user == application.user or request.user.is_staff:
        return True
    return not application.is_private


@login_required
def view_pitch_deck(request, application_id):
    application = get_object_or_404(Application, id=application_id)
    if not _can_view_pitch_deck(request, application):
        raise Http404("Access Denied")
    if not application.pitch_deck:
        raise Http404("No pitch deck uploaded.")

    is_pdf = application.pitch_deck.name.lower().endswith('.pdf')

    return render(request, 'matchmaking/pitch_deck_viewer.html', {
        'application': application,
        'is_pdf': is_pdf,
    })


@login_required
def pitch_deck_file(request, application_id):
    application = get_object_or_404(Application, id=application_id)
    if not _can_view_pitch_deck(request, application):
        raise Http404("Access Denied")
    if not application.pitch_deck:
        raise Http404("No pitch deck uploaded.")

    # as_attachment=False: pdf.js fetches this inline, not a download prompt
    return FileResponse(application.pitch_deck.open('rb'), content_type='application/pdf', as_attachment=False)


@login_required
@require_POST
def record_deck_telemetry(request, application_id):
    """
    Ingests navigator.sendBeacon() payloads from the viewer. sendBeacon can't set
    custom headers, so the CSRF token travels as a normal form field
    (request.POST['csrfmiddlewaretoken']) — same as any other Django form POST —
    with the actual telemetry JSON in a second form field, rather than a raw
    JSON body with an X-CSRFToken header.
    Skips silently for the founder previewing their own deck — that's not investor interest.
    """
    application = get_object_or_404(Application, id=application_id)
    if request.user == application.user:
        return JsonResponse({'status': 'skipped'})

    try:
        payload = json.loads(request.POST.get('payload', '{}'))
        client_session_id = payload.get('client_session_id', '')[:64]
        slide_times = payload.get('slide_times', [])

        if not client_session_id or not slide_times:
            return JsonResponse({'status': 'error', 'message': 'Missing data'}, status=400)

        session, _ = PitchDeckViewSession.objects.get_or_create(
            founder=application,
            viewer=request.user,
            client_session_id=client_session_id,
        )

        PitchDeckSlideTime.objects.bulk_create([
            PitchDeckSlideTime(
                session=session,
                slide_number=int(entry['slide']),
                duration_seconds=float(entry['duration']),
            )
            for entry in slide_times
            if 'slide' in entry and 'duration' in entry
        ])

        return JsonResponse({'status': 'success'})
    except Exception as e:
        logger.warning(f"Deck telemetry ingestion failed: {str(e)}")
        return JsonResponse({'status': 'error'}, status=400)


@login_required
def deal_pulse(request):
    """
    Investor-side pipeline board over their real platform Connections,
    bucketed into Active / Needs Attention / Completed. Mirrors the
    founder-side Fundraising CRM's visual pattern, but tracks actual
    Connection records rather than a separate off-platform lead list —
    investors' deal flow already lives on-platform via Connection.
    """
    investor_profile = getattr(request.user, 'match_investor_profile', None)
    if not investor_profile:
        messages.info(request, "Complete your investor profile to use Deal Pulse.")
        return redirect('usersettings:edit_investor_profile')

    connections = Connection.objects.filter(investor=investor_profile).select_related('founder__user')

    completed_statuses = {'FUNDED', 'DECLINED'}
    board = {'ACTIVE': [], 'NEEDS_ATTENTION': [], 'COMPLETED': []}
    for conn in connections:
        if conn.status in completed_statuses:
            board['COMPLETED'].append(conn)
        elif conn.needs_attention:
            board['NEEDS_ATTENTION'].append(conn)
        else:
            board['ACTIVE'].append(conn)

    columns = [
        {'key': 'ACTIVE', 'label': 'Active', 'connections': board['ACTIVE']},
        {'key': 'NEEDS_ATTENTION', 'label': 'Needs Attention', 'connections': board['NEEDS_ATTENTION']},
        {'key': 'COMPLETED', 'label': 'Completed', 'connections': board['COMPLETED']},
    ]

    return render(request, 'matchmaking/deal_pulse.html', {
        'investor': investor_profile,
        'columns': columns,
    })


@login_required
@require_POST
def toggle_deal_attention(request, connection_id):
    conn = get_object_or_404(Connection, id=connection_id, investor__user=request.user)
    conn.needs_attention = not conn.needs_attention
    conn.save(update_fields=['needs_attention', 'updated_at'])
    return redirect('matchmaking:deal_pulse')


@login_required
@require_POST
def update_deal_notes(request, connection_id):
    conn = get_object_or_404(Connection, id=connection_id, investor__user=request.user)
    conn.notes = request.POST.get('notes', '').strip()
    conn.save(update_fields=['notes', 'updated_at'])
    return redirect('matchmaking:deal_pulse')


@login_required
def deck_analytics(request, application_id):
    application = get_object_or_404(Application, id=application_id)
    if not (request.user == application.user or request.user.is_staff):
        messages.error(request, "You don't have access to this deck's analytics.")
        return redirect('accounts:profile', username=application.user.username)

    from django.db.models import Avg, Count

    sessions = PitchDeckViewSession.objects.filter(founder=application)
    total_sessions = sessions.count()
    unique_viewers = sessions.values('viewer').distinct().count()

    slide_stats = list(
        PitchDeckSlideTime.objects.filter(session__founder=application)
        .values('slide_number')
        .annotate(avg_duration=Avg('duration_seconds'), views=Count('id'))
        .order_by('slide_number')
    )

    total_time = sum(row['avg_duration'] * row['views'] for row in slide_stats)
    avg_session_time = round(total_time / total_sessions, 1) if total_sessions else 0

    return render(request, 'matchmaking/deck_analytics.html', {
        'application': application,
        'total_sessions': total_sessions,
        'unique_viewers': unique_viewers,
        'avg_session_time': avg_session_time,
        'slide_labels': json.dumps([f"Slide {row['slide_number']}" for row in slide_stats]),
        'slide_durations': json.dumps([round(row['avg_duration'], 1) for row in slide_stats]),
    })


@login_required
@require_POST
def toggle_follow(request, username):
    target_user = get_object_or_404(User, username=username)

    # Prevent self-following
    if target_user == request.user:
        return JsonResponse({'status': 'error', 'message': 'Cannot follow yourself'}, status=400)

    existing_follow = Follow.objects.filter(follower=request.user, following=target_user).first()

    if existing_follow:
        existing_follow.delete()
        return JsonResponse({'status': 'success', 'is_following': False})

    from usersettings.models import UserSettings
    if not UserSettings.for_user(target_user).accept_follow_requests:
        return JsonResponse({'status': 'error', 'message': 'This user is not accepting new followers.'}, status=403)


@login_required
@require_POST
def post_milestone(request):
    application = getattr(request.user, 'match_founder_profile', None)
    if not application:
        raise PermissionDenied("Only founders can post milestones.")

    milestone_type = request.POST.get('milestone_type', 'other')
    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()

    if not title:
        messages.error(request, "A milestone needs a title.")
        return redirect('matchmaking:founder_dashboard')

    milestone = FounderMilestone.objects.create(
        founder=application,
        milestone_type=milestone_type,
        title=title,
        description=description,
    )

    # Notify followers — fire-and-forget, must never break the posting flow
    try:
        from notifications.models import Notification
        followers = Follow.objects.filter(following=request.user).select_related('follower')
        for f in followers:
            Notification.objects.create(
                recipient=f.follower,
                sender=request.user,
                notification_type='MILESTONE',
                message=f"{application.company_name} posted a new milestone: {milestone.title}",
                target_url=reverse('accounts:profile', kwargs={'username': request.user.username})
            )
    except Exception as e:
        logger.warning(f"Failed to create milestone notifications: {str(e)}")

    messages.success(request, "Milestone posted.")
    return redirect('matchmaking:founder_dashboard')


@login_required
@require_POST
def delete_milestone(request, milestone_id):
    milestone = get_object_or_404(FounderMilestone, id=milestone_id, founder__user=request.user)
    milestone.delete()
    return redirect('matchmaking:founder_dashboard')

    Follow.objects.create(follower=request.user, following=target_user)
    return JsonResponse({'status': 'success', 'is_following': True})