"""
Growth metrics — Acquisition / Activation / Engagement / Value Creation /
Feature Adoption tabs on platform_metrics. Same convention as analytics.py:
pure queryset aggregates, no per-user Python loops, reuses ZELDA_EVENT_TYPES
and _pre_signup_counts from analytics.py so the pre-signup funnel numbers
can never drift between the two dashboards.
"""
import json
import statistics
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, OuterRef, Q, Subquery
from django.utils import timezone

from .analytics import ZELDA_EVENT_TYPES, _pre_signup_counts
from .models import (
    Application, InvestorApplication, SellerApplication, BuyerApplication,
    InvestorInterestEvent, AcquisitionInterestEvent, Connection, AcquisitionConnection,
    PageEvent, SearchEvent, MessageThread, PitchDeckViewSession, PitchDeckSlideTime,
    PitchVideoComment,
)
from growth.models import ReferralInvite
from zelda_api.vector_models import DocumentSource

User = get_user_model()


def get_deck_engagement_stats(application):
    """
    Pitch deck engagement analytics — aggregate only, never per-viewer
    identity (safe to show an investor even though the underlying sessions
    include other investors). Shared by accounts.views.profile_analysis
    (the founder's own analytics page) and the IC memo generator
    (zelda_api/ic_memo.py) so the two can never disagree on the numbers.
    """
    if not application or not application.pitch_deck:
        return None

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
    return {
        'total_sessions': total_sessions,
        'unique_viewers': unique_viewers,
        'avg_session_time': round(total_time / total_sessions, 1) if total_sessions else 0,
        'slides': [
            {'slide_number': row['slide_number'], 'avg_duration': round(row['avg_duration'], 1), 'views': row['views']}
            for row in slide_stats
        ],
        'slide_labels': json.dumps([f"Slide {row['slide_number']}" for row in slide_stats]),
        'slide_durations': json.dumps([round(row['avg_duration'], 1) for row in slide_stats]),
    }


TRENDING_WINDOW_DAYS = 7
TRENDING_MIN_UNIQUE_VIEWERS = 5
FREQUENTLY_ANALYZED_MIN_UNIQUE_ANALYSTS = 3


def get_profile_trust_badges(application):
    """
    Privacy-preserving social-proof badges for a founder's public profile.
    Never expose the raw counts backing these (view totals, exact analyze
    counts) — that reveals individual investor behavior and invites gaming
    ("3 investors analyzed me today" changes what founders optimize for).
    Each badge is a boolean gated behind a minimum number of DISTINCT
    investors, so one or two investors' activity can never surface here.
    """
    if not application:
        return {'trending': False, 'frequently_analyzed': False}

    window_start = timezone.now() - timedelta(days=TRENDING_WINDOW_DAYS)
    recent_unique_viewers = InvestorInterestEvent.objects.filter(
        founder=application, event_type='view', created_at__gte=window_start
    ).values('investor_id').distinct().count()

    unique_analysts = InvestorInterestEvent.objects.filter(
        founder=application, event_type='analyze'
    ).values('investor_id').distinct().count()

    return {
        'trending': recent_unique_viewers >= TRENDING_MIN_UNIQUE_VIEWERS,
        'frequently_analyzed': unique_analysts >= FREQUENTLY_ANALYZED_MIN_UNIQUE_ANALYSTS,
    }


PLATFORM_INSIGHT_MIN_COHORT_SIZE = 10
RECENT_UPDATE_WINDOW_DAYS = 30


def _avg_investor_views_per_founder(applications_qs):
    """Average count of investor 'view' events per founder in this queryset."""
    founder_ids = list(applications_qs.values_list('id', flat=True))
    if not founder_ids:
        return 0.0
    total_views = InvestorInterestEvent.objects.filter(founder_id__in=founder_ids, event_type='view').count()
    return round(total_views / len(founder_ids), 1)


def _intro_rate_pct(applications_qs):
    """% of founders in this queryset with at least one Connection."""
    total = applications_qs.count()
    if not total:
        return 0.0
    with_intro = applications_qs.filter(
        id__in=Connection.objects.values_list('founder_id', flat=True).distinct()
    ).count()
    return round(with_intro / total * 100, 1)


def get_platform_insights():
    """
    Aggregate, platform-level observations for the founder dashboard —
    never a judgment about a specific company, only "founders like X have
    tended to see Y so far." Each insight is omitted entirely unless BOTH
    compared cohorts clear PLATFORM_INSIGHT_MIN_COHORT_SIZE, so a handful of
    founders can never produce a misleadingly confident claim (same
    "0 samples != 0 value" discipline as the rest of this module). Framed
    as an observed association, not a causal instruction — these cohorts
    aren't randomized, so "founders who did X saw more Y" does not mean X
    caused Y.
    """
    insights = []

    complete = Application.objects.filter(description_vector__isnull=False)
    incomplete = Application.objects.filter(description_vector__isnull=True)
    if complete.count() >= PLATFORM_INSIGHT_MIN_COHORT_SIZE and incomplete.count() >= PLATFORM_INSIGHT_MIN_COHORT_SIZE:
        insights.append(
            f"Founders with a completed profile have averaged {_avg_investor_views_per_founder(complete)} "
            f"investor views, vs {_avg_investor_views_per_founder(incomplete)} for incomplete profiles, "
            f"based on {complete.count() + incomplete.count()} founders on the platform so far."
        )

    with_deck = Application.objects.exclude(pitch_deck='').exclude(pitch_deck__isnull=True)
    without_deck = Application.objects.filter(Q(pitch_deck='') | Q(pitch_deck__isnull=True))
    if with_deck.count() >= PLATFORM_INSIGHT_MIN_COHORT_SIZE and without_deck.count() >= PLATFORM_INSIGHT_MIN_COHORT_SIZE:
        insights.append(
            f"{_intro_rate_pct(with_deck)}% of founders with a pitch deck uploaded have received an "
            f"introduction, vs {_intro_rate_pct(without_deck)}% of those without one, "
            f"based on {with_deck.count() + without_deck.count()} founders on the platform so far."
        )

    recent_cutoff = timezone.now() - timedelta(days=RECENT_UPDATE_WINDOW_DAYS)
    recently_updated = Application.objects.filter(vector_fields_updated_at__gte=recent_cutoff)
    stale = Application.objects.filter(
        Q(vector_fields_updated_at__lt=recent_cutoff) | Q(vector_fields_updated_at__isnull=True)
    )
    if recently_updated.count() >= PLATFORM_INSIGHT_MIN_COHORT_SIZE and stale.count() >= PLATFORM_INSIGHT_MIN_COHORT_SIZE:
        insights.append(
            f"Profiles updated within the last {RECENT_UPDATE_WINDOW_DAYS} days have averaged "
            f"{_avg_investor_views_per_founder(recently_updated)} investor views, vs "
            f"{_avg_investor_views_per_founder(stale)} for older profiles, "
            f"based on {recently_updated.count() + stale.count()} founders on the platform so far."
        )

    return insights


def get_pitch_video_funnel(profile, role):
    """
    Video -> Profile Conversion: of the distinct investors/buyers who
    played this founder/seller's pitch video, how many also opened the
    profile, ran a Zelda analysis, requested an introduction, or messaged
    them. Each stage is the video-viewer cohort intersected with that
    event type, not a raw aggregate count — most profile opens/analyses
    have nothing to do with the pitch video at all (an investor can reach
    a profile from the dashboard, search, or a direct link), so comparing
    raw totals stage-over-stage produces meaningless ratios that can
    exceed 100%. Intersecting keeps every percentage bounded to 0-100 and
    answers "of the people who watched, how many went further" instead.
    """
    if role == 'founder':
        events = InvestorInterestEvent.objects.filter(founder=profile)
        actor_field = 'investor_id'
    else:
        events = AcquisitionInterestEvent.objects.filter(seller=profile)
        actor_field = 'buyer_id'

    def actor_ids(event_type):
        return set(events.filter(event_type=event_type).values_list(actor_field, flat=True))

    played = actor_ids('video_play')
    opened = actor_ids('view') & played
    analyzed = actor_ids('analyze') & played
    intro_requested = actor_ids('intro_request') & played
    messaged = actor_ids('message_sent') & played

    def rate(cohort):
        return round(len(cohort) / len(played) * 100, 1) if played else None

    return {
        'plays': len(played),
        'profile_opens': len(opened),
        'analyses': len(analyzed),
        'intro_requests': len(intro_requested),
        'conversations': len(messaged),
        'profile_open_pct': rate(opened),
        'analysis_pct': rate(analyzed),
        'intro_request_pct': rate(intro_requested),
        'conversation_pct': rate(messaged),
    }


def _founder_intro_hit_count(applications_qs):
    """How many founders in this queryset have received >=1 intro_request."""
    ids = list(applications_qs.values_list('id', flat=True))
    if not ids:
        return 0
    return InvestorInterestEvent.objects.filter(
        founder_id__in=ids, event_type='intro_request'
    ).values('founder_id').distinct().count()


def _seller_intro_hit_count(applications_qs):
    """How many sellers in this queryset have received >=1 intro_request."""
    ids = list(applications_qs.values_list('id', flat=True))
    if not ids:
        return 0
    return AcquisitionInterestEvent.objects.filter(
        seller_id__in=ids, event_type='intro_request'
    ).values('seller_id').distinct().count()


def get_pitch_video_social_signal_insights():
    """
    Do likes/comments/saves on a pitch video actually predict outcomes, or
    are they just vanity metrics? Compares the intro-request rate between
    videos with >=1 like/comment/save vs videos with none, blending
    founders and sellers into one cohort per signal (rather than two
    separate insights) so the platform reaches PLATFORM_INSIGHT_MIN_COHORT_SIZE
    sooner while pitch-video volume is still small. Same non-causal,
    "on the platform so far" framing as get_platform_insights — these
    cohorts aren't randomized, so a like doesn't cause an intro request;
    a founder/seller compelling enough to get liked is often also
    compelling enough to earn an intro on the merits alone.
    """
    insights = []

    founders_with_video = Application.objects.exclude(pitch_video='').exclude(pitch_video__isnull=True)
    sellers_with_video = SellerApplication.objects.exclude(pitch_video='').exclude(pitch_video__isnull=True)

    # --- Liked vs not-liked ---
    liked_founders = founders_with_video.filter(pitch_video_likes__isnull=False).distinct()
    unliked_founders = founders_with_video.exclude(id__in=liked_founders.values('id'))
    liked_sellers = sellers_with_video.filter(pitch_video_likes__isnull=False).distinct()
    unliked_sellers = sellers_with_video.exclude(id__in=liked_sellers.values('id'))

    liked_total = liked_founders.count() + liked_sellers.count()
    unliked_total = unliked_founders.count() + unliked_sellers.count()
    if liked_total >= PLATFORM_INSIGHT_MIN_COHORT_SIZE and unliked_total >= PLATFORM_INSIGHT_MIN_COHORT_SIZE:
        liked_hits = _founder_intro_hit_count(liked_founders) + _seller_intro_hit_count(liked_sellers)
        unliked_hits = _founder_intro_hit_count(unliked_founders) + _seller_intro_hit_count(unliked_sellers)
        insights.append(
            f"Pitch videos with at least one like have led to an introduction "
            f"{round(liked_hits / liked_total * 100, 1)}% of the time, vs "
            f"{round(unliked_hits / unliked_total * 100, 1)}% for videos with no likes, "
            f"based on {liked_total + unliked_total} pitch videos on the platform so far."
        )

    # --- Commented vs not-commented ---
    commented_founder_ids = PitchVideoComment.objects.filter(founder__isnull=False).values_list('founder_id', flat=True).distinct()
    commented_seller_ids = PitchVideoComment.objects.filter(seller__isnull=False).values_list('seller_id', flat=True).distinct()
    commented_founders = founders_with_video.filter(id__in=commented_founder_ids)
    uncommented_founders = founders_with_video.exclude(id__in=commented_founder_ids)
    commented_sellers = sellers_with_video.filter(id__in=commented_seller_ids)
    uncommented_sellers = sellers_with_video.exclude(id__in=commented_seller_ids)

    commented_total = commented_founders.count() + commented_sellers.count()
    uncommented_total = uncommented_founders.count() + uncommented_sellers.count()
    if commented_total >= PLATFORM_INSIGHT_MIN_COHORT_SIZE and uncommented_total >= PLATFORM_INSIGHT_MIN_COHORT_SIZE:
        commented_hits = _founder_intro_hit_count(commented_founders) + _seller_intro_hit_count(commented_sellers)
        uncommented_hits = _founder_intro_hit_count(uncommented_founders) + _seller_intro_hit_count(uncommented_sellers)
        insights.append(
            f"Pitch videos with at least one comment have led to an introduction "
            f"{round(commented_hits / commented_total * 100, 1)}% of the time, vs "
            f"{round(uncommented_hits / uncommented_total * 100, 1)}% for videos with no comments, "
            f"based on {commented_total + uncommented_total} pitch videos on the platform so far."
        )

    # --- Saved vs not-saved ---
    saved_founders = founders_with_video.filter(pitch_video_saves__isnull=False).distinct()
    unsaved_founders = founders_with_video.exclude(id__in=saved_founders.values('id'))
    saved_sellers = sellers_with_video.filter(pitch_video_saves__isnull=False).distinct()
    unsaved_sellers = sellers_with_video.exclude(id__in=saved_sellers.values('id'))

    saved_total = saved_founders.count() + saved_sellers.count()
    unsaved_total = unsaved_founders.count() + unsaved_sellers.count()
    if saved_total >= PLATFORM_INSIGHT_MIN_COHORT_SIZE and unsaved_total >= PLATFORM_INSIGHT_MIN_COHORT_SIZE:
        saved_hits = _founder_intro_hit_count(saved_founders) + _seller_intro_hit_count(saved_sellers)
        unsaved_hits = _founder_intro_hit_count(unsaved_founders) + _seller_intro_hit_count(unsaved_sellers)
        insights.append(
            f"Saved pitch videos have led to an introduction "
            f"{round(saved_hits / saved_total * 100, 1)}% of the time, vs "
            f"{round(unsaved_hits / unsaved_total * 100, 1)}% for videos that were never saved, "
            f"based on {saved_total + unsaved_total} pitch videos on the platform so far."
        )

    return insights


def _avg_days(queryset, delta_annotation='delta'):
    """Average of a DurationField annotation, in days (None if no rows)."""
    result = queryset.aggregate(avg=Avg(delta_annotation))['avg']
    return round(result.total_seconds() / 86400, 1) if result else None


def _median_duration(queryset, delta_field='delta', unit='hours'):
    """
    Median (not mean) of a DurationField annotation — medians resist the
    one outlier who took 6 months, which is exactly the kind of skew that
    makes an average of "time to X" misleading for a small/early cohort.
    Computed in Python since percentile functions aren't portably
    available across SQLite/Postgres; fine here since this only ever runs
    over the subset of profiles that already reached that stage, not the
    whole table.
    Returns (median_value_in_unit, sample_size).
    """
    divisor = 3600 if unit == 'hours' else 86400
    seconds = [d.total_seconds() for d in queryset.values_list(delta_field, flat=True) if d is not None]
    if not seconds:
        return None, 0
    return round(statistics.median(seconds) / divisor, 1), len(seconds)


def get_time_to_value_metrics():
    """
    Cohort time-to-value: signup -> profile complete -> first Zelda use ->
    first match viewed -> first conversation -> first completed deal.
    Each stage is a median (see _median_duration) over only the profiles
    that have actually reached that stage — profiles that haven't don't
    contribute a data point, they're not counted as "0 hours."
    """
    def _role_row(label, model, vector_field, completion_time_field,
                  interest_model, interest_fk_field,
                  connection_model, connection_fk_field, connection_status):
        base = model.objects.all()

        profile_complete_qs = base.filter(**{f'{vector_field}__isnull': False}).annotate(
            delta=ExpressionWrapper(F(completion_time_field) - F('created_at'), output_field=DurationField())
        ).filter(delta__isnull=False)
        profile_complete_hours, profile_complete_n = _median_duration(profile_complete_qs, unit='hours')

        def _first_event_row(event_filter, unit):
            subquery = interest_model.objects.filter(
                **{interest_fk_field: OuterRef('pk'), **event_filter}
            ).order_by('created_at').values('created_at')[:1]
            qs = base.annotate(first_at=Subquery(subquery)).filter(first_at__isnull=False).annotate(
                delta=ExpressionWrapper(F('first_at') - F('created_at'), output_field=DurationField())
            )
            return _median_duration(qs, unit=unit)

        zelda_hours, zelda_n = _first_event_row({'event_type__in': ZELDA_EVENT_TYPES}, 'hours')
        match_hours, match_n = _first_event_row({'event_type': 'view'}, 'hours')
        conversation_days, conversation_n = _first_event_row({'event_type': 'message_sent'}, 'days')

        deal_subquery = connection_model.objects.filter(
            **{connection_fk_field: OuterRef('pk'), 'status': connection_status}
        ).order_by('updated_at').values('updated_at')[:1]
        deal_qs = base.annotate(first_deal_at=Subquery(deal_subquery)).filter(first_deal_at__isnull=False).annotate(
            delta=ExpressionWrapper(F('first_deal_at') - F('created_at'), output_field=DurationField())
        )
        deal_days, deal_n = _median_duration(deal_qs, unit='days')

        return {
            'label': label,
            'stages': [
                {'label': 'Profile Complete', 'unit': 'hours', 'median': profile_complete_hours, 'n': profile_complete_n},
                {'label': 'First Zelda Use', 'unit': 'hours', 'median': zelda_hours, 'n': zelda_n},
                {'label': 'First Match Viewed', 'unit': 'hours', 'median': match_hours, 'n': match_n},
                {'label': 'First Conversation', 'unit': 'days', 'median': conversation_days, 'n': conversation_n},
                {'label': 'First Completed Deal', 'unit': 'days', 'median': deal_days, 'n': deal_n},
            ],
        }

    rows = [
        _role_row('Founder', Application, 'description_vector', 'vector_fields_updated_at',
                  InvestorInterestEvent, 'founder_id', Connection, 'founder_id', 'FUNDED'),
        _role_row('Investor', InvestorApplication, 'focus_vector', 'updated_at',
                  InvestorInterestEvent, 'investor_id', Connection, 'investor_id', 'FUNDED'),
        _role_row('Seller', SellerApplication, 'description_vector', 'vector_fields_updated_at',
                  AcquisitionInterestEvent, 'seller_id', AcquisitionConnection, 'seller_id', 'CLOSED'),
        _role_row('Buyer', BuyerApplication, 'focus_vector', 'updated_at',
                  AcquisitionInterestEvent, 'buyer_id', AcquisitionConnection, 'buyer_id', 'CLOSED'),
    ]
    return rows


def get_conversation_speed_retention_insight():
    """
    Do founders who reach their first conversation quickly actually come
    back? Splits founders who've had at least one conversation into a
    "within 48 hours of signup" cohort and an "after 48 hours" cohort, then
    compares how many of each group logged in again at least 3 days after
    signing up (the closest "did they return" signal available without any
    new tracking). Only covers founders — that's the cohort the question
    was asked about; the same shape could be extended to other roles later.
    """
    first_conv_subquery = InvestorInterestEvent.objects.filter(
        founder_id=OuterRef('pk'), event_type='message_sent'
    ).order_by('created_at').values('created_at')[:1]

    founders_with_conversation = Application.objects.annotate(
        first_conversation_at=Subquery(first_conv_subquery)
    ).filter(first_conversation_at__isnull=False).annotate(
        delta=ExpressionWrapper(F('first_conversation_at') - F('created_at'), output_field=DurationField())
    ).select_related('user')

    fast_total = fast_returned = slow_total = slow_returned = 0
    for founder in founders_with_conversation:
        returned = bool(founder.user.last_login and founder.user.last_login >= founder.created_at + timedelta(days=3))
        if founder.delta <= timedelta(hours=48):
            fast_total += 1
            fast_returned += int(returned)
        else:
            slow_total += 1
            slow_returned += int(returned)

    def _cohort(total, returned):
        return {
            'total': total,
            'returned': returned,
            'return_rate': round((returned / total) * 100, 1) if total else None,
        }

    return {
        'within_48h': _cohort(fast_total, fast_returned),
        'after_48h': _cohort(slow_total, slow_returned),
    }


def get_marketplace_liquidity_funnel():
    """
    Where does the marketplace actually leak users? Each stage shown as a
    % of that side's starting cohort (not stage-to-stage dropoff like the
    Funnel tab) — "100 founders joined -> 65% completed profiles -> ..." is
    a more direct read on marketplace health than a chain of relative drops.
    """
    def _cohort_funnel(stages):
        first_count = stages[0][1] if stages else 0
        return [
            {
                'label': label,
                'count': count,
                'pct_of_starting_cohort': round((count / first_count) * 100, 1) if first_count else 0,
            }
            for label, count in stages
        ]

    founder_funnel = _cohort_funnel([
        ('Founders Joined', Application.objects.count()),
        ('Completed Profiles', Application.objects.filter(description_vector__isnull=False).count()),
        ('Were Viewed', Application.objects.filter(
            id__in=InvestorInterestEvent.objects.filter(event_type='view').values_list('founder_id', flat=True)
        ).count()),
        ('Received Investor Interest', Application.objects.filter(
            id__in=InvestorInterestEvent.objects.filter(event_type__in=['thumbs_up', 'intro_request']).values_list('founder_id', flat=True)
        ).count()),
        ('Conversations Started', Application.objects.filter(
            id__in=InvestorInterestEvent.objects.filter(event_type='message_sent').values_list('founder_id', flat=True)
        ).count()),
        ('Deals Completed', Application.objects.filter(
            id__in=Connection.objects.filter(status='FUNDED').values_list('founder_id', flat=True)
        ).count()),
    ])

    seller_funnel = _cohort_funnel([
        ('Sellers Joined', SellerApplication.objects.count()),
        ('Completed Listings', SellerApplication.objects.filter(description_vector__isnull=False).count()),
        ('Were Viewed', SellerApplication.objects.filter(
            id__in=AcquisitionInterestEvent.objects.filter(event_type='view').values_list('seller_id', flat=True)
        ).count()),
        ('Received Buyer Interest', SellerApplication.objects.filter(
            id__in=AcquisitionInterestEvent.objects.filter(event_type__in=['thumbs_up', 'intro_request']).values_list('seller_id', flat=True)
        ).count()),
        ('Conversations Started', SellerApplication.objects.filter(
            id__in=AcquisitionInterestEvent.objects.filter(event_type='message_sent').values_list('seller_id', flat=True)
        ).count()),
        ('Deals Completed', SellerApplication.objects.filter(
            id__in=AcquisitionConnection.objects.filter(status='CLOSED').values_list('seller_id', flat=True)
        ).count()),
    ])

    return {'founder': founder_funnel, 'seller': seller_funnel}


def get_acquisition_metrics():
    thirty_days_ago = timezone.now() - timedelta(days=30)

    registrations_by_day = {}
    for model in (Application, InvestorApplication, SellerApplication, BuyerApplication):
        for row in model.objects.filter(created_at__gte=thirty_days_ago).values('created_at__date').annotate(count=Count('id')):
            day = row['created_at__date'].isoformat()
            registrations_by_day[day] = registrations_by_day.get(day, 0) + row['count']
    registrations_sorted = sorted(registrations_by_day.items())

    # Cold-traffic source, captured first-touch on PageEvent.utm_source.
    referral_source_breakdown = list(
        PageEvent.objects.exclude(utm_source='')
        .values('utm_source')
        .annotate(count=Count('session_key', distinct=True))
        .order_by('-count')[:10]
    )

    # Organic user-to-user referrals (Fundraising CRM / Deal Pulse invites).
    organic_referral_breakdown = list(
        ReferralInvite.objects.values('source')
        .annotate(sent=Count('id'), accepted=Count('id', filter=Q(status='ACCEPTED')))
    )

    landing, started = _pre_signup_counts()
    signup_completed = PageEvent.objects.filter(event_type='signup_completed').values('session_key').distinct().count()
    landing_to_signup_rate = round((started / landing) * 100, 1) if landing else 0
    signup_to_completed_rate = round((signup_completed / started) * 100, 1) if started else 0

    return {
        'registration_labels': [d for d, _ in registrations_sorted],
        'registration_counts': [c for _, c in registrations_sorted],
        'total_new_registrations_30d': sum(registrations_by_day.values()),
        'referral_source_breakdown': referral_source_breakdown,
        'organic_referral_breakdown': organic_referral_breakdown,
        'landing_views': landing,
        'signup_started': started,
        'landing_to_signup_rate': landing_to_signup_rate,
        'signup_to_completed_rate': signup_to_completed_rate,
    }


def get_activation_metrics():
    rows = []

    def _row(label, model, vector_field, completion_time_field, interest_model, actor_fk_field, first_view_source):
        total = model.objects.count()
        complete_qs = model.objects.filter(**{f'{vector_field}__isnull': False})
        complete_count = complete_qs.count()
        completion_rate = round((complete_count / total) * 100, 1) if total else 0

        time_to_complete = _avg_days(
            complete_qs.annotate(
                delta=ExpressionWrapper(F(completion_time_field) - F('created_at'), output_field=DurationField())
            ).filter(delta__isnull=False)
        )

        # First Zelda interaction / first match viewed — earliest event date
        # per profile that has at least one such event, correlated via a
        # Subquery(OuterRef(...)) since this is a per-row "first occurrence"
        # lookup, not a simple join.
        first_zelda_subquery = interest_model.objects.filter(
            **{actor_fk_field: OuterRef('pk'), 'event_type__in': ZELDA_EVENT_TYPES}
        ).order_by('created_at').values('created_at')[:1]
        zelda_qs = model.objects.annotate(
            first_zelda=Subquery(first_zelda_subquery)
        ).filter(first_zelda__isnull=False).annotate(
            delta=ExpressionWrapper(F('first_zelda') - F('created_at'), output_field=DurationField())
        )
        avg_days_to_zelda = _avg_days(zelda_qs)

        first_match_subquery = interest_model.objects.filter(
            **{actor_fk_field: OuterRef('pk'), 'event_type': 'view'}
        ).order_by('created_at').values('created_at')[:1]
        match_qs = model.objects.annotate(
            first_match=Subquery(first_match_subquery)
        ).filter(first_match__isnull=False).annotate(
            delta=ExpressionWrapper(F('first_match') - F('created_at'), output_field=DurationField())
        )
        avg_days_to_match = _avg_days(match_qs)

        rows.append({
            'label': label,
            'total': total,
            'complete_count': complete_count,
            'completion_rate': completion_rate,
            'avg_days_to_complete': time_to_complete,
            'avg_days_to_first_zelda': avg_days_to_zelda,
            'avg_days_to_first_match_viewed': avg_days_to_match,
        })

    _row('Founder', Application, 'description_vector', 'vector_fields_updated_at', InvestorInterestEvent, 'founder_id', 'founder')
    _row('Investor', InvestorApplication, 'focus_vector', 'updated_at', InvestorInterestEvent, 'investor_id', 'investor')
    _row('Seller', SellerApplication, 'description_vector', 'vector_fields_updated_at', AcquisitionInterestEvent, 'seller_id', 'seller')
    _row('Buyer', BuyerApplication, 'focus_vector', 'updated_at', AcquisitionInterestEvent, 'buyer_id', 'buyer')

    return rows


def get_engagement_metrics():
    week_ago = timezone.now() - timedelta(days=7)

    wau = {
        'founder': User.objects.filter(last_login__gte=week_ago, match_founder_profile__isnull=False).count(),
        'investor': User.objects.filter(last_login__gte=week_ago, match_investor_profile__isnull=False).count(),
        'seller': User.objects.filter(last_login__gte=week_ago, match_seller_profile__isnull=False).count(),
        'buyer': User.objects.filter(last_login__gte=week_ago, match_buyer_profile__isnull=False).count(),
    }

    recent_searches = SearchEvent.objects.filter(created_at__gte=week_ago)
    total_searches = recent_searches.count()
    distinct_searchers = recent_searches.exclude(user__isnull=True).values('user').distinct().count()
    searches_per_user = round(total_searches / distinct_searchers, 1) if distinct_searchers else 0

    matches_viewed_7d = (
        InvestorInterestEvent.objects.filter(event_type='view', created_at__gte=week_ago).count()
        + AcquisitionInterestEvent.objects.filter(event_type='view', created_at__gte=week_ago).count()
    )

    messages_initiated_7d = MessageThread.objects.filter(created_at__gte=week_ago).count()
    messages_initiated_total = MessageThread.objects.count()

    return {
        'wau': wau,
        'total_searches_7d': total_searches,
        'distinct_searchers_7d': distinct_searchers,
        'searches_per_user_7d': searches_per_user,
        'matches_viewed_7d': matches_viewed_7d,
        'messages_initiated_7d': messages_initiated_7d,
        'messages_initiated_total': messages_initiated_total,
    }


def get_value_creation_metrics():
    introductions_made = Connection.objects.count() + AcquisitionConnection.objects.count()

    # "Meetings scheduled" isn't trackable — there's no calendar feature —
    # so this counts actual message_sent events as an honest proxy instead.
    conversations_started = (
        InvestorInterestEvent.objects.filter(event_type='message_sent').count()
        + AcquisitionInterestEvent.objects.filter(event_type='message_sent').count()
    )

    funding_conversations = Connection.objects.filter(status='ACCEPTED').count()
    acquisition_conversations = AcquisitionConnection.objects.filter(status='ACCEPTED').count()
    completed_deals = (
        Connection.objects.filter(status='FUNDED').count()
        + AcquisitionConnection.objects.filter(status='CLOSED').count()
    )

    return {
        'introductions_made': introductions_made,
        'conversations_started': conversations_started,
        'funding_conversations': funding_conversations,
        'acquisition_conversations': acquisition_conversations,
        'completed_deals': completed_deals,
    }


def get_feature_adoption_metrics():
    founder_count = Application.objects.count()
    seller_count = SellerApplication.objects.count()

    def _feature_row(label, adopted_count, eligible_count):
        adoption_pct = round((adopted_count / eligible_count) * 100, 1) if eligible_count else 0
        return {
            'label': label,
            'adopted_count': adopted_count,
            'eligible_count': eligible_count,
            'adoption_pct': adoption_pct,
            'ignored_pct': round(100 - adoption_pct, 1) if eligible_count else 0,
        }

    zelda_adopted = (
        Application.objects.filter(
            id__in=InvestorInterestEvent.objects.filter(event_type__in=ZELDA_EVENT_TYPES).values_list('founder_id', flat=True)
        ).count()
        + SellerApplication.objects.filter(
            id__in=AcquisitionInterestEvent.objects.filter(event_type__in=ZELDA_EVENT_TYPES).values_list('seller_id', flat=True)
        ).count()
    )

    match_list_adopted = PageEvent.objects.filter(event_type='dashboard_view').exclude(user__isnull=True).values('user').distinct().count()
    match_list_eligible = founder_count + InvestorApplication.objects.count()

    pitch_deck_adopted = Application.objects.exclude(pitch_deck='').count()
    milestones_adopted = Application.objects.filter(milestones__isnull=False).distinct().count()
    valuation_adopted = Application.objects.filter(
        user__in=DocumentSource.objects.filter(valuation_report__isnull=False).values_list('uploaded_by', flat=True)
    ).count()

    return [
        _feature_row('Used Zelda (analysis/memo/truth delta)', zelda_adopted, founder_count + seller_count),
        _feature_row('Viewed match list', match_list_adopted, match_list_eligible),
        _feature_row('Uploaded pitch deck', pitch_deck_adopted, founder_count),
        _feature_row('Created a milestone', milestones_adopted, founder_count),
        _feature_row('Used valuation reports', valuation_adopted, founder_count),
    ]
