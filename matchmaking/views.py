import csv
import json
import logging
from datetime import timedelta
from urllib.parse import quote
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.db import connection
from django.db.models import Q, F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
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
from matchmaking.models import Application, Connection, InvestorApplication, MatchFeedback, ConnectionRequest, log_investor_event, PitchDeckViewSession, PitchDeckSlideTime, FundraisingLead, FounderMilestone, log_training_example, MessageThread, PitchVideoView, ProfileView, log_page_event, log_search_event, SearchEvent
from matchmaking.models import DataRoomDocument, DataRoomAccessRequest, DataRoomDocumentView, DataRoomInformationRequest, can_view_data_room, can_download_data_room_document, can_view_deal_workspace
from matchmaking.deal_activity import get_deal_activity_timeline
from matchmaking.models import founder_description_meets_word_count
from matchmaking.models import SellerApplication, BuyerApplication, AcquisitionConnection, DealFeedback, log_buyer_event, AcquisitionInterestEvent
from matchmaking.models import PitchVideoComment
from matchmaking.services.ai_engine import calculate_similarity, generate_profile_embedding, calculate_sparse_similarity
from matchmaking.utils import calculate_rule_based_score, get_blended_match, clean_financial_input, passes_hard_filters
from matchmaking.match_components import evaluate_deal_match, evaluate_venture_match
from matchmaking.match_score import Band
from matchmaking.utils import calculate_deal_rule_based_score, get_deal_blended_match
from .forms import DataRoomDocumentForm

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
    Handles PENDING -> ACCEPTED/DECLINED, ACCEPTED -> FUNDED_PENDING (the
    founder's claim), and FUNDED_PENDING -> FUNDED/ACCEPTED (the investor's
    confirmation or denial).

    FUNDED is a verified, two-sided state, not a self-report — it already
    feeds real downstream consumers (an investor's public "companies
    funded" count, quarterly growth-metrics reports, and the match-
    prediction training/grading pipeline below), so letting the founder
    alone flip a connection straight to FUNDED let anyone fabricate that
    signal unilaterally. The founder's action now only proposes it; the
    side effects (log_investor_event, training example, prediction
    grading) fire on the investor's confirmation, not the founder's claim.
    """
    try:
        data = json.loads(request.body)
        request_id = data.get('id')
        action = data.get('action')  # Expected: 'ACCEPTED', 'DECLINED', 'FUNDED', 'CONFIRM_FUNDED', or 'DENY_FUNDED'

        if action not in ['ACCEPTED', 'DECLINED', 'FUNDED', 'CONFIRM_FUNDED', 'DENY_FUNDED']:
            return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)

        conn_req = get_object_or_404(Connection, id=request_id)

        if action == 'FUNDED':
            if conn_req.founder.user != request.user:
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
            if conn_req.status != 'ACCEPTED':
                return JsonResponse({'status': 'error', 'message': 'Only accepted connections can be marked funded.'}, status=400)

            conn_req.status = 'FUNDED_PENDING'
            conn_req.save(update_fields=['status'])

            from notifications.models import Notification
            Notification.objects.create(
                recipient=conn_req.investor.user, sender=request.user, notification_type='FUNDED_CONFIRMATION',
                message=f"{conn_req.founder.company_name or request.user.username} marked your deal as funded — please confirm.",
                target_url=reverse('matchmaking:investor_dashboard'),
            )
            return JsonResponse({'status': 'success', 'new_status': conn_req.status})

        if action in ('CONFIRM_FUNDED', 'DENY_FUNDED'):
            if conn_req.investor.user != request.user:
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
            if conn_req.status != 'FUNDED_PENDING':
                return JsonResponse({'status': 'error', 'message': 'No pending funded claim to respond to.'}, status=400)

            conn_req.status = 'FUNDED' if action == 'CONFIRM_FUNDED' else 'ACCEPTED'
            update_fields = ['status']
            if action == 'CONFIRM_FUNDED':
                conn_req.funded_at = timezone.now()
                update_fields.append('funded_at')
            conn_req.save(update_fields=update_fields)

            if action == 'CONFIRM_FUNDED':
                log_investor_event(conn_req.investor.user, conn_req.founder, 'funded')
                log_training_example('INVESTOR', conn_req.investor.id, 'FOUNDER', conn_req.founder.id, 'POSITIVE', 'funded')
                from .tasks import grade_investor_prediction_snapshots
                grade_investor_prediction_snapshots.delay(conn_req.investor.id, conn_req.founder.id)

            from notifications.models import Notification
            Notification.objects.create(
                recipient=conn_req.founder.user, sender=request.user, notification_type='FUNDED_CONFIRMATION',
                message=(
                    f"{conn_req.investor.company_name or request.user.username} confirmed the deal as funded."
                    if action == 'CONFIRM_FUNDED' else
                    f"{conn_req.investor.company_name or request.user.username} said this deal wasn't funded — marked back as accepted."
                ),
                target_url=reverse('matchmaking:founder_dashboard'),
            )
            return JsonResponse({'status': 'success', 'new_status': conn_req.status})

        # The party who did NOT initiate the connection is the one who accepts/declines it
        responder_user = conn_req.investor.user if conn_req.initiated_by == 'FOUNDER' else conn_req.founder.user
        if responder_user != request.user:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

        conn_req.status = action
        update_fields = ['status']
        if action == 'ACCEPTED':
            conn_req.accepted_at = timezone.now()
            update_fields.append('accepted_at')
        conn_req.save(update_fields=update_fields)

        if action == 'DECLINED':
            log_training_example('INVESTOR', conn_req.investor.id, 'FOUNDER', conn_req.founder.id, 'NEGATIVE', 'declined')

        return JsonResponse({'status': 'success', 'new_status': action})
    except Exception as e:
        logger.error(f"Connection action error: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@require_POST
def acquisition_connection_action_view(request):
    """
    Business Marketplace equivalent of connection_action_view. Handles
    PENDING -> ACCEPTED/DECLINED, ACCEPTED -> CLOSED_PENDING (the seller's
    claim), and CLOSED_PENDING -> CLOSED/ACCEPTED (the buyer's confirmation
    or denial) — same two-sided verification rationale as FUNDED above,
    since CLOSED already feeds the buyer prediction training/grading
    pipeline and shouldn't be a unilateral seller claim.
    """
    try:
        data = json.loads(request.body)
        request_id = data.get('id')
        action = data.get('action')  # Expected: 'ACCEPTED', 'DECLINED', 'CLOSED', 'CONFIRM_CLOSED', or 'DENY_CLOSED'

        if action not in ['ACCEPTED', 'DECLINED', 'CLOSED', 'CONFIRM_CLOSED', 'DENY_CLOSED']:
            return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)

        conn_req = get_object_or_404(AcquisitionConnection, id=request_id)

        if action == 'CLOSED':
            if conn_req.seller.user != request.user:
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
            if conn_req.status != 'ACCEPTED':
                return JsonResponse({'status': 'error', 'message': 'Only accepted connections can be marked closed.'}, status=400)

            conn_req.status = 'CLOSED_PENDING'
            conn_req.save(update_fields=['status'])

            from notifications.models import Notification
            Notification.objects.create(
                recipient=conn_req.buyer.user, sender=request.user, notification_type='CLOSED_CONFIRMATION',
                message=f"{conn_req.seller.company_name or request.user.username} marked this deal as closed — please confirm.",
                target_url=reverse('matchmaking:buyer_dashboard'),
            )
            return JsonResponse({'status': 'success', 'new_status': conn_req.status})

        if action in ('CONFIRM_CLOSED', 'DENY_CLOSED'):
            if conn_req.buyer.user != request.user:
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
            if conn_req.status != 'CLOSED_PENDING':
                return JsonResponse({'status': 'error', 'message': 'No pending closed claim to respond to.'}, status=400)

            conn_req.status = 'CLOSED' if action == 'CONFIRM_CLOSED' else 'ACCEPTED'
            update_fields = ['status']
            if action == 'CONFIRM_CLOSED':
                conn_req.closed_at = timezone.now()
                update_fields.append('closed_at')
            conn_req.save(update_fields=update_fields)

            if action == 'CONFIRM_CLOSED':
                log_buyer_event(conn_req.buyer.user, conn_req.seller, 'closed')
                log_training_example('BUYER', conn_req.buyer.id, 'SELLER', conn_req.seller.id, 'POSITIVE', 'closed')
                from .tasks import grade_buyer_prediction_snapshots
                grade_buyer_prediction_snapshots.delay(conn_req.buyer.id, conn_req.seller.id)

            from notifications.models import Notification
            Notification.objects.create(
                recipient=conn_req.seller.user, sender=request.user, notification_type='CLOSED_CONFIRMATION',
                message=(
                    f"{conn_req.buyer.company_name or request.user.username} confirmed the deal as closed."
                    if action == 'CONFIRM_CLOSED' else
                    f"{conn_req.buyer.company_name or request.user.username} said this deal wasn't closed — marked back as accepted."
                ),
                target_url=reverse('matchmaking:seller_dashboard'),
            )
            return JsonResponse({'status': 'success', 'new_status': conn_req.status})

        responder_user = conn_req.buyer.user if conn_req.initiated_by == 'SELLER' else conn_req.seller.user
        if responder_user != request.user:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

        conn_req.status = action
        update_fields = ['status']
        if action == 'ACCEPTED':
            conn_req.accepted_at = timezone.now()
            update_fields.append('accepted_at')
        conn_req.save(update_fields=update_fields)

        if action == 'DECLINED':
            log_training_example('BUYER', conn_req.buyer.id, 'SELLER', conn_req.seller.id, 'NEGATIVE', 'declined')

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

def _signal_label(signal, matched='Match', partial='Adjacent'):
    """Plain-language label for one component's finding."""
    if signal is None or not signal.present:
        return 'Not stated'
    if signal.value >= 100.0:
        return matched
    if signal.value > 0.0:
        return partial
    return 'Outside'


def _overall_label(band):
    from .match_score import Band
    return {
        Band.STRONG: 'Passed',
        Band.NOTABLE: 'Partial',
        Band.POSSIBLE: 'Partial',
        Band.UNRANKED: 'Unranked',
    }[band]


def _generate_explanatory_insights(result, application, investor):
    """
    Plain-language explanation of why a founder and an investor were
    matched. Rendered on the investor dashboard's match accordion and on
    the Zelda Intelligence Report ("Why Zelda surfaced this"), so the
    wording stays conservative enough to read well in a dense list and on
    a report page alike.

    Reads the MatchResult's signals rather than re-deriving sector and
    stage for itself. It used to do the latter, with subtly different
    rules from the components -- a second opinion on the same question,
    which is how one product ends up disagreeing with itself about
    whether a sector matched.

    No percentage is returned. The band is the user-facing answer; the
    internal score orders candidates within a band and is never rendered.
    """
    from .match_components import SECTOR, STAGE

    signals = {s.key: s for s in result.signals}
    sector, stage = signals.get(SECTOR), signals.get(STAGE)
    sector_hit = bool(sector and sector.present and sector.value >= 100.0)
    stage_hit = bool(stage and stage.present and stage.value >= 100.0)

    if sector_hit and stage_hit:
        summary = "The company's sector and raise stage both line up with your stated focus."
    elif sector_hit:
        summary = "The company's sector lines up with your stated focus; the raise stage is nearby."
    elif stage_hit:
        summary = "The company's raise stage matches your mandate; the sector is adjacent to your focus."
    else:
        summary = "The company is close enough to your focus and mandate to be worth a look."

    sector_str = (getattr(application, 'sector', '') or '').strip()
    stage_str = (getattr(application, 'stage', '') or '').strip()
    mandate_stage_str = (getattr(investor, 'investment_stage', '') or '').strip()

    return {
        'band': result.band.label,
        'summary': summary,
        'pillars': [
            {
                'title': 'Sector',
                'score': _signal_label(sector),
                'desc': f"{sector_str or 'Sector not stated'} — " + (
                    "in your stated focus." if sector_hit
                    else "not stated on one side." if sector is None or not sector.present
                    else "outside your stated focus." if sector.value == 0.0
                    else "not an explicit focus area for you, but close enough to surface."
                ),
            },
            {
                'title': 'Stage',
                'score': _signal_label(stage, partial='Nearby'),
                'desc': f"Raising at {stage_str or 'an unstated stage'} — " + (
                    "matches your mandate." if stage_hit
                    else "no stage stated on one side." if stage is None or not stage.present
                    else f"your mandate is {mandate_stage_str or 'not set'}."
                ),
            },
            {
                'title': 'Overall fit',
                'score': _overall_label(result.band),
                'desc': (
                    "Sector and stage are independently corroborated, so this is a strong match."
                    if result.band.name == 'STRONG'
                    else "Only part of the picture is corroborated, so this is a softer match."
                ),
            },
        ],
    }


def _generate_deal_explanatory_insights(result, seller, buyer):
    """
    Deal-economics equivalent, reading the same MatchResult shape.

    The old copy led with "Blended alignment index of N% via semantic
    matching vectors and deal-economics validation rules" -- a number the
    evidence could not support, wrapped in machine vocabulary. Both are
    gone.
    """
    from .match_components import DEAL_SIZE, DEAL_STRUCTURE, INDUSTRY

    signals = {s.key: s for s in result.signals}
    industry = signals.get(INDUSTRY)
    size = signals.get(DEAL_SIZE)
    structure = signals.get(DEAL_STRUCTURE)
    industry_str = getattr(seller, 'industry', '') or 'not stated'

    return {
        'band': result.band.label,
        'summary': (
            f"This is a {result.band.label.lower()} match on the evidence both sides have stated."
        ),
        'pillars': [
            {
                'title': 'Industry Alignment',
                'score': _signal_label(industry, partial='Adjacent'),
                'desc': f"Business industry '{industry_str}' read against the acquirer's stated thesis.",
            },
            {
                'title': 'Deal Size Fit',
                'score': _signal_label(size, matched='Match', partial='Near'),
                'desc': (
                    "Asking price sits inside the stated budget."
                    if size is not None and size.present and size.value >= 100.0
                    else "Asking price or budget has not been stated on one side."
                    if size is None or not size.present
                    else "Asking price falls outside the stated budget."
                ),
            },
            {
                'title': 'Deal Structure',
                'score': _signal_label(structure, partial='Open'),
                'desc': (
                    structure.detail if structure is not None and structure.present
                    else "Neither side has stated a structure preference, so this says nothing either way."
                ),
            },
        ],
    }


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

    log_page_event(request, 'dashboard_view', role='investor', user=request.user)

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

    pending_requests = Connection.objects.filter(
        investor=investor_profile,
        status__iexact='pending',
        initiated_by='FOUNDER'
    ).select_related('founder__user')

    # Includes FUNDED_PENDING so the investor sees the founder's funded
    # claim here and can confirm/deny it, rather than it only existing as
    # a notification.
    accepted_connections = Connection.objects.filter(
        investor=investor_profile,
        status__in=['ACCEPTED', 'FUNDED_PENDING']
    ).select_related('founder__user')

    match_results = []
    connection_status_map = dict(
        Connection.objects.filter(investor=investor_profile).values_list('founder_id', 'status')
    )
    requested_ids = connection_status_map.keys()

    # Privacy Gatekeeper: uses Application.objects.discoverable() (is_private=False, not archived)
    if not investor_profile.focus_vector and investor_profile.investment_focus:
        search_terms = [term.strip() for term in investor_profile.investment_focus.replace(',', ' ').split() if len(term.strip()) > 2]
        query = Q()
        for term in search_terms:
            query |= Q(sector__icontains=term) | Q(description__icontains=term) | Q(company_name__icontains=term)

        founders = Application.objects.discoverable().exclude(review_status='DENIED').filter(
            query | Q(stage__icontains=investor_profile.investment_stage)
        ).select_related('user')
    else:
        founders = Application.objects.discoverable().exclude(review_status='DENIED').select_related('user')

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
        # Hard-filter gate: excluded entirely rather than down-ranked — see
        # passes_hard_filters' docstring in matchmaking/utils.py.
        if not passes_hard_filters(founder, investor_profile):
            continue

        if not founder.description_vector and founder.description:
            try:
                vector_array = generate_profile_embedding(founder.description)
                if vector_array:
                    founder.description_vector = vector_array
                    founder.save()
            except Exception as e:
                logger.warning(f"Failed lazy-generation embedding for founder application {founder.id}: {str(e)}")

        # One evaluation, one result. Every consumer reads the same shape
        # from the same call rather than assembling its own idea of a
        # match out of raw parts.
        result = evaluate_venture_match(founder, investor_profile)

        if result.band > Band.UNRANKED:
            match_results.append({
                'founder': founder,
                'match': result,
                'band': result.band.label,
                'already_requested': founder.id in requested_ids,
                'connection_status': connection_status_map.get(founder.id),
                'ai_insights': _generate_explanatory_insights(result, founder, investor_profile),
            })

    # Band first, internal score only to order within a band — the score
    # has no meaning across bands and is never shown either way.
    match_results = sorted(
        match_results, key=lambda x: (x['match'].band, x['match'].score), reverse=True)

    intro_quota_remaining = None
    if not investor_profile.is_premium:
        intro_quota_remaining = max(0, DAILY_INTRO_REQUEST_LIMIT - count_investor_intro_requests_today(investor_profile))

    return render(request, 'matchmaking/investor_dashboard.html', {
        'matches': match_results,
        'investor': investor_profile,
        'pending_requests': pending_requests,
        'accepted_connections': accepted_connections,
        'intro_quota_remaining': intro_quota_remaining,
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

    pending_requests = AcquisitionConnection.objects.filter(
        buyer=buyer_profile,
        status__iexact='pending',
        initiated_by='SELLER'
    ).select_related('seller__user')

    # Includes CLOSED_PENDING so the buyer sees the seller's closed claim
    # here and can confirm/deny it, rather than it only existing as a
    # notification.
    accepted_connections = AcquisitionConnection.objects.filter(
        buyer=buyer_profile,
        status__in=['ACCEPTED', 'CLOSED_PENDING']
    ).select_related('seller__user')

    match_results = []
    connection_status_map = dict(
        AcquisitionConnection.objects.filter(buyer=buyer_profile).values_list('seller_id', 'status')
    )
    requested_ids = connection_status_map.keys()

    # Privacy Gatekeeper: uses SellerApplication.objects.discoverable() (is_private=False, not archived)
    sellers = SellerApplication.objects.discoverable().exclude(review_status='DENIED').select_related('user')

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

        result = evaluate_deal_match(seller, buyer_profile)

        if result.band > Band.UNRANKED:
            match_results.append({
                'seller': seller,
                'match': result,
                'band': result.band.label,
                'already_requested': seller.id in requested_ids,
                'connection_status': connection_status_map.get(seller.id),
                'deal_insights': _generate_deal_explanatory_insights(result, seller, buyer_profile),
            })

    match_results = sorted(
        match_results, key=lambda x: (x['match'].band, x['match'].score), reverse=True)

    intro_quota_remaining = None
    if not buyer_profile.is_premium:
        intro_quota_remaining = max(0, DAILY_INTRO_REQUEST_LIMIT - count_buyer_intro_requests_today(buyer_profile))

    return render(request, 'matchmaking/buyer_dashboard.html', {
        'matches': match_results,
        'buyer': buyer_profile,
        'pending_requests': pending_requests,
        'accepted_connections': accepted_connections,
        'intro_quota_remaining': intro_quota_remaining,
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

    founders = Application.objects.discoverable().filter(
        id__in=liked_founder_ids
    ).exclude(review_status='DENIED').select_related('user')

    requested_ids = Connection.objects.filter(investor=investor_profile).values_list('founder_id', flat=True)

    shortlist = []
    for founder in founders:
        # The +10 thumbs-up nudge that used to be applied here is gone.
        # Feedback is a statement about the person, not about the fit, so
        # it must never move the canonical result. It was also redundant:
        # this list is already filtered to founders this investor liked,
        # so the nudge lifted every row equally and ordered nothing.
        result = evaluate_venture_match(founder, investor_profile)

        shortlist.append({
            'founder': founder,
            'match': result,
            'band': result.band.label,
            'already_requested': founder.id in requested_ids,
        })

    shortlist = sorted(
        shortlist, key=lambda x: (x['match'].band, x['match'].score), reverse=True)

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

    log_page_event(request, 'dashboard_view', role='founder', user=request.user)

    if not application.description_vector and founder_description_meets_word_count(application.description):
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

    # Includes FUNDED_PENDING so the founder still sees the deal (with an
    # "awaiting investor confirmation" state instead of the Mark as Funded
    # button) rather than it silently disappearing once claimed.
    accepted_connections = Connection.objects.filter(
        founder=application,
        status__in=['ACCEPTED', 'FUNDED_PENDING']
    ).select_related('investor__user')

    # Privacy Gatekeeper: uses InvestorApplication.objects.discoverable() (is_private=False, not archived)
    investors = InvestorApplication.objects.discoverable().exclude(review_status='DENIED').select_related('user')
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
        # Same evaluation as the investor side sees for this pairing --
        # the contract is symmetric, so the two dashboards can no longer
        # disagree about how well the same founder and investor fit.
        result = evaluate_venture_match(application, investor)

        if result.band > Band.UNRANKED:
            match_results.append({
                'investor': investor,
                'match': result,
                'band': result.band.label,
                'already_requested': investor.id in connection_status_map,
                'connection_status': connection_status_map.get(investor.id),
                'ai_insights': _generate_explanatory_insights(result, application, investor),
            })

    match_results = sorted(
        match_results, key=lambda x: (x['match'].band, x['match'].score), reverse=True)

    from .growth_metrics import get_platform_insights, get_pitch_video_social_signal_insights
    platform_insights = get_platform_insights()
    if application.pitch_video:
        platform_insights = platform_insights + get_pitch_video_social_signal_insights()

    return render(request, 'matchmaking/founder_dashboard.html', {
        'matches': match_results,
        'application': application,
        'pending_requests': pending_requests,
        'accepted_connections': accepted_connections,
        'platform_insights': platform_insights,
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

    # Includes CLOSED_PENDING so the seller still sees the deal (with an
    # "awaiting buyer confirmation" state instead of the Mark as Closed
    # button) rather than it silently disappearing once claimed.
    accepted_connections = AcquisitionConnection.objects.filter(
        seller=seller_profile,
        status__in=['ACCEPTED', 'CLOSED_PENDING']
    ).select_related('buyer__user')

    # Privacy Gatekeeper: uses BuyerApplication.objects.discoverable() (is_private=False, not archived)
    buyers = BuyerApplication.objects.discoverable().exclude(review_status='DENIED').select_related('user')
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
        result = evaluate_deal_match(seller_profile, buyer)

        if result.band > Band.UNRANKED:
            match_results.append({
                'buyer': buyer,
                'match': result,
                'band': result.band.label,
                'already_requested': buyer.id in connection_status_map,
                'connection_status': connection_status_map.get(buyer.id),
                'deal_insights': _generate_deal_explanatory_insights(result, seller_profile, buyer),
            })

    match_results = sorted(
        match_results, key=lambda x: (x['match'].band, x['match'].score), reverse=True)

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

    platform_insights = []
    if seller_profile.pitch_video:
        from .growth_metrics import get_pitch_video_social_signal_insights
        platform_insights = get_pitch_video_social_signal_insights()

    return render(request, 'matchmaking/seller_dashboard.html', {
        'matches': match_results,
        'seller_profile': seller_profile,
        'pending_requests': pending_requests,
        'accepted_connections': accepted_connections,
        'suggested_valuation': suggested_valuation,
        'platform_insights': platform_insights,
        'filters': {
            'structure': filter_structure,
            'min_budget': filter_min_budget,
        },
    })


@login_required
@require_POST
def activate_founder_highlight(request):
    """
    Founder Premium's monthly perk: a 24-hour visibility boost across the
    bulletin board, pitch video listing, blog posts, and job posts (see
    Application.is_highlighted and the sort keys in founder_bulletin_board/
    _rank_pitch_video_profiles/blog.views.blog_view/jobs.views.JobListView).
    Replaces the old "see investor identity in your digest" perk — see
    matchmaking/digest.py's module docstring for why.
    """
    application = getattr(request.user, 'match_founder_profile', None)
    if not application:
        messages.error(request, "Complete your founder profile first.")
        return redirect('matchmaking:founder_dashboard')

    if not application.can_activate_highlight:
        if not application.is_premium:
            messages.error(request, "The monthly highlight is a Founder Premium perk.")
        else:
            messages.error(request, "Your highlight was already used this month — check back after your cooldown ends.")
        return redirect('matchmaking:founder_dashboard')

    application.activate_highlight()
    messages.success(request, "You're highlighted for the next 24 hours across the bulletin board, pitch videos, blog, and jobs.")
    return redirect('matchmaking:founder_dashboard')


@login_required
@require_POST
def activate_seller_highlight(request):
    """Seller Premium's mirror of activate_founder_highlight — see that view's docstring."""
    seller_profile = getattr(request.user, 'match_seller_profile', None)
    if not seller_profile:
        messages.error(request, "Complete your business listing first.")
        return redirect('matchmaking:seller_dashboard')

    if not seller_profile.can_activate_highlight:
        if not seller_profile.is_premium:
            messages.error(request, "The monthly highlight is a Seller Premium perk.")
        else:
            messages.error(request, "Your highlight was already used this month — check back after your cooldown ends.")
        return redirect('matchmaking:seller_dashboard')

    seller_profile.activate_highlight()
    messages.success(request, "You're highlighted for the next 24 hours across the business marketplace and pitch videos.")
    return redirect('matchmaking:seller_dashboard')


FREE_CRM_LEAD_LIMIT = 15


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

    lead_count = leads.count()

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
        'lead_count': lead_count,
        'lead_limit': FREE_CRM_LEAD_LIMIT,
    })


@login_required
@require_POST
def create_lead(request):
    application = getattr(request.user, 'match_founder_profile', None)
    if not application:
        raise Http404("Founder profile required.")

    if not application.is_premium and FundraisingLead.objects.filter(founder=application).count() >= FREE_CRM_LEAD_LIMIT:
        messages.error(request, f"Free tier is limited to {FREE_CRM_LEAD_LIMIT} CRM leads. Upgrade to Founder Premium for unlimited leads.")
        return redirect('matchmaking:fundraising_crm')

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
    if connection.vendor == 'postgresql' and source.description_vector_pg:
        # ANN fast path — hits the HNSW index (migration 0049) instead of the
        # O(n) Python cosine scan below. Pull a slightly larger pool than we
        # need (20) so the score>0.3 filter still has room to work with,
        # since the DB only orders by distance, it doesn't know our threshold.
        from pgvector.django import CosineDistance
        candidates = Application.objects.discoverable().exclude(id=source.id).filter(
            description_vector_pg__isnull=False
        ).exclude(review_status='DENIED').select_related('user').annotate(
            distance=CosineDistance('description_vector_pg', source.description_vector_pg)
        ).order_by('distance')[:20]

        for candidate in candidates:
            score = 1 - candidate.distance  # CosineDistance = 1 - cosine similarity
            if score > 0.3:
                results.append({'application': candidate, 'score': round(score * 100, 1)})
        results = results[:6]
    elif source.description_vector:
        candidates = Application.objects.discoverable().exclude(id=source.id).filter(
            description_vector__isnull=False
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

    for app in Application.objects.filter(review_status='APPROVED', archived_at__isnull=True).order_by('-created_at')[:limit]:
        name = app.company_name if not app.is_private else 'A new founder'
        events.append({
            'icon': 'bi-rocket-takeoff-fill',
            'message': f"{name} joined the network in {app.sector or 'General Tech'}.",
            'timestamp': app.created_at,
        })

    for inv in InvestorApplication.objects.filter(review_status='APPROVED', archived_at__isnull=True).order_by('-created_at')[:limit]:
        name = inv.company_name if not inv.is_private else 'A new investor'
        events.append({
            'icon': 'bi-graph-up-arrow',
            'message': f"{name} joined the network.",
            'timestamp': inv.created_at,
        })

    # 'FUNDED'/'CLOSED' say "Verified" explicitly — same public contract as
    # the profile and bulletin-card badges (see Application.has_verified_funding
    # / SellerApplication.has_verified_sale in matchmaking/models.py). This
    # is presentation only: FUNDED_PENDING/CLOSED_PENDING (the self-reported,
    # unconfirmed claim) fall through to the generic 'A connection was
    # updated' default below, same as before this wording pass.
    connection_labels = {
        'pending': ('bi-hand-index-thumb', 'A new introduction was requested'),
        'ACCEPTED': ('bi-check-circle-fill', 'An introduction was accepted'),
        'FUNDED': ('bi-trophy-fill', 'A deal was Verified Funded'),
    }
    for conn in Connection.objects.select_related('founder', 'investor').order_by('-updated_at')[:limit]:
        icon, label = connection_labels.get(conn.status, ('bi-hand-index-thumb', 'A connection was updated'))
        if not conn.founder.is_private and not conn.investor.is_private:
            label = f"{label}: {conn.investor.company_name} ↔ {conn.founder.company_name}"
        events.append({'icon': icon, 'message': label + '.', 'timestamp': conn.updated_at})

    acquisition_connection_labels = {
        'pending': ('bi-hand-index-thumb', 'A new introduction was requested'),
        'ACCEPTED': ('bi-check-circle-fill', 'An introduction was accepted'),
        'CLOSED': ('bi-trophy-fill', 'A deal was Verified Sold'),
    }
    for conn in AcquisitionConnection.objects.select_related('seller', 'buyer').order_by('-updated_at')[:limit]:
        icon, label = acquisition_connection_labels.get(conn.status, ('bi-hand-index-thumb', 'A connection was updated'))
        if not conn.seller.is_private and not conn.buyer.is_private:
            label = f"{label}: {conn.buyer.company_name} ↔ {conn.seller.company_name}"
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
    pitches_queryset = Application.objects.discoverable().exclude(review_status='DENIED').select_related('user')
    
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
    connection_status_map = {}
    if investor_profile:
        feedback_map = dict(
            MatchFeedback.objects.filter(
                investor=investor_profile, application__in=pitches_queryset
            ).values_list('application_id', 'vote')
        )
        connection_status_map = dict(
            Connection.objects.filter(investor=investor_profile).values_list('founder_id', 'status')
        )

    # Verified Funded badge: same canonical, mutually-confirmed FUNDED status
    # as Application.has_verified_funding/verified_funding_count (see
    # matchmaking.models — never a profile field, claim, or AI inference).
    # Computed as one grouped query for the whole board rather than calling
    # the per-instance property per-card, to avoid N+1.
    from django.db.models import Count
    verified_funded_counts = dict(
        Connection.objects.filter(founder__in=pitches_queryset, status='FUNDED')
        .values('founder_id').annotate(n=Count('id')).values_list('founder_id', 'n')
    )

    pitches = []
    for pitch in pitches_queryset:
        # Hard-filter gate: excluded entirely (not shown, not scored) rather
        # than down-ranked — see passes_hard_filters' docstring. Only
        # applies when an investor is viewing; anonymous/founder visitors
        # see the full public board unaffected.
        if investor_profile and not passes_hard_filters(pitch, investor_profile):
            continue

        # A viewer with no investor profile gets no match at all, rather
        # than the hardcoded 75 that used to stand in for one. An
        # anonymous browser has no mandate, so there is nothing to match
        # against and nothing honest to show.
        ai_insights_data = None
        result = None
        if investor_profile:
            result = evaluate_venture_match(pitch, investor_profile)
            ai_insights_data = _generate_explanatory_insights(result, pitch, investor_profile)

        # The vote is recorded and shown, but it does not touch the band.
        # It used to shift the displayed number by +/-10, which made a
        # personal opinion look like a property of the pairing.
        pitch.investor_vote = feedback_map.get(pitch.id) or 0
        pitch.match = result
        pitch.band = result.band.label if result else None
        pitch.ai_insights = ai_insights_data
        pitch.connection_status = connection_status_map.get(pitch.id)
        pitch.already_requested = pitch.id in connection_status_map
        pitch.verified_funded_count = verified_funded_counts.get(pitch.id, 0)
        pitch.has_verified_funded = pitch.verified_funded_count > 0
        pitches.append(pitch)
        
    # Founder Premium perk (or a staff-curated feature): Featured Placement —
    # featured founders sort first, then by band within each group. An
    # active monthly
    # highlight (see Application.is_highlighted) outranks plain Featured
    # Placement — it's the stronger, time-boxed signal.
    # Featured placement first, then band, then the internal score within
    # a band. A viewer with no mandate has no match to sort on, so those
    # rows fall back to a stable neutral position rather than to a
    # fabricated default.
    pitches = sorted(pitches, key=lambda x: (
        not x.is_highlighted,
        not (x.is_premium or x.is_staff_featured),
        -(x.match.band if x.match else 0),
        -(x.match.score if x.match else 0),
    ))

    return render(request, 'matchmaking/bulletin_board.html', {
        'pitches': pitches,
        'selected_sector': selected_sector,
        'pulse_events': get_foundry_pulse_events(),
        'investor_profile': investor_profile,
    })


def acquisition_bulletin_board(request):
    """
    Public browse page for the Business Marketplace — mirrors
    founder_bulletin_board, but for businesses-for-sale matched against
    deal economics rather than sector/stage. Kept as its own view (not
    merged into the founder bulletin board) since the two marketplaces
    have different privacy and matching rules.
    """
    listings_queryset = SellerApplication.objects.discoverable().exclude(review_status='DENIED').select_related('user')

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
    connection_status_map = {}
    if buyer_profile:
        feedback_map = dict(
            DealFeedback.objects.filter(
                buyer=buyer_profile, seller__in=listings_queryset
            ).values_list('seller_id', 'vote')
        )
        connection_status_map = dict(
            AcquisitionConnection.objects.filter(buyer=buyer_profile).values_list('seller_id', 'status')
        )

    # Verified Sold badge — same canonical, mutually-confirmed CLOSED status
    # as SellerApplication.has_verified_sale/verified_sale_count (see
    # matchmaking.models); grouped query mirrors verified_funded_counts in
    # founder_bulletin_board.
    from django.db.models import Count
    verified_sold_counts = dict(
        AcquisitionConnection.objects.filter(seller__in=listings_queryset, status='CLOSED')
        .values('seller_id').annotate(n=Count('id')).values_list('seller_id', 'n')
    )

    listings = []
    for listing in listings_queryset:
        # Mirrors founder_bulletin_board: no mandate, no match, and no
        # hardcoded 75 standing in for one.
        deal_insights_data = None
        result = None
        if buyer_profile:
            result = evaluate_deal_match(listing, buyer_profile)
            deal_insights_data = _generate_deal_explanatory_insights(result, listing, buyer_profile)

        listing.buyer_vote = feedback_map.get(listing.id) or 0
        listing.match = result
        listing.band = result.band.label if result else None
        listing.deal_insights = deal_insights_data
        listing.connection_status = connection_status_map.get(listing.id)
        listing.already_requested = listing.id in connection_status_map
        listing.verified_sold_count = verified_sold_counts.get(listing.id, 0)
        listing.has_verified_sold = listing.verified_sold_count > 0
        listings.append(listing)

    # Seller Premium perk (or a staff-curated feature): Featured Listing —
    # featured sellers sort first, then by match score within each group
    # (mirrors founder_bulletin_board's Featured Placement — see that view
    # for the same pattern). An active monthly highlight outranks plain
    # Featured Listing, same as the founder side.
    listings = sorted(listings, key=lambda x: (
        not x.is_highlighted,
        not (x.is_premium or x.is_staff_featured),
        -(x.match.band if x.match else 0),
        -(x.match.score if x.match else 0),
    ))

    return render(request, 'matchmaking/acquisition_bulletin_board.html', {
        'listings': listings,
        'selected_industry': selected_industry,
        'buyer_profile': buyer_profile,
    })


# ==========================================
# INTERACTION & TRANSACTION HANDLERS
# ==========================================

DAILY_INTRO_REQUEST_LIMIT = 3


def count_investor_intro_requests_today(investor_profile):
    """Non-premium investors are capped at DAILY_INTRO_REQUEST_LIMIT investor-initiated
    intro requests per rolling 24h — shared by the rate-limit check in request_intro
    and the proactive quota display on investor_dashboard."""
    return Connection.objects.filter(
        investor=investor_profile,
        initiated_by='INVESTOR',
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).count()


def count_buyer_intro_requests_today(buyer_profile):
    """Buyer-side equivalent of count_investor_intro_requests_today."""
    return AcquisitionConnection.objects.filter(
        buyer=buyer_profile,
        initiated_by='BUYER',
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).count()


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
        daily_count = count_investor_intro_requests_today(investor_profile)
        if daily_count >= DAILY_INTRO_REQUEST_LIMIT:
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

        # Admin-facing FYI only — this goes to ADMIN_EMAIL, not to the
        # founder or investor (the founder's own accurate in-app
        # Notification is created above). connection_action_view is a
        # direct two-party accept/decline with no staff step, so this
        # copy previously implied a manual approval that never happens —
        # fixed to describe what actually happens instead.
        subject = f"Intro request: {investor_profile.company_name or 'Private Investor'} -> {founder_app.company_name}"
        email_body = (
            f"New introduction request:\n\n"
            f"Investor: {getattr(investor_profile, 'full_name', 'Anonymous Portfolio Manager')} ({investor_profile.company_name or 'Private Partner'})\n"
            f"Founder: {founder_app.company_name}\n\n"
            f"Mandate Target Stage: {investor_profile.investment_stage}\n\n"
            f"No action needed — the founder can accept or decline this directly from their dashboard."
        )

        # `getattr(settings, 'ADMIN_EMAIL', DEFAULT_FROM_EMAIL)` never
        # actually falls back: ADMIN_EMAIL is always a defined setting
        # (django-environ defaults it to ''), so getattr's default only
        # kicks in when an attribute is *missing*, not when it's falsy.
        # With ADMIN_EMAIL unset, recipient_list ends up as [''], and
        # EmailMessage.recipients() silently filters out falsy addresses —
        # so this email has been failing to send with no error at all
        # whenever ADMIN_EMAIL isn't configured. `or` actually falls back.
        send_mail(
            subject=subject,
            message=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_EMAIL or settings.DEFAULT_FROM_EMAIL],
            fail_silently=True
        )
        messages.success(request, f"Intro request sent for {founder_app.company_name}!")
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
        daily_count = count_buyer_intro_requests_today(buyer_profile)
        if daily_count >= DAILY_INTRO_REQUEST_LIMIT:
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
    log_training_example(
        'INVESTOR', investor_profile.id, 'FOUNDER', founder_app.id,
        'POSITIVE' if numerical_vote == 1 else 'NEGATIVE',
        'thumbs_up' if numerical_vote == 1 else 'thumbs_down',
    )

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
    log_training_example(
        'BUYER', buyer_profile.id, 'SELLER', seller_app.id,
        'POSITIVE' if numerical_vote == 1 else 'NEGATIVE',
        'thumbs_up' if numerical_vote == 1 else 'thumbs_down',
    )

    if is_json:
        return JsonResponse({'status': 'success'})

    messages.success(request, "Feedback recorded. We're tuning your algorithm!")
    return redirect(request.META.get('HTTP_REFERER', 'matchmaking:buyer_dashboard'))


@login_required
def initiate_direct_chat(request, target_user_id):
    """
    Creates (or resolves) the deterministic chat_<sorted numeric ids>
    channel between request.user and target_user_id, same scheme
    whichever party initiates. Existing callers (the profile page's
    plain "Message" link) get the original full-page redirect; an AJAX
    caller (the content-share picker, which needs the channel_id without
    navigating away — see matchmaking/static/js/matchmaking.js's
    ContentShare) gets JSON instead. NOT the same channel-id scheme as
    createDealRoom's deal_<sorted string ids> — this is the plain-DM
    channel, deal_ is reserved for a specific accepted Connection.
    """
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    target_user = get_object_or_404(User, id=target_user_id)
    current_user_id = str(request.user.id)
    target_id_str = str(target_user.id)

    if current_user_id == target_id_str:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': "You can't message yourself."}, status=400)
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

    # "Profiles messaged" tracking — Stream Chat holds the actual messages
    # (external), so this is the local proxy: one row per unique pair,
    # regardless of role combo, get-or-created every time a channel exists.
    MessageThread.log_thread(request.user, target_user)

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

    if is_ajax:
        return JsonResponse({'status': 'success', 'channel_id': channel_id})
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
    queryset = Application.objects.discoverable().select_related('user').exclude(review_status='DENIED')

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

    non_empty_filters = {k: v for k, v in filters.items() if v}
    if non_empty_filters:
        query_summary = '; '.join(f"{k}={v}" for k, v in non_empty_filters.items())
        log_search_event(request, 'filter_search', query_summary)

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
            app.team_size,
            app.years_in_business,
            app.company_website,
        ])

    return response


@login_required
def export_acquisition_csv(request):
    """
    Premium-gated CSV export of the current Business Marketplace search
    result set — Buyer Premium's mirror of export_search_csv. Same filters
    as acquisition_bulletin_board (industry, q), same privacy rules.
    """
    buyer_profile = getattr(request.user, 'match_buyer_profile', None)
    if not buyer_profile or not buyer_profile.is_premium:
        messages.error(request, "CSV export is a premium buyer feature. Upgrade your account to unlock listing exports.")
        query_string = request.GET.urlencode()
        redirect_url = reverse('matchmaking:acquisition_bulletin_board')
        if query_string:
            redirect_url = f"{redirect_url}?{query_string}"
        return redirect(redirect_url)

    queryset = SellerApplication.objects.discoverable().exclude(review_status='DENIED')

    selected_industry = request.GET.get('industry', '').strip()
    search_query = request.GET.get('q', '').strip()
    if selected_industry:
        queryset = queryset.filter(industry__iexact=selected_industry)
    if search_query:
        queryset = queryset.filter(
            Q(company_name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(industry__icontains=search_query) |
            Q(extra_info__icontains=search_query)
        )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="interlink_foundry_acquisitions_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Company Name', 'Industry', 'Location', 'Asking Price',
        'Annual Revenue', 'EBITDA', 'Deal Structure', 'Years in Business', 'Website',
    ])
    for listing in queryset:
        writer.writerow([
            listing.company_name,
            listing.industry,
            listing.geography,
            listing.asking_price,
            listing.annual_revenue,
            listing.ebitda,
            listing.get_deal_structure_display(),
            listing.years_in_business,
            listing.company_website,
        ])

    return response


@login_required
def seller_interest_analytics(request):
    """
    Seller Premium perk: detailed buyer-interest analytics for a seller's own
    listing — an event-count breakdown plus a recent-activity feed, both
    sourced from AcquisitionInterestEvent (silently logged on every buyer
    interaction already). Mirrors deck_analytics' role as a premium
    visibility upgrade on top of data that was already being collected.
    """
    seller_profile = getattr(request.user, 'match_seller_profile', None)
    if not seller_profile:
        messages.info(request, "Complete your business listing first.")
        return redirect('usersettings:edit_seller_profile')

    if not seller_profile.is_premium:
        messages.error(request, "Interest analytics is a Seller Premium feature. Upgrade to see who's engaging with your listing.")
        return redirect('matchmaking:seller_dashboard')

    from django.db.models import Count

    events = AcquisitionInterestEvent.objects.filter(seller=seller_profile).select_related('buyer')

    event_counts = {
        row['event_type']: row['count']
        for row in events.values('event_type').annotate(count=Count('id'))
    }
    event_labels = dict(AcquisitionInterestEvent.EVENT_TYPES)
    event_summary = [
        {'type': event_type, 'label': event_labels.get(event_type, event_type), 'count': event_counts.get(event_type, 0)}
        for event_type, _ in AcquisitionInterestEvent.EVENT_TYPES
    ]

    recent_events = events.order_by('-created_at')[:50]

    return render(request, 'matchmaking/seller_interest_analytics.html', {
        'seller_profile': seller_profile,
        'event_summary': event_summary,
        'recent_events': recent_events,
    })


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

    # Full activation funnel (all 4 personas) + Zelda feature-usage breakdown —
    # see matchmaking/analytics.py for how each stage is computed.
    from .analytics import get_founder_investor_funnel, get_seller_buyer_funnel, get_zelda_feature_usage
    founder_investor_funnel = get_founder_investor_funnel()
    seller_buyer_funnel = get_seller_buyer_funnel()
    zelda_feature_usage = get_zelda_feature_usage()
    funnel_tables = [
        ('founder', 'Founder', founder_investor_funnel['founder']),
        ('investor', 'Investor', founder_investor_funnel['investor']),
        ('seller', 'Seller', seller_buyer_funnel['seller']),
        ('buyer', 'Buyer', seller_buyer_funnel['buyer']),
    ]

    # Acquisition / Activation / Engagement / Value Creation / Feature
    # Adoption tabs — see matchmaking/growth_metrics.py for how each is computed.
    from . import growth_metrics
    acquisition_metrics = growth_metrics.get_acquisition_metrics()
    activation_metrics = growth_metrics.get_activation_metrics()
    engagement_metrics = growth_metrics.get_engagement_metrics()
    value_creation_metrics = growth_metrics.get_value_creation_metrics()
    feature_adoption_metrics = growth_metrics.get_feature_adoption_metrics()
    time_to_value_metrics = growth_metrics.get_time_to_value_metrics()
    conversation_speed_retention = growth_metrics.get_conversation_speed_retention_insight()
    marketplace_liquidity = growth_metrics.get_marketplace_liquidity_funnel()

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
        'founder_investor_funnel': founder_investor_funnel,
        'seller_buyer_funnel': seller_buyer_funnel,
        'zelda_feature_usage': zelda_feature_usage,
        'funnel_tables': funnel_tables,
        'acquisition_metrics': acquisition_metrics,
        'activation_metrics': activation_metrics,
        'engagement_metrics': engagement_metrics,
        'value_creation_metrics': value_creation_metrics,
        'feature_adoption_metrics': feature_adoption_metrics,
        'time_to_value_metrics': time_to_value_metrics,
        'conversation_speed_retention': conversation_speed_retention,
        'marketplace_liquidity': marketplace_liquidity,
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
    The Zelda Intelligence Report — the 30-second orientation layer.

    It answers, fast: what is this company, why did it surface for this
    investor, what did Zelda notice, and where to look next. The deep
    analysis — thesis, scenarios, recommendation, the full
    problem/market/team/financial/risk write-ups — is the IC Memo's job;
    this page never reproduces it.

    Everything here is a re-presentation of data the platform already
    produced: the founder's IntelligenceMemo, the Truth Delta report, the
    Application fields, and (for a logged-in investor) the match signal.
    Nothing is generated or recomputed. When the real data isn't there,
    the page says so.
    """
    from django.urls import reverse
    from zelda_api.disclaimers import DUE_DILIGENCE_DISCLAIMER
    from zelda_api.ic_memo import (
        latest_analyzed_pitch_deck_and_memo, truth_delta_signal,
        zelda_report_observations, can_view_ic_memo,
    )
    from zelda_api.report_nav import build_report_nav, OVERVIEW as REPORT_OVERVIEW
    from zelda_api.vector_models import DocumentSource

    formatted_name = company_slug.replace('-', ' ')
    founder_app = get_object_or_404(Application, company_name__iexact=formatted_name)

    # Access: investor profile or staff only (unchanged).
    investor_profile = getattr(request.user, 'match_investor_profile', None)
    if not investor_profile and not request.user.is_staff:
        raise PermissionDenied("Access to proprietary asset intelligence reports is restricted.")

    # Zelda Lite / Zelda AI split — gated on the FOUNDER's own Premium
    # (their report to unlock for viewing investors), staff bypass for
    # support (unchanged).
    memo_tier = 'full' if (request.user.is_staff or founder_app.is_premium) else 'lite'

    # --- Real intelligence data ---------------------------------------
    pitch_deck_doc, memo = latest_analyzed_pitch_deck_and_memo(founder_app.user)

    # "Processing" means a deck is genuinely in the pipeline but hasn't
    # produced an analyzed memo yet — not a cache miss.
    analysis_pending = memo is None and (
        DocumentSource.objects
        .filter(uploaded_by=founder_app.user, document_type='pitch_deck')
        .exclude(status__in=['analyzed', 'error'])
        .exists()
    )

    overview_text = (memo.executive_summary if memo and memo.executive_summary
                     else founder_app.description)

    truth_delta = truth_delta_signal(pitch_deck_doc)

    # "What Zelda noticed" / "Worth investigating" — deterministic synthesis
    # of the memo + Truth Delta data, full tier only. Either list comes
    # back empty when the data can't support a real observation, and the
    # template then omits that section.
    observations = {'noticed': [], 'worth_investigating': []}
    if memo_tier == 'full' and memo is not None:
        observations = zelda_report_observations(memo, pitch_deck_doc)

    # The funnel: only offer the IC Memo when this viewer can actually open
    # it; otherwise point them at the connection that unlocks it.
    can_ic_memo = bool(pitch_deck_doc) and can_view_ic_memo(request.user, founder_app)
    ic_memo_url = (reverse('zelda_api:ic_memo', args=[pitch_deck_doc.id])
                   if (pitch_deck_doc and memo is not None) else None)
    truth_delta_url = (reverse('zelda_api:truth_delta_ui', args=[pitch_deck_doc.id])
                       if pitch_deck_doc else None)
    for item in observations['worth_investigating']:
        if item['target'] == 'ic_memo':
            item['url'] = ic_memo_url if can_ic_memo else None
        elif item['target'] == 'truth_delta':
            item['url'] = truth_delta_url
        else:
            item['url'] = None

    # --- Why Zelda surfaced this (investor + match vectors only) ------
    # The plain-language sector / stage / overall-fit signals. The raw
    # match percentage is deliberately NOT surfaced on this report — it's
    # a fourth quasi-score the orientation layer doesn't need. The
    # calculation is untouched; other surfaces still use it.
    ai_insights_data = None
    if investor_profile:
        ai_insights_data = _generate_explanatory_insights(
            evaluate_venture_match(founder_app, investor_profile), founder_app, investor_profile)

    # The deal room is only a real destination once there's an accepted
    # connection — otherwise the button dropped an investor into an empty
    # generic chat shell for a company they aren't connected to.
    has_deal_room = bool(investor_profile) and Connection.objects.filter(
        investor=investor_profile, founder=founder_app, status='ACCEPTED',
    ).exists()

    context = {
        'founder_app': founder_app,
        'memo_tier': memo_tier,
        'has_analysis': memo is not None,
        'analysis_pending': analysis_pending,
        'overview_text': overview_text,
        'truth_delta': truth_delta,
        'truth_delta_url': truth_delta_url,
        'observations': observations,
        'ai_insights': ai_insights_data,
        'investor': investor_profile,
        'can_view_ic_memo': can_ic_memo,
        'ic_memo_url': ic_memo_url,
        'has_deal_room': has_deal_room,
        'report_nav': build_report_nav(request.user, founder_app.user, REPORT_OVERVIEW),
        'disclaimer': DUE_DILIGENCE_DISCLAIMER,
    }

    return render(request, 'matchmaking/memo_detail.html', context)

def _can_view_pitch_deck(request, application):
    """Same privacy rule as the profile page: private decks are owner/staff-only.
    A staff-hidden deck (under review) is also owner/staff-only, regardless
    of the is_private setting."""
    if request.user == application.user or request.user.is_staff:
        return True
    if application.is_hidden_by_staff:
        return False
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
@require_POST
def record_video_telemetry(request, application_id):
    """
    Ingests navigator.sendBeacon() payloads from the pitch video player —
    same beacon-with-CSRF-as-form-field pattern as record_deck_telemetry.
    Video has one linear timeline (not per-slide), so this tracks the
    furthest playback position reached per session directly, rather than
    accumulating incremental deltas the way slide time does.
    Skips silently for the founder previewing their own video.
    """
    application = get_object_or_404(Application, id=application_id)
    if request.user == application.user:
        return JsonResponse({'status': 'skipped'})

    try:
        payload = json.loads(request.POST.get('payload', '{}'))
        client_session_id = payload.get('client_session_id', '')[:64]
        watched_seconds = float(payload.get('watched_seconds', 0))
        video_duration_seconds = float(payload.get('video_duration_seconds', 0))

        if not client_session_id or video_duration_seconds <= 0:
            return JsonResponse({'status': 'error', 'message': 'Missing data'}, status=400)

        session, created = PitchVideoView.objects.get_or_create(
            founder=application,
            viewer=request.user,
            client_session_id=client_session_id,
            defaults={
                'video_duration_seconds': video_duration_seconds,
                'max_watched_seconds': watched_seconds,
            },
        )
        if not created:
            from django.db.models.functions import Greatest
            from django.db.models import Value
            PitchVideoView.objects.filter(pk=session.pk).update(
                max_watched_seconds=Greatest('max_watched_seconds', Value(watched_seconds)),
                video_duration_seconds=video_duration_seconds,
            )

        return JsonResponse({'status': 'success'})
    except Exception as e:
        logger.warning(f"Video telemetry ingestion failed: {str(e)}")
        return JsonResponse({'status': 'error'}, status=400)


@login_required
def data_room(request, username):
    """
    Founder due-diligence document room. Titles/categories are visible to
    any connected investor (can_view_data_room), but downloading a specific
    file needs the founder's per-document approval (DataRoomAccessRequest) —
    so the owner/staff view shows all documents plus pending requests to
    decide on, while an investor view shows a per-document status instead.
    """
    founder_application = get_object_or_404(Application, user__username=username)
    if not can_view_data_room(request.user, founder_application):
        raise Http404("Access Denied")

    is_owner_or_staff = request.user == founder_application.user or request.user.is_staff
    documents = list(founder_application.data_room_documents.all())

    pending_requests = []
    pending_information_requests = []
    category_request_status = []
    if is_owner_or_staff:
        pending_requests = DataRoomAccessRequest.objects.filter(
            document__founder=founder_application, status='PENDING'
        ).select_related('document', 'investor__user')
        pending_information_requests = DataRoomInformationRequest.objects.filter(
            founder=founder_application, status='PENDING'
        ).select_related('investor__user')
    else:
        investor_profile = getattr(request.user, 'match_investor_profile', None)
        my_requests = {
            r.document_id: r for r in DataRoomAccessRequest.objects.filter(
                investor=investor_profile, document__founder=founder_application
            )
        } if investor_profile else {}
        for document in documents:
            document.my_request = my_requests.get(document.id)
            # MATCH_ONLY documents skip the request/approval workflow —
            # already downloadable to anyone allowed in the room at all.
            document.can_download_directly = document.visibility == 'MATCH_ONLY'

        # "Request Information" — structured request for a category the
        # founder hasn't uploaded anything for yet (see
        # DataRoomInformationRequest's docstring). Excludes 'OTHER' since
        # that's a catch-all, not a specific ask an investor would name.
        if investor_profile:
            my_info_requests = {
                r.category: r for r in DataRoomInformationRequest.objects.filter(
                    founder=founder_application, investor=investor_profile
                )
            }
            category_request_status = [
                (value, label, my_info_requests.get(value))
                for value, label in DataRoomDocument.CATEGORY_CHOICES if value != 'OTHER'
            ]

    return render(request, 'matchmaking/data_room.html', {
        'founder_application': founder_application,
        'documents': documents,
        'is_owner_or_staff': is_owner_or_staff,
        'pending_requests': pending_requests,
        'pending_information_requests': pending_information_requests,
        'category_request_status': category_request_status,
        'category_choices': DataRoomDocument.CATEGORY_CHOICES,
        'visibility_choices': DataRoomDocument.VISIBILITY_CHOICES,
    })


@login_required
@require_POST
def data_room_upload(request, username):
    founder_application = get_object_or_404(Application, user__username=username)
    if not (request.user == founder_application.user or request.user.is_staff):
        raise PermissionDenied

    form = DataRoomDocumentForm(request.POST, request.FILES)
    if form.is_valid():
        document = form.save(commit=False)
        document.founder = founder_application
        if not document.visibility:
            document.visibility = 'INVESTOR_APPROVED'
        document.save()
        messages.success(request, f'"{document.label}" uploaded to the data room.')

        # Uploading a document satisfies any investor's outstanding
        # "please provide X" request for that same category — the founder
        # doesn't have to separately act on each one. This only marks the
        # category as covered; the investor still needs a normal
        # DataRoomAccessRequest (approved separately) to download this file.
        fulfilled_requests = DataRoomInformationRequest.objects.filter(
            founder=founder_application, category=document.category, status='PENDING'
        ).select_related('investor__user')
        if fulfilled_requests:
            from notifications.models import Notification
            for info_request in fulfilled_requests:
                info_request.status = 'FULFILLED'
                info_request.decided_at = timezone.now()
                info_request.fulfilled_document = document
                info_request.save(update_fields=['status', 'decided_at', 'fulfilled_document'])
                Notification.objects.create(
                    recipient=info_request.investor.user, sender=request.user, notification_type='DATA_ROOM_INFO_FULFILLED',
                    message=f"{founder_application.company_name} uploaded {document.get_category_display()} — your request has been fulfilled.",
                    target_url=reverse('matchmaking:data_room', kwargs={'username': username}),
                )
    else:
        error_text = ' '.join(str(e) for errors in form.errors.values() for e in errors)
        messages.error(request, error_text or "Upload failed.")

    return redirect('matchmaking:data_room', username=username)


@login_required
@require_POST
def data_room_delete(request, document_id):
    document = get_object_or_404(DataRoomDocument, id=document_id)
    if not (request.user == document.founder.user or request.user.is_staff):
        raise PermissionDenied

    label = document.label
    username = document.founder.user.username
    document.delete()
    messages.success(request, f'"{label}" deleted.')
    return redirect('matchmaking:data_room', username=username)


@login_required
@require_POST
def data_room_request_access(request, document_id):
    document = get_object_or_404(DataRoomDocument, id=document_id)
    if not can_view_data_room(request.user, document.founder):
        raise Http404("Access Denied")

    investor_profile = getattr(request.user, 'match_investor_profile', None)
    if not investor_profile or request.user == document.founder.user:
        raise PermissionDenied

    # MATCH_ONLY documents skip the approval workflow entirely — being
    # allowed into the room already grants download (see
    # can_download_data_room_document) — so there's nothing to request.
    if document.visibility == 'MATCH_ONLY':
        messages.info(request, f'"{document.label}" doesn\'t require a request — download it directly.')
        return redirect('matchmaking:data_room', username=document.founder.user.username)

    nda_accepted = request.POST.get('nda_accepted') == 'on'
    if document.visibility == 'NDA_REQUIRED' and not nda_accepted:
        messages.error(request, f'You must acknowledge the NDA to request "{document.label}".')
        return redirect('matchmaking:data_room', username=document.founder.user.username)

    access_request, created = DataRoomAccessRequest.objects.get_or_create(
        document=document, investor=investor_profile,
        defaults={'nda_accepted': nda_accepted},
    )
    if not created:
        update_fields = []
        if access_request.status == 'DENIED':
            access_request.status = 'PENDING'
            access_request.decided_at = None
            update_fields += ['status', 'decided_at']
        if nda_accepted and not access_request.nda_accepted:
            access_request.nda_accepted = True
            update_fields.append('nda_accepted')
        if update_fields:
            access_request.save(update_fields=update_fields)

    messages.success(request, f'Requested access to "{document.label}".')
    return redirect('matchmaking:data_room', username=document.founder.user.username)


@login_required
@require_POST
def data_room_decide_request(request, request_id):
    access_request = get_object_or_404(DataRoomAccessRequest, id=request_id)
    founder_application = access_request.document.founder
    if not (request.user == founder_application.user or request.user.is_staff):
        raise PermissionDenied

    decision = request.POST.get('decision')
    if decision not in ('APPROVE', 'DENY'):
        messages.error(request, "Invalid decision.")
        return redirect('matchmaking:data_room', username=founder_application.user.username)

    access_request.status = 'APPROVED' if decision == 'APPROVE' else 'DENIED'
    access_request.decided_at = timezone.now()
    access_request.save(update_fields=['status', 'decided_at'])
    messages.success(request, f"Request {'approved' if decision == 'APPROVE' else 'denied'}.")
    return redirect('matchmaking:data_room', username=founder_application.user.username)


@login_required
@require_POST
def data_room_request_information(request, username):
    """Structured "please provide X" request for a category the founder
    hasn't uploaded anything for yet — see DataRoomInformationRequest's
    docstring. Distinct from data_room_request_access, which asks for
    access to a document that already exists."""
    founder_application = get_object_or_404(Application, user__username=username)
    if not can_view_data_room(request.user, founder_application):
        raise Http404("Access Denied")

    investor_profile = getattr(request.user, 'match_investor_profile', None)
    if not investor_profile or request.user == founder_application.user:
        raise PermissionDenied

    valid_categories = {value for value, _ in DataRoomDocument.CATEGORY_CHOICES if value != 'OTHER'}
    requested_categories = [c for c in request.POST.getlist('categories') if c in valid_categories]
    if not requested_categories:
        messages.error(request, "Select at least one category to request.")
        return redirect('matchmaking:data_room', username=username)

    requested_labels = []
    for category in requested_categories:
        info_request, created = DataRoomInformationRequest.objects.get_or_create(
            founder=founder_application, investor=investor_profile, category=category,
        )
        if not created and info_request.status != 'PENDING':
            info_request.status = 'PENDING'
            info_request.decided_at = None
            info_request.fulfilled_document = None
            info_request.save(update_fields=['status', 'decided_at', 'fulfilled_document'])
        requested_labels.append(info_request.get_category_display())

    from notifications.models import Notification
    Notification.objects.create(
        recipient=founder_application.user, sender=request.user, notification_type='DATA_ROOM_INFO_REQUEST',
        message=f"{investor_profile.company_name} requested: {', '.join(requested_labels)}.",
        target_url=reverse('matchmaking:data_room', kwargs={'username': username}),
    )
    messages.success(request, f"Requested: {', '.join(requested_labels)}.")
    return redirect('matchmaking:data_room', username=username)


@login_required
@require_POST
def data_room_decline_information_request(request, request_id):
    info_request = get_object_or_404(DataRoomInformationRequest, id=request_id)
    founder_application = info_request.founder
    if not (request.user == founder_application.user or request.user.is_staff):
        raise PermissionDenied
    if info_request.status != 'PENDING':
        messages.error(request, "This request has already been resolved.")
        return redirect('matchmaking:data_room', username=founder_application.user.username)

    info_request.status = 'DECLINED'
    info_request.decided_at = timezone.now()
    info_request.save(update_fields=['status', 'decided_at'])

    from notifications.models import Notification
    Notification.objects.create(
        recipient=info_request.investor.user, sender=request.user, notification_type='DATA_ROOM_INFO_DECLINED',
        message=f"{founder_application.company_name} declined your request for {info_request.get_category_display()}.",
        target_url=reverse('matchmaking:data_room', kwargs={'username': founder_application.user.username}),
    )
    messages.success(request, "Request declined.")
    return redirect('matchmaking:data_room', username=founder_application.user.username)


@login_required
def data_room_document_serve(request, document_id):
    """Never link document.file.url directly — in local FileSystemStorage
    dev mode that's an unauthenticated, guessable /media/... path. This
    view is the only authorized way to get the actual file bytes."""
    document = get_object_or_404(DataRoomDocument, id=document_id)
    if not can_download_data_room_document(request.user, document):
        raise Http404("Access Denied")

    DataRoomDocumentView.objects.create(document=document, viewer=request.user)
    filename = document.file.name.rsplit('/', 1)[-1]
    return FileResponse(document.file.open('rb'), as_attachment=True, filename=filename)


@login_required
@require_POST
def record_profile_duration(request, username):
    """
    Ingests navigator.sendBeacon() payloads reporting time-on-page for a
    profile visit, matched back to the ProfileView row accounts.views.profile()
    created when the page first loaded (same viewer+viewed_user+session_key).
    """
    viewed_user = get_object_or_404(User, username=username)
    if request.user == viewed_user:
        return JsonResponse({'status': 'skipped'})

    try:
        payload = json.loads(request.POST.get('payload', '{}'))
        duration_seconds = float(payload.get('duration_seconds', 0))
        session_key = request.session.session_key or ''

        if duration_seconds <= 0:
            return JsonResponse({'status': 'error', 'message': 'Missing data'}, status=400)

        row = ProfileView.objects.filter(
            viewed_user=viewed_user, viewer=request.user, session_key=session_key,
        ).order_by('-created_at').first()
        if row:
            row.duration_seconds = duration_seconds
            row.save(update_fields=['duration_seconds'])

        return JsonResponse({'status': 'success'})
    except Exception as e:
        logger.warning(f"Profile duration ingestion failed: {str(e)}")
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
        elif conn.status == 'FUNDED_PENDING' or conn.needs_attention:
            # FUNDED_PENDING means the founder claimed this deal closed and
            # is waiting on this investor to confirm/deny — always actionable
            # regardless of the investor's own manual needs_attention flag.
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


def _get_deal_zelda_summary(company_application):
    """
    Read-only Zelda intelligence summary for the Deal Room — never
    generates or refreshes anything, only reads whatever already exists.
    Works for either side of the marketplace: company_application is the
    founder's Application on an investment deal, the seller's
    SellerApplication on an acquisition deal — completion_percentage is
    computed via insights_engine._completion_percentage, which already
    handles both (SellerApplication has no such property of its own).
    Safe to show to anyone who reaches the Deal Room at all: being a party
    to an ACCEPTED relationship with this company already satisfies
    zelda_api.ic_memo.can_view_ic_memo's gate for a founder, and everything
    surfaced here (a completion %, a recommendation, a score) is at or
    below what that Lite-tier preview already discloses.
    """
    from zelda_api.vector_models import IntelligenceMemo
    from zelda_api.truth_delta_models import TruthDeltaReport
    from matchmaking.insights_engine import _completion_percentage

    company_user = company_application.user
    latest_memo = IntelligenceMemo.objects.filter(
        document__uploaded_by=company_user
    ).select_related('document').order_by('-updated_at').first()
    latest_truth_delta = TruthDeltaReport.objects.filter(
        document__uploaded_by=company_user
    ).order_by('-created_at').first()

    return {
        'completion_percentage': _completion_percentage(company_application),
        'latest_memo': latest_memo,
        'latest_truth_delta': latest_truth_delta,
    }


def _stream_deal_channel_id(user_id_a, user_id_b):
    """
    Same deterministic id StreamChatController.createDealRoom() computes
    client-side (matchmaking/static/js/matchmaking.js) the moment EITHER
    a Connection or an AcquisitionConnection is accepted — both dashboards'
    updateConnection()/updateAcquisitionConnection() call the identical JS
    function, so one formula covers both deal types. Reused here, not
    recreated, so "Open Chat" always opens the real channel Stream already
    has for this pair rather than standing up a second, competing one.
    sorted() on strings is lexicographic, matching JS's default
    Array.sort() exactly (NOT numeric — e.g. "10" sorts before "9" — but
    both sides only need to agree with each other, not with numeric
    ordering).
    """
    member_ids = sorted([str(user_id_a), str(user_id_b)])
    return f"deal_{member_ids[0]}_{member_ids[1]}"


@login_required
def deal_workspace_view(request, connection_id):
    """
    Deal Room for one Investor<->Founder relationship. Deliberately owns
    nothing: composes the existing Stream Chat channel, the existing
    founder Data Room, and existing read-only Zelda reports, plus a
    relationship-scoped activity timeline (matchmaking/deal_activity.py).
    See can_view_deal_workspace's docstring for the access gate. Shares
    templates/matchmaking/deal_workspace.html with
    acquisition_deal_workspace_view below — same presentation, deal_type
    tells the template which terminology/sections apply.
    """
    connection = get_object_or_404(Connection, id=connection_id)
    if not can_view_deal_workspace(request.user, connection):
        raise Http404("Access Denied")

    founder_application = connection.founder
    investor_application = connection.investor

    # can_view_deal_workspace is deliberately BROADER than can_view_data_room
    # — it admits FUNDED_PENDING/FUNDED too, so the Deal Room stays
    # reachable to review a deal's history after it closes, whereas
    # can_view_data_room grants an investor access only while status is
    # exactly 'ACCEPTED'. That gap means "allowed into the Deal Room" must
    # NEVER be treated as "allowed to see the Data Room's contents" — this
    # re-checks the Data Room's own authoritative gate explicitly, so a
    # founded/pending-funded investor never sees document titles here that
    # the real Data Room page would 404 them on. The presentation is
    # shared; this authorization check is not.
    data_room_accessible = can_view_data_room(request.user, founder_application)

    # Same reasoning applies to the activity timeline as to the document
    # list above: 'document'-category events (uploads, views, requests,
    # decisions) disclose Data Room titles, so they're withheld the moment
    # data_room_accessible is False — never let a wider Deal Room gate
    # leak Data Room-specific information through a different panel.
    # 'relationship'/'verified_outcome'/'engagement' events are unaffected
    # (the pitch deck has its own, separate, looser viewing gate).
    activity = get_deal_activity_timeline(connection)
    if not data_room_accessible:
        activity = [event for event in activity if event['category'] != 'document']

    return render(request, 'matchmaking/deal_workspace.html', {
        'deal_type': 'investment',
        'connection': connection,
        'company_application': founder_application,
        'counterparty_application': investor_application,
        'company_label': 'Founder',
        'counterparty_label': 'Investor',
        'data_room_exists': True,
        'data_room_accessible': data_room_accessible,
        'data_room_url': reverse('matchmaking:data_room', kwargs={'username': founder_application.user.username}) if data_room_accessible else None,
        'chat_channel_id': _stream_deal_channel_id(founder_application.user_id, investor_application.user_id),
        'zelda_summary': _get_deal_zelda_summary(founder_application),
        'documents': list(founder_application.data_room_documents.all()[:10]) if data_room_accessible else [],
        'activity': activity,
        'is_verified_outcome': connection.status == 'FUNDED',
        'verified_outcome_label': 'Verified Funded',
    })


@login_required
def acquisition_deal_workspace_view(request, connection_id):
    """
    Deal Room for one Buyer<->Seller relationship — mirrors
    deal_workspace_view exactly, same shared template. One real gap, not
    papered over: there is no seller-side Data Room (DataRoomDocument.
    founder is hard-FK'd to Application, not SellerApplication — confirmed
    absent, not merely unused; see matchmaking/deal_activity.py's
    get_acquisition_deal_activity_timeline docstring for the same finding
    applied to the activity timeline). data_room_exists=False tells the
    template to render that honestly instead of a broken or empty-looking
    working panel — distinct from data_room_accessible (see
    deal_workspace_view), which is about a specific viewer's access to
    Data Room infrastructure that DOES exist; here neither applies.
    """
    from .models import AcquisitionConnection, can_view_acquisition_deal_workspace
    from .deal_activity import get_acquisition_deal_activity_timeline

    connection = get_object_or_404(AcquisitionConnection, id=connection_id)
    if not can_view_acquisition_deal_workspace(request.user, connection):
        raise Http404("Access Denied")

    seller_application = connection.seller
    buyer_application = connection.buyer

    return render(request, 'matchmaking/deal_workspace.html', {
        'deal_type': 'acquisition',
        'connection': connection,
        'company_application': seller_application,
        'counterparty_application': buyer_application,
        'company_label': 'Seller',
        'counterparty_label': 'Buyer',
        'data_room_exists': False,
        'data_room_accessible': False,
        'data_room_url': None,
        'chat_channel_id': _stream_deal_channel_id(seller_application.user_id, buyer_application.user_id),
        'zelda_summary': _get_deal_zelda_summary(seller_application),
        'documents': [],
        'activity': get_acquisition_deal_activity_timeline(connection),
        'is_verified_outcome': connection.status == 'CLOSED',
        'verified_outcome_label': 'Verified Sold',
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

    Follow.objects.create(follower=request.user, following=target_user)
    return JsonResponse({'status': 'success', 'is_following': True})


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


# ──────────────────────────────────────────────────────────────────────────
# PITCH VIDEOS SECTION — founder/seller pitch videos, Zelda-ranked (not a
# chronological/viral feed) with social actions each owner can disable
# per-video via pitch_video_*_enabled settings.
# ──────────────────────────────────────────────────────────────────────────

def _rank_pitch_video_profiles(items, evaluate, viewer_partner_profile):
    """
    Sorts founders/sellers with a pitch video: active monthly highlight
    first, then staff/premium-featured (same convention as
    founder_bulletin_board/acquisition_bulletin_board), then by the
    canonical match against the viewer's investor/buyer profile if they
    have one, then most-recent first.

    This used to compute its own score straight from
    calculate_rule_based_score and render it as "{score}% Match" -- a rule
    subtotal presented as a match percentage, on the same scale where a
    bare stage agreement is worth 60. It is a canonical match consumer
    like any other and now reads the contract.
    """
    items = list(items)
    for item in items:
        item.match = evaluate(item, viewer_partner_profile) if viewer_partner_profile else None
        item.band = item.match.band.label if item.match else None

    items.sort(key=lambda x: (
        not x.is_highlighted,
        not (x.is_premium or x.is_staff_featured),
        -(x.match.band if x.match else 0),
        -(x.match.score if x.match else 0),
        -x.created_at.timestamp() if x.created_at else 0,
    ))
    return items


def pitch_videos_section(request):
    """
    GET /pitch-videos/ — founders and sellers who've uploaded a pitch
    video, ranked highest-match-first for an authenticated investor/buyer
    (falls back to featured-then-recency for everyone else). Deliberately
    not an infinite chronological scroll — see _rank_pitch_video_profiles.
    """
    investor_profile = None
    buyer_profile = None
    liked_founder_ids = saved_founder_ids = liked_seller_ids = saved_seller_ids = frozenset()

    if request.user.is_authenticated:
        investor_profile = getattr(request.user, 'match_investor_profile', None)
        buyer_profile = getattr(request.user, 'match_buyer_profile', None)
        liked_founder_ids = set(request.user.liked_founder_pitch_videos.values_list('id', flat=True))
        saved_founder_ids = set(request.user.saved_founder_pitch_videos.values_list('id', flat=True))
        liked_seller_ids = set(request.user.liked_seller_pitch_videos.values_list('id', flat=True))
        saved_seller_ids = set(request.user.saved_seller_pitch_videos.values_list('id', flat=True))

    # pitch_video is null=True, blank=True — existing rows may have either
    # NULL or '' for "no video", and exclude(pitch_video='') alone doesn't
    # catch NULL (three-valued SQL logic drops those rows from the negation
    # too, but .exclude() on a nullable field lets NULL rows straight
    # through unfiltered), which crashes FieldFile.url in the template.
    # PROFILE_ONLY is always excluded (owner opted the video out of this
    # section entirely, keeping it on their profile page); ROLE_ONLY is
    # excluded unless the viewer actually holds the matching role, so
    # anonymous visitors and same-role peers never see it here either.
    founder_qs = Application.objects.discoverable().exclude(
        review_status='DENIED'
    ).exclude(pitch_video='').exclude(pitch_video__isnull=True).exclude(
        pitch_video_visibility='PROFILE_ONLY'
    ).select_related('user')
    if not investor_profile:
        founder_qs = founder_qs.exclude(pitch_video_visibility='ROLE_ONLY')

    seller_qs = SellerApplication.objects.discoverable().exclude(
        review_status='DENIED'
    ).exclude(pitch_video='').exclude(pitch_video__isnull=True).exclude(
        pitch_video_visibility='PROFILE_ONLY'
    ).select_related('user')
    if not buyer_profile:
        seller_qs = seller_qs.exclude(pitch_video_visibility='ROLE_ONLY')

    founders = _rank_pitch_video_profiles(
        founder_qs, lambda f, inv: evaluate_venture_match(f, inv), investor_profile
    )
    for f in founders:
        f.viewer_has_liked = f.id in liked_founder_ids
        f.viewer_has_saved = f.id in saved_founder_ids
        f.like_count = f.pitch_video_likes.count() if f.pitch_video_show_like_count else None
        f.comment_count = f.pitch_video_comments.count()

    sellers = _rank_pitch_video_profiles(
        seller_qs, lambda s, buy: evaluate_deal_match(s, buy), buyer_profile
    )
    for s in sellers:
        s.viewer_has_liked = s.id in liked_seller_ids
        s.viewer_has_saved = s.id in saved_seller_ids
        s.like_count = s.pitch_video_likes.count() if s.pitch_video_show_like_count else None
        s.comment_count = s.pitch_video_comments.count()

    # Buyers came here primarily for sellers, everyone else primarily for
    # founders — just controls which tab is active by default, both lists
    # are always rendered.
    default_tab = 'sellers' if buyer_profile and not investor_profile else 'founders'

    return render(request, 'matchmaking/pitch_videos.html', {
        'founders': founders,
        'sellers': sellers,
        'default_tab': default_tab,
    })


def _pitch_video_owner(role, profile_id):
    """Resolves a (role, id) pair to its Application/SellerApplication instance, or raises Http404."""
    if role == 'founder':
        return get_object_or_404(Application.objects.discoverable(), id=profile_id)
    elif role == 'seller':
        return get_object_or_404(SellerApplication.objects.discoverable(), id=profile_id)
    raise Http404("Unknown pitch video role.")


@require_POST
def log_pitch_video_play(request, role, profile_id):
    """
    Top of the Video -> Profile Conversion funnel (see
    growth_metrics.get_pitch_video_funnel). Fired once per session from
    the Pitch Videos section on first `play`, distinct from the older
    PitchVideoView/record_video_telemetry watch-depth tracker, which is
    scoped to a founder's own profile page. Same investor/buyer role
    gating as the 'view' event logged in accounts.views.profile, so this
    event log never mixes in plays from anonymous visitors or same-role
    peers browsing each other's videos.
    """
    obj = _pitch_video_owner(role, profile_id)

    if request.user.is_authenticated and request.user.id != obj.user_id:
        if role == 'founder' and getattr(request.user, 'match_investor_profile', None):
            log_investor_event(request.user, obj, 'video_play')
        elif role == 'seller' and getattr(request.user, 'match_buyer_profile', None):
            log_buyer_event(request.user, obj, 'video_play')

    return JsonResponse({'status': 'success'})


@login_required
@require_POST
def toggle_pitch_video_like(request, role, profile_id):
    obj = _pitch_video_owner(role, profile_id)

    if obj.pitch_video_likes.filter(id=request.user.id).exists():
        obj.pitch_video_likes.remove(request.user)
        liked = False
    else:
        obj.pitch_video_likes.add(request.user)
        liked = True

    return JsonResponse({
        'status': 'success',
        'liked': liked,
        'like_count': obj.pitch_video_likes.count() if obj.pitch_video_show_like_count else None,
    })


@login_required
@require_POST
def toggle_pitch_video_save(request, role, profile_id):
    obj = _pitch_video_owner(role, profile_id)

    if obj.pitch_video_saves.filter(id=request.user.id).exists():
        obj.pitch_video_saves.remove(request.user)
        saved = False
    else:
        obj.pitch_video_saves.add(request.user)
        saved = True

    return JsonResponse({'status': 'success', 'saved': saved})


@login_required
@require_POST
def post_pitch_video_comment(request, role, profile_id):
    obj = _pitch_video_owner(role, profile_id)

    if not obj.pitch_video_comments_enabled:
        return JsonResponse({'error': 'Comments are disabled on this video.'}, status=403)

    body = request.POST.get('body', '').strip()
    if not body:
        return JsonResponse({'error': 'Comment cannot be empty.'}, status=400)
    if len(body) > 1000:
        return JsonResponse({'error': 'Comment is too long (max 1000 characters).'}, status=400)

    comment = PitchVideoComment.objects.create(
        founder=obj if role == 'founder' else None,
        seller=obj if role == 'seller' else None,
        author=request.user,
        body=body,
    )

    if obj.pitch_video_notify_on_comments and obj.user != request.user:
        try:
            from notifications.models import Notification
            Notification.objects.create(
                recipient=obj.user,
                sender=request.user,
                notification_type='PITCH_VIDEO_COMMENT',
                message=f"{request.user.get_full_name() or request.user.username} commented on your pitch video.",
                target_url=reverse('matchmaking:pitch_videos'),
            )
        except Exception as e:
            logger.warning(f"Failed to create pitch video comment notification: {str(e)}")

    return JsonResponse({
        'status': 'success',
        'comment': {
            'id': comment.id,
            'author': request.user.get_full_name() or request.user.username,
            'body': comment.body,
            'created_at': comment.created_at.strftime('%b %d, %Y'),
        },
    })


@login_required
@require_POST
def delete_pitch_video_comment(request, comment_id):
    comment = get_object_or_404(PitchVideoComment, id=comment_id)
    owner_user = comment.founder.user if comment.founder_id else comment.seller.user
    if comment.author != request.user and owner_user != request.user and not request.user.is_staff:
        return JsonResponse({'error': 'Not authorized.'}, status=403)
    comment.delete()
    return JsonResponse({'status': 'success'})


@login_required
@require_POST
def toggle_pitch_video_setting(request):
    """
    AJAX toggle for one of the four pitch-video engagement settings,
    applied to whichever profile(s) the requesting user owns. Mirrors the
    existing allow_direct_messages AJAX toggle in accounts/views.py.
    """
    setting = request.POST.get('setting')
    enabled = request.POST.get('enabled') == 'true'

    allowed_settings = {
        'comments_enabled': 'pitch_video_comments_enabled',
        'shares_enabled': 'pitch_video_shares_enabled',
        'show_like_count': 'pitch_video_show_like_count',
        'notify_on_comments': 'pitch_video_notify_on_comments',
    }
    field_name = allowed_settings.get(setting)
    if not field_name:
        return JsonResponse({'error': 'Unknown setting.'}, status=400)

    updated = False
    founder_profile = getattr(request.user, 'match_founder_profile', None)
    if founder_profile:
        setattr(founder_profile, field_name, enabled)
        founder_profile.save(update_fields=[field_name])
        updated = True

    seller_profile = getattr(request.user, 'match_seller_profile', None)
    if seller_profile:
        setattr(seller_profile, field_name, enabled)
        seller_profile.save(update_fields=[field_name])
        updated = True

    if not updated:
        return JsonResponse({'error': 'No founder or seller profile found.'}, status=404)

    return JsonResponse({'status': 'success', 'setting': setting, 'enabled': enabled})


@login_required
@require_POST
def set_pitch_video_visibility(request):
    """
    Where a pitch video appears: SITE_WIDE (default, shown to everyone in
    the Pitch Videos section — see pitch_videos_section), ROLE_ONLY (only
    to authenticated investors/buyers), or PROFILE_ONLY (pulled from the
    section entirely, still visible on the owner's own profile page since
    that page never consults this field). Same owner-profile-lookup
    pattern as toggle_pitch_video_setting, kept as a separate endpoint
    since this is a 3-way choice rather than a boolean.
    """
    visibility = request.POST.get('visibility')
    valid_choices = {'SITE_WIDE', 'ROLE_ONLY', 'PROFILE_ONLY'}
    if visibility not in valid_choices:
        return JsonResponse({'error': 'Unknown visibility setting.'}, status=400)

    updated = False
    founder_profile = getattr(request.user, 'match_founder_profile', None)
    if founder_profile:
        founder_profile.pitch_video_visibility = visibility
        founder_profile.save(update_fields=['pitch_video_visibility'])
        updated = True

    seller_profile = getattr(request.user, 'match_seller_profile', None)
    if seller_profile:
        seller_profile.pitch_video_visibility = visibility
        seller_profile.save(update_fields=['pitch_video_visibility'])
        updated = True

    if not updated:
        return JsonResponse({'error': 'No founder or seller profile found.'}, status=404)

    return JsonResponse({'status': 'success', 'visibility': visibility})


# ──────────────────────────────────────────────────────────────────────────
# EXPLORE / ELEVATOR PITCHES — the anonymous short-form discovery front door.
#
# Deliberately NOT the Pitch Videos section above: that one is a Zelda-ranked
# grid of 1-3 min videos gated by investor/buyer role. This is a full-screen
# vertical swipe feed of =<30s ProfileVideo(kind=ELEVATOR_PITCH) clips that
# anyone — logged out, no role chosen — can watch. The funnel is
# curiosity -> elevator pitch -> profile -> deck/Zelda -> deal, so every card's
# primary CTA points at the owner's profile.
#
# Moderation is publish-first (see ProfileVideo docstring): a clip is live the
# moment it uploads; the first viewer report quarantines it and pings staff.
# ──────────────────────────────────────────────────────────────────────────

from .models import ProfileVideo, ProfileVideoReport


def _rank_elevator_pitches(videos):
    """
    Featured/highlighted owners first (same bulletin-board convention as
    _rank_pitch_video_profiles), then a light completion-rate nudge among
    clips that have enough views to be meaningful, then newest-first.
    Intentionally simple — no per-viewer personalization or engagement
    optimization in Phase 1.
    """
    def key(v):
        p = v.owner_profile
        highlighted = bool(p and getattr(p, 'is_highlighted', False))
        featured = bool(p and (getattr(p, 'is_premium', False) or getattr(p, 'is_staff_featured', False)))
        completion = round(v.completion_rate, 2) if v.view_count >= 5 else 0.4
        return (
            not highlighted,
            not featured,
            -completion,
            -(v.created_at.timestamp() if v.created_at else 0),
        )
    return sorted(videos, key=key)


@ensure_csrf_cookie
def explore_feed(request):
    """
    GET /explore/ — the Elevator Pitches feed. No auth, no role selection.
    ?v=<id> starts the scroll at a specific clip (used by Share links).
    @ensure_csrf_cookie so the standalone page's play/interested/report
    fetches have a CSRF token even for a first-time anonymous visitor.
    """
    videos = list(ProfileVideo.objects.visible_elevator_pitches())
    videos = _rank_elevator_pitches(videos)

    interested_ids = frozenset()
    if request.user.is_authenticated:
        interested_ids = set(
            request.user.interested_profile_videos.values_list('id', flat=True)
        )

    # The profile page is @login_required. For an anonymous viewer the "View
    # profile" CTA is the conversion point — send them to signup with the
    # profile as `next` so they land there right after creating an account.
    def _profile_link(username):
        path = reverse('accounts:profile', kwargs={'username': username})
        if request.user.is_authenticated:
            return path
        return f"{reverse('accounts:signup')}?next={quote(path)}"

    cards = []
    for v in videos:
        p = v.owner_profile
        if not p:
            continue
        is_founder = v.role == 'founder'
        cards.append({
            'id': v.id,
            'video_url': v.video.url,
            'caption': v.caption,
            'company_name': getattr(p, 'company_name', ''),
            'owner_name': getattr(p, 'founder_name', '') or getattr(p, 'seller_name', ''),
            'context': (
                f"{getattr(p, 'sector', '')} · {getattr(p, 'stage', '')}".strip(' ·')
                if is_founder else
                f"{getattr(p, 'industry', '')} · For sale".strip(' ·')
            ),
            'role_label': 'Founder' if is_founder else 'Business for sale',
            'profile_url': _profile_link(p.user.username),
            'interested_count': v.interested_users.count(),
            'viewer_interested': v.id in interested_ids,
        })

    try:
        start_id = int(request.GET.get('v', ''))
    except (TypeError, ValueError):
        start_id = None

    return render(request, 'matchmaking/explore.html', {
        'cards': cards,
        'start_id': start_id,
        'reason_choices': ProfileVideoReport.REASON_CHOICES,
    })


def _get_published_elevator_pitch(video_id):
    return ProfileVideo.objects.filter(
        id=video_id, kind=ProfileVideo.KIND_ELEVATOR_PITCH,
    ).select_related('founder__user', 'seller__user').first()


@require_POST
def elevator_pitch_play(request, video_id):
    """
    Fired by the feed when a clip enters view / finishes. Anonymous-safe:
    counts are aggregate only (no per-viewer row, no PII), deduped per
    session so a scroll back up doesn't double-count. Body: {"completed": bool}.
    """
    video = _get_published_elevator_pitch(video_id)
    if not video or video.status != ProfileVideo.STATUS_PUBLISHED:
        return JsonResponse({'status': 'ignored'})

    try:
        completed = bool(json.loads(request.body or '{}').get('completed'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        completed = False

    seen = request.session.get('ep_seen', [])
    done = request.session.get('ep_done', [])
    changed = False

    if video_id not in seen:
        ProfileVideo.objects.filter(id=video_id).update(view_count=F('view_count') + 1)
        seen.append(video_id)
        request.session['ep_seen'] = seen[-200:]
        changed = True
    if completed and video_id not in done:
        ProfileVideo.objects.filter(id=video_id).update(
            completed_view_count=F('completed_view_count') + 1
        )
        done.append(video_id)
        request.session['ep_done'] = done[-200:]
        changed = True

    if changed:
        request.session.modified = True
    return JsonResponse({'status': 'success'})


@login_required
@require_POST
def elevator_pitch_interested(request, video_id):
    """'Interested' — a soft signal on the feed, kept deliberately light
    (no comments/saves in Explore). Anonymous clicks redirect to signup
    client-side before ever reaching here."""
    video = _get_published_elevator_pitch(video_id)
    if not video:
        return JsonResponse({'error': 'Not found.'}, status=404)

    if video.interested_users.filter(id=request.user.id).exists():
        video.interested_users.remove(request.user)
        interested = False
    else:
        video.interested_users.add(request.user)
        interested = True
        owner_user = video.owner_profile.user
        if owner_user != request.user:
            try:
                from notifications.models import Notification
                Notification.objects.create(
                    recipient=owner_user, sender=request.user,
                    notification_type='ELEVATOR_PITCH_INTEREST',
                    message=f"{request.user.get_full_name() or request.user.username} is interested in your elevator pitch.",
                    target_url=reverse('accounts:profile', kwargs={'username': owner_user.username}),
                )
            except Exception as e:
                logger.warning(f"elevator pitch interest notification failed: {e}")

    return JsonResponse({
        'status': 'success',
        'interested': interested,
        'interested_count': video.interested_users.count(),
    })


@login_required
@require_POST
def elevator_pitch_report(request, video_id):
    """
    A logged-in viewer reports a clip. The first report on a PUBLISHED clip
    quarantines it (off Explore, into the staff queue) and notifies staff.
    A report is a temporary takedown pending review, never an automatic
    verdict — staff restore or remove from the admin.
    """
    video = _get_published_elevator_pitch(video_id)
    if not video:
        return JsonResponse({'error': 'Not found.'}, status=404)

    reason = (request.POST.get('reason') or '').strip().upper()
    valid_reasons = {c[0] for c in ProfileVideoReport.REASON_CHOICES}
    if reason not in valid_reasons:
        return JsonResponse({'error': 'Pick a reason.'}, status=400)
    detail = (request.POST.get('detail') or '').strip()[:1000]

    if video.owner_profile.user_id == request.user.id:
        return JsonResponse({'error': "You can't report your own video."}, status=400)

    report, created = ProfileVideoReport.objects.get_or_create(
        video=video, reporter=request.user,
        defaults={'reason': reason, 'detail': detail},
    )
    if not created:
        return JsonResponse({'status': 'success', 'already_reported': True})

    ProfileVideo.objects.filter(id=video.id).update(report_count=F('report_count') + 1)
    was_published = video.status == ProfileVideo.STATUS_PUBLISHED
    if was_published:
        video.quarantine(first_report_at=report.created_at)
        _notify_staff_of_video_report(video, report)

    return JsonResponse({'status': 'success', 'quarantined': was_published})


def _notify_staff_of_video_report(video, report):
    """In-app Notification for every staff user + an email to ADMINS."""
    queue_url = reverse('admin:matchmaking_profilevideo_changelist') + '?status__exact=QUARANTINED'
    try:
        from notifications.models import Notification
        staff = User.objects.filter(is_staff=True, is_active=True)
        Notification.objects.bulk_create([
            Notification(
                recipient=s, sender=report.reporter,
                notification_type='ELEVATOR_PITCH_REPORT',
                message=f"Elevator pitch by {video.owner_display} was reported ({report.get_reason_display()}) and pulled from Explore.",
                target_url=queue_url,
            )
            for s in staff
        ])
    except Exception as e:
        logger.warning(f"staff report notification failed: {e}")

    try:
        from django.core.mail import mail_admins
        mail_admins(
            subject=f"[Explore] Elevator pitch reported — {video.owner_display}",
            message=(
                f"Reason: {report.get_reason_display()}\n"
                f"Reporter: {report.reporter.username}\n"
                f"Detail: {report.detail or '(none)'}\n\n"
                f"The clip has been quarantined (removed from Explore) pending your review.\n"
                f"Review queue: {queue_url}\n"
            ),
            fail_silently=True,
        )
    except Exception as e:
        logger.warning(f"mail_admins for video report failed: {e}")


@login_required
def manage_elevator_pitch(request):
    """
    Owner-facing upload/replace/delete for the single ELEVATOR_PITCH clip on
    the requester's founder or seller profile. Reached from Settings ->
    Pitch Video. The =<30s / =<30MB / MP4-MOV-WEBM limits are enforced by
    the model field validators; the browser also checks duration before
    the file is sent and posts it back as `duration_seconds`.
    """
    profile = getattr(request.user, 'match_founder_profile', None)
    role = 'founder'
    if profile is None:
        profile = getattr(request.user, 'match_seller_profile', None)
        role = 'seller'
    if profile is None:
        messages.error(request, "Add a founder or business-for-sale profile first.")
        return redirect('usersettings:home')

    existing = ProfileVideo.objects.filter(
        **{role: profile}, kind=ProfileVideo.KIND_ELEVATOR_PITCH,
    ).first()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'delete' and existing:
            existing.video.delete(save=False)
            existing.delete()
            messages.success(request, "Elevator pitch removed.")
            return redirect('usersettings:home')

        caption = (request.POST.get('caption') or '').strip()[:140]
        duration = request.POST.get('duration_seconds')
        try:
            duration = float(duration) if duration else None
        except ValueError:
            duration = None

        upload = request.FILES.get('video')
        if not upload and existing:
            existing.caption = caption
            existing.save(update_fields=['caption', 'updated_at'])
            messages.success(request, "Elevator pitch caption updated.")
            return redirect('usersettings:home')

        if not upload:
            messages.error(request, "Choose a video file to upload.")
            return redirect('matchmaking:manage_elevator_pitch')

        if duration is not None and duration > ProfileVideo.ELEVATOR_MAX_SECONDS + 2:
            messages.error(
                request,
                f"That clip is {duration:.0f}s. Elevator pitches must be {ProfileVideo.ELEVATOR_MAX_SECONDS} seconds or less.",
            )
            return redirect('matchmaking:manage_elevator_pitch')

        target = existing or ProfileVideo(**{role: profile}, kind=ProfileVideo.KIND_ELEVATOR_PITCH)
        if existing and existing.video:
            existing.video.delete(save=False)
        target.video = upload
        target.caption = caption
        target.duration_seconds = duration
        # A fresh upload of a previously removed/quarantined clip re-enters review-free.
        target.status = ProfileVideo.STATUS_PUBLISHED
        try:
            target.full_clean(exclude=['founder', 'seller'])
        except ValidationError as e:
            messages.error(request, "; ".join(e.messages))
            return redirect('matchmaking:manage_elevator_pitch')
        target.save()
        messages.success(request, "Elevator pitch is live on Explore.")
        return redirect('usersettings:home')

    return render(request, 'matchmaking/manage_elevator_pitch.html', {
        'existing': existing,
        'role': role,
        'max_seconds': ProfileVideo.ELEVATOR_MAX_SECONDS,
        'max_mb': ProfileVideo.ELEVATOR_MAX_MB,
    })


# 1x1 transparent PNG — the smallest valid image, served by digest_open_pixel.
_TRANSPARENT_PIXEL_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
    b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)


def digest_open_pixel(request, token):
    """
    Embedded as an <img> in the weekly digest email — no auth, no CSRF,
    must always return a valid (tiny) image regardless of whether the
    token is recognized, since email clients don't care about our
    bookkeeping and a broken image would just look like a bug to the user.
    """
    from .models import DigestEngagementEvent

    sent_event = DigestEngagementEvent.objects.filter(token=token, event_type='sent').first()
    if sent_event and not DigestEngagementEvent.objects.filter(token=token, event_type='opened').exists():
        DigestEngagementEvent.objects.create(recipient=sent_event.recipient, event_type='opened', token=token)

    return HttpResponse(_TRANSPARENT_PIXEL_PNG, content_type='image/png')


def digest_click_redirect(request, token, destination):
    """
    The weekly digest's hero-match link routes through here before landing
    on the real dashboard, purely to record the click — same
    fail-open shape as digest_open_pixel: an unrecognized token still
    redirects, it just doesn't get credited as a tracked click.
    """
    from .models import DigestEngagementEvent

    sent_event = DigestEngagementEvent.objects.filter(token=token, event_type='sent').first()
    if sent_event and not DigestEngagementEvent.objects.filter(token=token, event_type='clicked').exists():
        DigestEngagementEvent.objects.create(recipient=sent_event.recipient, event_type='clicked', token=token)

    target = 'matchmaking:founder_dashboard' if destination == 'founder' else 'matchmaking:investor_dashboard'
    return redirect(target)