"""
Full-funnel product analytics — powers the Funnel and Zelda Usage tabs on
platform_metrics. Every stage below is a pure aggregate COUNT against data
that already exists elsewhere in the app (vector presence, interest events,
Connection/AcquisitionConnection status, is_premium) — the only genuinely
new tracking is PageEvent, which covers the pre-signup stages that have no
User row yet. See matchmaking/models.py::PageEvent/log_page_event.

Deliberately no per-user Python loops: each stage is one queryset-level
query, not N calls to the single-user compute_*_journey_stage helpers in
matchmaking/utils.py (those are for a single logged-in user's onboarding
widget, not bulk aggregation).
"""
from .models import (
    PageEvent, Application, InvestorApplication, SellerApplication, BuyerApplication,
    InvestorInterestEvent, AcquisitionInterestEvent, Connection, AcquisitionConnection,
)

ZELDA_EVENT_TYPES = ['analyze', 'memo_view', 'truth_delta_view']

FUNNEL_STAGES = [
    ('landing', 'Landing Page'),
    ('signup_started', 'Signup Started'),
    ('signup_completed', 'Signup Completed'),
    ('profile_complete', 'Profile Complete'),
    ('matched', 'First Match'),
    ('intro_sent', 'Introduction Sent'),
    ('intro_accepted', 'Introduction Accepted'),
    ('deal_room', 'Deal Room Reached'),
    ('zelda_used', 'Used Zelda'),
    ('premium', 'Premium Upgrade'),
]


def _with_dropoff(stage_counts):
    """Turns an ordered {stage_key: count} dict into a list of
    {key, label, count, dropoff_pct} — dropoff_pct is the % lost vs the
    previous stage (None for the first stage)."""
    rows = []
    previous_count = None
    for key, label in FUNNEL_STAGES:
        count = stage_counts.get(key, 0)
        dropoff_pct = None
        if previous_count is not None and previous_count > 0:
            dropoff_pct = round((1 - (count / previous_count)) * 100, 1)
        rows.append({'key': key, 'label': label, 'count': count, 'dropoff_pct': dropoff_pct})
        previous_count = count
    return rows


def _pre_signup_counts():
    landing = PageEvent.objects.filter(event_type='landing_view').values('session_key').distinct().count()
    started = PageEvent.objects.filter(event_type='signup_started').values('session_key').distinct().count()
    return landing, started


def get_founder_investor_funnel():
    landing, started = _pre_signup_counts()

    founder_signups = Application.objects.count()
    founder_profile_complete = Application.objects.filter(description_vector__isnull=False).count()
    founder_matched = Application.objects.filter(
        id__in=InvestorInterestEvent.objects.values_list('founder_id', flat=True).distinct()
    ).count()
    founder_intro_sent = Application.objects.filter(
        id__in=Connection.objects.values_list('founder_id', flat=True).distinct()
    ).count()
    founder_intro_accepted = Application.objects.filter(
        id__in=Connection.objects.filter(status='ACCEPTED').values_list('founder_id', flat=True).distinct()
    ).count()
    founder_deal_room = Application.objects.filter(
        id__in=InvestorInterestEvent.objects.filter(event_type='message_sent').values_list('founder_id', flat=True).distinct()
    ).count()
    founder_zelda_used = Application.objects.filter(
        id__in=InvestorInterestEvent.objects.filter(event_type__in=ZELDA_EVENT_TYPES).values_list('founder_id', flat=True).distinct()
    ).count()
    founder_premium = Application.objects.filter(is_premium=True).count()

    founder = _with_dropoff({
        'landing': landing,
        'signup_started': started,
        'signup_completed': founder_signups,
        'profile_complete': founder_profile_complete,
        'matched': founder_matched,
        'intro_sent': founder_intro_sent,
        'intro_accepted': founder_intro_accepted,
        'deal_room': founder_deal_room,
        'zelda_used': founder_zelda_used,
        'premium': founder_premium,
    })

    investor_signups = InvestorApplication.objects.count()
    investor_profile_complete = InvestorApplication.objects.filter(focus_vector__isnull=False).count()
    investor_matched = InvestorApplication.objects.filter(
        user__in=InvestorInterestEvent.objects.values_list('investor_id', flat=True).distinct()
    ).count()
    investor_intro_sent = InvestorApplication.objects.filter(
        id__in=Connection.objects.values_list('investor_id', flat=True).distinct()
    ).count()
    investor_intro_accepted = InvestorApplication.objects.filter(
        id__in=Connection.objects.filter(status='ACCEPTED').values_list('investor_id', flat=True).distinct()
    ).count()
    investor_deal_room = InvestorApplication.objects.filter(
        user__in=InvestorInterestEvent.objects.filter(event_type='message_sent').values_list('investor_id', flat=True).distinct()
    ).count()
    investor_zelda_used = InvestorApplication.objects.filter(
        user__in=InvestorInterestEvent.objects.filter(event_type__in=ZELDA_EVENT_TYPES).values_list('investor_id', flat=True).distinct()
    ).count()
    investor_premium = InvestorApplication.objects.filter(is_premium=True).count()

    investor = _with_dropoff({
        'landing': landing,
        'signup_started': started,
        'signup_completed': investor_signups,
        'profile_complete': investor_profile_complete,
        'matched': investor_matched,
        'intro_sent': investor_intro_sent,
        'intro_accepted': investor_intro_accepted,
        'deal_room': investor_deal_room,
        'zelda_used': investor_zelda_used,
        'premium': investor_premium,
    })

    return {'founder': founder, 'investor': investor}


def get_seller_buyer_funnel():
    landing, started = _pre_signup_counts()

    seller_signups = SellerApplication.objects.count()
    seller_profile_complete = SellerApplication.objects.filter(description_vector__isnull=False).count()
    seller_matched = SellerApplication.objects.filter(
        id__in=AcquisitionInterestEvent.objects.values_list('seller_id', flat=True).distinct()
    ).count()
    seller_intro_sent = SellerApplication.objects.filter(
        id__in=AcquisitionConnection.objects.values_list('seller_id', flat=True).distinct()
    ).count()
    seller_intro_accepted = SellerApplication.objects.filter(
        id__in=AcquisitionConnection.objects.filter(status='ACCEPTED').values_list('seller_id', flat=True).distinct()
    ).count()
    seller_deal_room = SellerApplication.objects.filter(
        id__in=AcquisitionInterestEvent.objects.filter(event_type='message_sent').values_list('seller_id', flat=True).distinct()
    ).count()
    seller_zelda_used = SellerApplication.objects.filter(
        id__in=AcquisitionInterestEvent.objects.filter(event_type__in=ZELDA_EVENT_TYPES).values_list('seller_id', flat=True).distinct()
    ).count()
    seller_premium = SellerApplication.objects.filter(is_premium=True).count()

    seller = _with_dropoff({
        'landing': landing,
        'signup_started': started,
        'signup_completed': seller_signups,
        'profile_complete': seller_profile_complete,
        'matched': seller_matched,
        'intro_sent': seller_intro_sent,
        'intro_accepted': seller_intro_accepted,
        'deal_room': seller_deal_room,
        'zelda_used': seller_zelda_used,
        'premium': seller_premium,
    })

    buyer_signups = BuyerApplication.objects.count()
    buyer_profile_complete = BuyerApplication.objects.filter(focus_vector__isnull=False).count()
    buyer_matched = BuyerApplication.objects.filter(
        user__in=AcquisitionInterestEvent.objects.values_list('buyer_id', flat=True).distinct()
    ).count()
    buyer_intro_sent = BuyerApplication.objects.filter(
        id__in=AcquisitionConnection.objects.values_list('buyer_id', flat=True).distinct()
    ).count()
    buyer_intro_accepted = BuyerApplication.objects.filter(
        id__in=AcquisitionConnection.objects.filter(status='ACCEPTED').values_list('buyer_id', flat=True).distinct()
    ).count()
    buyer_deal_room = BuyerApplication.objects.filter(
        user__in=AcquisitionInterestEvent.objects.filter(event_type='message_sent').values_list('buyer_id', flat=True).distinct()
    ).count()
    buyer_zelda_used = BuyerApplication.objects.filter(
        user__in=AcquisitionInterestEvent.objects.filter(event_type__in=ZELDA_EVENT_TYPES).values_list('buyer_id', flat=True).distinct()
    ).count()
    buyer_premium = BuyerApplication.objects.filter(is_premium=True).count()

    buyer = _with_dropoff({
        'landing': landing,
        'signup_started': started,
        'signup_completed': buyer_signups,
        'profile_complete': buyer_profile_complete,
        'matched': buyer_matched,
        'intro_sent': buyer_intro_sent,
        'intro_accepted': buyer_intro_accepted,
        'deal_room': buyer_deal_room,
        'zelda_used': buyer_zelda_used,
        'premium': buyer_premium,
    })

    return {'seller': seller, 'buyer': buyer}


def get_zelda_feature_usage():
    """Breakdown of which Zelda features get used, by role — answers
    'which Zelda feature gets used' directly, separate from the funnel's
    single collapsed 'zelda_used' checkpoint."""
    feature_labels = {
        'analyze': 'Analyzed with Zelda',
        'memo_view': 'Viewed Intelligence Memo',
        'truth_delta_view': 'Viewed Truth Delta',
        'message_sent': 'Sent Direct Message',
    }
    rows = []
    for event_type, label in feature_labels.items():
        rows.append({
            'label': label,
            'investor': InvestorInterestEvent.objects.filter(event_type=event_type).count(),
            'buyer': AcquisitionInterestEvent.objects.filter(event_type=event_type).count(),
        })
    return rows
