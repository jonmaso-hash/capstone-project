# matchmaking/funnel.py
"""
Rolls up counts across the digest -> subscription funnel for a rolling
window. Deliberately simple aggregate counts per stage, not per-user
multi-touch attribution — attribution is a much harder problem to get
right, and there's no evidence yet that stage counts alone won't already
answer the real question: is any of this converting at all. Once these
numbers show where the drop-off actually is, that's the point to invest
in richer attribution for that specific stage.

Every stage here reuses a model that already existed for its own reason
(DigestEngagementEvent is the one genuinely new piece this added) rather
than introducing a parallel event log.
"""
from datetime import timedelta

from django.utils import timezone


def funnel_summary(days=7):
    """
    intros_sent counts Connection, not ConnectionRequest: ConnectionRequest
    is a separate, differently-shaped model that nothing in the app ever
    creates (request_intro/request_intro_from_founder both create
    Connection rows) — counting it would silently return zero forever, an
    incorrect metric that's worse than no metric at all.

    deal_rooms_created has the same class of problem: the DealRoom model
    is never instantiated outside tests — the real chat channel is created
    client-side (matchmaking.js -> Stream Chat) the moment a Connection
    reaches status='ACCEPTED', with no server-side record of that event.
    Counting accepted connections in the window is the closest available
    proxy for "a deal room became accessible," not a literal DealRoom count.
    """
    from .models import DigestEngagementEvent, InvestorInterestEvent, Connection
    from zelda_api.vector_models import DocumentSource
    from billing.models import Subscription

    window_start = timezone.now() - timedelta(days=days)

    events = DigestEngagementEvent.objects.filter(created_at__gte=window_start)
    digests_sent = events.filter(event_type='sent').count()
    digests_opened = events.filter(event_type='opened').count()
    digests_clicked = events.filter(event_type='clicked').count()

    profile_views = InvestorInterestEvent.objects.filter(event_type='view', created_at__gte=window_start).count()
    analyses_generated = DocumentSource.objects.filter(created_at__gte=window_start).exclude(status='error').count()
    subscriptions_started = Subscription.objects.filter(created_at__gte=window_start, status=Subscription.Status.ACTIVE).count()
    intros_sent = Connection.objects.filter(created_at__gte=window_start).count()
    deal_rooms_created = Connection.objects.filter(status='ACCEPTED', updated_at__gte=window_start).count()

    def rate(numerator, denominator):
        return round(numerator / denominator * 100, 1) if denominator else None

    return {
        'window_days': days,
        'digests_sent': digests_sent,
        'digests_opened': digests_opened,
        'digests_clicked': digests_clicked,
        'open_rate_pct': rate(digests_opened, digests_sent),
        'click_rate_pct': rate(digests_clicked, digests_sent),
        'profile_views': profile_views,
        'analyses_generated': analyses_generated,
        'subscriptions_started': subscriptions_started,
        'intros_sent': intros_sent,
        'deal_rooms_created': deal_rooms_created,
    }
