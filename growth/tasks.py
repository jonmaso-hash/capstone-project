import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import Count
from django.utils import timezone
from django.utils.text import slugify

logger = logging.getLogger(__name__)

STAGE_ORDER = ['Pre-Seed', 'Seed', 'Series A', 'Series B', 'Series C']


def _median(values):
    if not values:
        return None
    values = sorted(values)
    n = len(values)
    mid = n // 2
    if n % 2 == 0:
        return (values[mid - 1] + values[mid]) / 2
    return values[mid]


def _quarter_label(reference_date):
    quarter = (reference_date.month - 1) // 3 + 1
    return f"Q{quarter} {reference_date.year}"


def _compute_insight_sections():
    """
    Aggregated, anonymized stats only — never per-user data. Reuses the
    same pure-queryset-aggregation style as matchmaking/analytics.py
    (no per-user Python loops beyond the bounded FUNDED-connection
    duration calc, which Django's ORM can't compute cross-backend).
    """
    from matchmaking.models import Application, Connection

    now = timezone.now()
    quarter_start = now - timedelta(days=90)

    recent_founders = Application.objects.filter(created_at__gte=quarter_start)

    top_sectors = list(
        recent_founders.exclude(sector='').values('sector').annotate(count=Count('id')).order_by('-count')[:5]
    )
    sectors_text = ', '.join(f"{row['sector']} ({row['count']})" for row in top_sectors) or 'Not enough data yet.'

    stage_medians = []
    for stage_key in STAGE_ORDER:
        amounts = list(
            recent_founders.filter(stage__iexact=stage_key).exclude(raising_amount=0)
            .values_list('raising_amount', flat=True)
        )
        median = _median([float(a) for a in amounts])
        if median is not None:
            stage_medians.append(f"{stage_key}: ${median:,.0f}")
    medians_text = '; '.join(stage_medians) or 'Not enough data yet.'

    funded = Connection.objects.filter(status='FUNDED', updated_at__gte=quarter_start)
    durations = [(c.updated_at - c.created_at).days for c in funded]
    avg_days = round(sum(durations) / len(durations), 1) if durations else None
    time_to_funded_text = (
        f"{avg_days} days from first connection to funded, on average." if avg_days is not None
        else "Not enough data yet."
    )

    return [
        {'heading': 'Most Active Sectors', 'text': sectors_text},
        {'heading': 'Median Raise by Stage', 'text': medians_text},
        {'heading': 'Time to Funded', 'text': time_to_funded_text},
    ]


@shared_task
def generate_quarterly_insight_report():
    """
    Content-marketing data drop — aggregated deal-flow stats only.
    Created as an unpublished draft; staff review and toggle is_published
    from the ops Insight Reports page before anything goes public.
    """
    from .models import PlatformInsightReport

    now = timezone.now()
    period_label = _quarter_label(now)

    if PlatformInsightReport.objects.filter(period_label=period_label).exists():
        return {'status': 'skipped', 'reason': 'already generated this quarter'}

    period_slug = slugify(f"{period_label}-{now.strftime('%Y%m%d')}")
    sections = _compute_insight_sections()

    PlatformInsightReport.objects.create(
        title=f"The Interlink Foundry {period_label} Deal Flow Report",
        period_label=period_label,
        period_slug=period_slug,
        body_sections=sections,
        is_published=False,
    )
    logger.info(f"Generated quarterly insight report draft for {period_label}")
    return {'status': 'success', 'period_label': period_label}
