# matchmaking/insights_engine.py
"""
Turns the interest-event stream (InvestorInterestEvent / AcquisitionInterestEvent
— identical event-type vocabulary, so every function here works unmodified
against either queryset) into the Premium-gated "Founder Insights" /
"Seller Insights" analytics: a funnel, week-over-week trending, a composite
marketplace score, conversion rates, opportunity alerts, next-best-action
recommendations, a privacy-preserving interest timeline, and a few
templated narrative insights. All aggregate-only, same convention as
growth_metrics.py's get_profile_trust_badges — never surfaces a single
viewer's identity or exact per-viewer behavior.

One deliberate scope limit, called out here so it doesn't get silently
reinvented: a true cross-role "who's viewing me" breakdown (founders vs.
investors vs. buyers vs. sellers all viewing ONE profile) is NOT
buildable from today's schema. InvestorInterestEvent only ever connects
an investor to a founder, and AcquisitionInterestEvent only a buyer to a
seller — there's no relationship model for a founder or seller viewing
another founder's profile, so every recorded viewer of a founder's
profile already IS an investor by construction. get_investor_focus_breakdown
/ get_buyer_deal_structure_breakdown answer the more useful real question
instead: WHICH investors/buyers (by stage/sector/deal-structure), not
THAT they're investors/buyers. A genuine cross-role breakdown would need
new instrumentation on the profile-view code path itself, capturing every
viewer's role regardless of relationship type — a bigger change than
this analytics layer, and out of scope here.
"""
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

# Ordered funnel stages — each a real event_type both interest-event
# models share. Not a strict linear funnel in reality (a viewer can
# message without a thumbs-up), but ordering it this way mirrors the
# actual intent-escalation path most engaged visitors follow.
FUNNEL_STAGES = [
    ('view', 'Profile Views'),
    ('memo_view', 'Memo Views'),
    ('truth_delta_view', 'Truth Delta Views'),
    ('thumbs_up', 'Thumbs Up'),
    ('intro_request', 'Intro Requests'),
    ('message_sent', 'Messages'),
]

TIMELINE_EVENT_LABELS = {
    'view': 'Profile viewed',
    'memo_view': 'Memo opened',
    'truth_delta_view': 'Truth Delta viewed',
    'analyze': 'Analyzed with Zelda',
    'thumbs_up': 'Thumbs up received',
    'intro_request': 'Introduction requested',
    'message_sent': 'Message sent',
}
TIMELINE_EVENT_TYPES = list(TIMELINE_EVENT_LABELS.keys())

# Tuning constants for the composite score — see get_engagement_score.
VISIBILITY_VIEWS_FOR_MAX_SCORE = 50
INTEREST_RATE_FOR_MAX_SCORE = 0.5  # (thumbs_up + intro_requests) / views
STALE_PROFILE_DAYS = 45
REPEAT_VIEWER_ALERT_THRESHOLD = 3  # same investor/buyer viewing the memo this many times this week


def get_funnel_stats(events_qs):
    """
    [{'event_type', 'label', 'count', 'drop_pct'}, ...] in FUNNEL_STAGES
    order. drop_pct is the percentage lost from the previous stage (None
    for the first stage, or when the previous stage was zero).
    """
    stages = []
    previous_count = None
    for event_type, label in FUNNEL_STAGES:
        count = events_qs.filter(event_type=event_type).count()
        drop_pct = None
        if previous_count is not None and previous_count > 0:
            drop_pct = round((1 - count / previous_count) * 100)
        stages.append({'event_type': event_type, 'label': label, 'count': count, 'drop_pct': drop_pct})
        previous_count = count
    return stages


def get_conversion_rates(funnel_stats):
    """
    Named conversion rates between the funnel's meaningful gates —
    View -> Memo, Memo -> Truth Delta, Truth Delta -> Intro,
    Intro -> Message (skips the thumbs-up stage, which isn't a gate on
    its own). None where the earlier stage is zero.
    """
    counts = {row['event_type']: row['count'] for row in funnel_stats}

    def _rate(from_type, to_type):
        base = counts.get(from_type, 0)
        return round(counts.get(to_type, 0) / base * 100) if base else None

    return {
        'view_to_memo': _rate('view', 'memo_view'),
        'memo_to_truth_delta': _rate('memo_view', 'truth_delta_view'),
        'truth_delta_to_intro': _rate('truth_delta_view', 'intro_request'),
        'intro_to_message': _rate('intro_request', 'message_sent'),
    }


def get_trending_stats(events_qs, event_type='view'):
    """
    {'today': {...}, 'last_7_days': {...}, 'last_30_days': {...}}, each
    {'current': int, 'pct_change': int|None} — pct_change compares the
    window to the equal-length window immediately before it (e.g. this
    7 days vs. the 7 days before that), None when the prior window was
    zero (a percentage off a zero baseline is meaningless, not "infinite%").
    """
    now = timezone.now()
    windows = [('today', timedelta(days=1)), ('last_7_days', timedelta(days=7)), ('last_30_days', timedelta(days=30))]
    result = {}
    for label, window in windows:
        current = events_qs.filter(event_type=event_type, created_at__gte=now - window).count()
        previous = events_qs.filter(
            event_type=event_type, created_at__gte=now - (window * 2), created_at__lt=now - window,
        ).count()
        pct_change = round((current - previous) / previous * 100) if previous > 0 else None
        result[label] = {'current': current, 'pct_change': pct_change}
    return result


def get_multi_metric_trends(events_qs, event_types=('view', 'memo_view', 'truth_delta_view')):
    """
    {event_type: {'label', 'pct_change', 'pct_change_abs'}} — the compact
    "Views +42% / Memo Opens +19% / Truth Delta Views -11%" trend-arrow
    row. Reuses get_trending_stats' last_7_days window per metric.
    pct_change_abs exists only because Django templates have no built-in
    abs filter — the template shows it next to a down-arrow when negative
    rather than a literal "-11%".
    """
    labels = dict(FUNNEL_STAGES)
    result = {}
    for event_type in event_types:
        pct_change = get_trending_stats(events_qs, event_type=event_type)['last_7_days']['pct_change']
        result[event_type] = {
            'label': labels.get(event_type, event_type),
            'pct_change': pct_change,
            'pct_change_abs': abs(pct_change) if pct_change is not None else None,
        }
    return result


def _completion_percentage(role_profile):
    """Reuses Application's real completion_percentage property; seller has no
    equivalent property, so a small ad-hoc equivalent is computed inline."""
    if hasattr(role_profile, 'completion_percentage'):
        return role_profile.completion_percentage
    tracked_fields = [
        role_profile.description, role_profile.industry, role_profile.cim_document,
        role_profile.pitch_video, role_profile.asking_price,
    ]
    filled = sum(1 for field in tracked_fields if field)
    return round(filled / len(tracked_fields) * 100)


def get_engagement_score(funnel_stats, role_profile):
    """
    0-100 composite ("Marketplace Score") from four independently 0-100
    sub-scores:
      - visibility: raw view volume, saturating at VISIBILITY_VIEWS_FOR_MAX_SCORE
      - interest: (thumbs_up + intro_requests) / views, saturating at INTEREST_RATE_FOR_MAX_SCORE
      - trust: verification status + profile completion
      - responsiveness: messages / intro_requests (how often an intro leads to a conversation)
    Deliberately NOT a percentile against other founders/sellers (see this
    module's docstring on cross-role/cohort limits) — a self-contained
    score, not a claimed ranking.
    """
    counts = {row['event_type']: row['count'] for row in funnel_stats}
    views = counts.get('view', 0)
    thumbs_up = counts.get('thumbs_up', 0)
    intro_requests = counts.get('intro_request', 0)
    messages = counts.get('message_sent', 0)

    visibility = min(100, round(views / VISIBILITY_VIEWS_FOR_MAX_SCORE * 100))
    interest_rate = (thumbs_up + intro_requests) / views if views else 0
    interest = min(100, round(interest_rate / INTEREST_RATE_FOR_MAX_SCORE * 100))
    trust = round(((100 if getattr(role_profile, 'is_verified', False) else 40) + _completion_percentage(role_profile)) / 2)
    responsiveness = min(100, round(messages / intro_requests * 100)) if intro_requests else 0

    overall = round((visibility + interest + trust + responsiveness) / 4)
    return {'overall': overall, 'visibility': visibility, 'interest': interest, 'trust': trust, 'responsiveness': responsiveness}


def get_strengths_and_improvements(engagement_score, role_profile):
    """
    Templated bullet lists driven by the same sub-scores shown on the
    score card, so the copy can never claim something the numbers don't
    back up. Capped at 3 each to stay skimmable.
    """
    strengths, improvements = [], []

    if engagement_score['visibility'] >= 70:
        strengths.append("High visibility — your profile is getting seen.")
    elif engagement_score['visibility'] < 30:
        improvements.append("Boost visibility — a complete pitch deck and video meaningfully increase views.")

    if engagement_score['interest'] >= 60:
        strengths.append("Strong investor interest relative to your view count.")
    elif engagement_score['interest'] < 20:
        improvements.append("Add traction data — interest relative to views is below average.")

    if engagement_score['trust'] >= 80:
        strengths.append("Strong profile completion and verification.")
    else:
        if not getattr(role_profile, 'is_verified', False):
            improvements.append("Complete business-email verification to build trust with viewers.")
        if _completion_percentage(role_profile) < 80:
            improvements.append("Finish filling out your profile — incomplete fields hurt credibility.")

    if engagement_score['responsiveness'] >= 70:
        strengths.append("Above-average responsiveness to introduction requests.")
    elif engagement_score['responsiveness'] == 0:
        pass  # no intro requests yet at all — nothing meaningful to say about responsiveness

    return {'strengths': strengths[:3], 'improvements': improvements[:3]}


def get_interest_timeline(events_qs, limit=12):
    """
    Chronological (newest first) list of the visitor-intent events for
    this profile — [{'label', 'created_at'}, ...]. No viewer identity at
    all, by design: this answers "is interest building or fading", not
    "who specifically is interested."
    """
    events = events_qs.filter(event_type__in=TIMELINE_EVENT_TYPES).order_by('-created_at')[:limit]
    return [
        {'label': TIMELINE_EVENT_LABELS.get(event.event_type, event.get_event_type_display()), 'created_at': event.created_at}
        for event in events
    ]


def get_ai_insights(funnel_stats, trending_stats):
    """
    A handful of templated, threshold-driven observations from the real
    numbers above — never a fabricated claim. Order: data-availability
    guard first, then whichever thresholds actually fire, capped so the
    list stays skimmable.
    """
    counts = {row['event_type']: row['count'] for row in funnel_stats}
    views = counts.get('view', 0)

    if views == 0:
        return ["Your profile hasn't been viewed yet — a complete pitch deck and video meaningfully improve visibility."]

    insights = []

    memo_stage = next(row for row in funnel_stats if row['event_type'] == 'memo_view')
    if memo_stage['drop_pct'] is not None and memo_stage['drop_pct'] >= 50:
        insights.append(f"Most visitors leave before opening your memo — a {memo_stage['drop_pct']}% drop-off from profile view to memo view.")

    truth_delta_stage = next(row for row in funnel_stats if row['event_type'] == 'truth_delta_view')
    if truth_delta_stage['count'] == 0 and memo_stage['count'] > 0:
        insights.append("Your Truth Delta report has not been viewed by anyone yet.")

    week = trending_stats.get('last_7_days', {})
    if week.get('pct_change') is not None and week['pct_change'] >= 20:
        insights.append(f"Your profile views are up {week['pct_change']}% over the last week.")
    elif week.get('pct_change') is not None and week['pct_change'] <= -20:
        insights.append(f"Your profile views are down {abs(week['pct_change'])}% over the last week.")

    thumbs_up = counts.get('thumbs_up', 0)
    if views and thumbs_up / views >= 0.15:
        insights.append("Your thumbs-up rate is strong relative to your view count — people who look are engaging.")

    intro_requests = counts.get('intro_request', 0)
    if thumbs_up > 0 and intro_requests / thumbs_up < 0.3:
        insights.append("Many visitors give a thumbs-up but stop short of requesting an introduction — tightening your ask may help convert interest.")

    if not insights:
        insights.append("Keep building engagement — insights sharpen as more people interact with your profile.")
    return insights[:4]


def get_opportunity_alerts(funnel_stats, trending_stats, events_qs, role_profile):
    """
    "Something changed, come look" alerts — distinct from get_ai_insights
    (which summarizes overall standing): alerts are time-boxed and
    designed to bring someone back to the page. Repeat-viewer detection
    stays fully anonymous (a count of repeat views, never which viewer).
    """
    alerts = []
    today = get_trending_stats(events_qs, 'view')['today']
    if today['current'] > 0:
        alerts.append(f"Your profile has received {today['current']} investor view{'s' if today['current'] != 1 else ''} today.")

    week = trending_stats.get('last_7_days', {})
    if week.get('pct_change') is not None and week['pct_change'] >= 20:
        alerts.append("Your profile is trending higher than last week.")

    week_start = timezone.now() - timedelta(days=7)
    viewer_field = 'investor_id' if hasattr(events_qs.model, 'investor') else 'buyer_id'
    repeat_viewer = (
        events_qs.filter(event_type='memo_view', created_at__gte=week_start)
        .values(viewer_field).annotate(n=Count('id')).filter(n__gte=REPEAT_VIEWER_ALERT_THRESHOLD)
        .exists()
    )
    if repeat_viewer:
        alerts.append(f"Someone viewed your memo {REPEAT_VIEWER_ALERT_THRESHOLD}+ times this week.")

    counts = {row['event_type']: row['count'] for row in funnel_stats}
    if counts.get('memo_view', 0) > 0 and counts.get('truth_delta_view', 0) == 0:
        alerts.append("Your Truth Delta report has not been viewed by anyone yet.")

    if getattr(role_profile, 'updated_at', None):
        days_stale = (timezone.now() - role_profile.updated_at).days
        if days_stale >= STALE_PROFILE_DAYS:
            alerts.append(f"Your profile hasn't been updated in {days_stale} days.")

    return alerts


def get_recommendations(funnel_stats, role_profile):
    """
    Ranked Next-Best-Action list — each backed by a real, checkable
    condition (profile fields or funnel drop-off), never generic advice.
    'impact' is a simple heuristic (missing trust-building fields rank
    High; funnel-tuning suggestions rank Medium) rather than anything
    measured, and is labeled as such in the UI.
    """
    recommendations = []
    counts = {row['event_type']: row['count'] for row in funnel_stats}

    if not getattr(role_profile, 'is_verified', False):
        recommendations.append({
            'action': 'Complete Verification', 'impact': 'High',
            'reason': 'Verified profiles receive more introduction requests.',
        })

    has_deck_or_video = bool(getattr(role_profile, 'pitch_deck', None) or getattr(role_profile, 'pitch_video', None)
                              or getattr(role_profile, 'cim_document', None))
    if not has_deck_or_video:
        recommendations.append({
            'action': 'Upload a Pitch Deck or Video', 'impact': 'High',
            'reason': 'Profiles without pitch materials get far fewer memo opens.',
        })

    memo_stage = next(row for row in funnel_stats if row['event_type'] == 'memo_view')
    if memo_stage['drop_pct'] is not None and memo_stage['drop_pct'] >= 50:
        recommendations.append({
            'action': 'Upload Updated Financials', 'impact': 'Medium',
            'reason': 'Visitors viewed your profile but rarely open your memo — sharper traction data can close that gap.',
        })

    if counts.get('memo_view', 0) > 0 and counts.get('truth_delta_view', 0) == 0:
        recommendations.append({
            'action': 'Highlight Verifiable Claims', 'impact': 'Medium',
            'reason': 'Visitors open your memo but never check Truth Delta — your claims may not be prominent enough to invite scrutiny.',
        })

    if _completion_percentage(role_profile) < 80:
        recommendations.append({
            'action': 'Finish Your Profile', 'impact': 'Medium',
            'reason': 'Incomplete profiles rank lower in search and match results.',
        })

    return recommendations[:4]


def get_investor_focus_breakdown(events_qs):
    """
    Founder-only: breaks down the UNIQUE investors who viewed this profile
    by their stated investment_stage/investment_focus — aggregate counts
    only, never which investor. See this module's docstring for why a
    role-based (founder/investor/buyer/seller) split isn't meaningful
    here — every recorded viewer already IS an investor by construction.
    """
    from .models import InvestorApplication

    viewer_user_ids = events_qs.filter(event_type='view').values_list('investor_id', flat=True).distinct()
    profiles = InvestorApplication.objects.filter(user_id__in=viewer_user_ids)
    by_stage = dict(
        profiles.exclude(investment_stage='').values('investment_stage')
        .annotate(n=Count('id')).values_list('investment_stage', 'n')
    )
    by_focus = dict(
        profiles.exclude(investment_focus='').values('investment_focus')
        .annotate(n=Count('id')).values_list('investment_focus', 'n')
    )
    return {'unique_viewers': profiles.count(), 'by_stage': by_stage, 'by_focus': by_focus}


def get_buyer_deal_structure_breakdown(events_qs):
    """
    Seller-only mirror of get_investor_focus_breakdown: breaks down the
    unique buyers who viewed this listing by preferred_deal_structure —
    the one clean categorical field BuyerApplication has (budget_min/max
    are numeric ranges, not a bucketable category worth inventing here).
    """
    from .models import BuyerApplication

    viewer_user_ids = events_qs.filter(event_type='view').values_list('buyer_id', flat=True).distinct()
    profiles = BuyerApplication.objects.filter(user_id__in=viewer_user_ids)
    by_deal_structure = dict(
        profiles.values('preferred_deal_structure')
        .annotate(n=Count('id')).values_list('preferred_deal_structure', 'n')
    )
    return {'unique_viewers': profiles.count(), 'by_deal_structure': by_deal_structure}
