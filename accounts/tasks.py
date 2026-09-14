from celery import shared_task
from django.utils import timezone


@shared_task
def prune_rate_limit_events():
    """
    Deletes counted rate-limit attempts older than accounts.rate_limits.RETENTION
    -- long past every limit's window -- so the table stays small. Runs daily
    from CELERY_BEAT_SCHEDULE. Returns how many rows were deleted.
    """
    from .models import RateLimitEvent
    from .rate_limits import RETENTION

    deleted, _ = RateLimitEvent.objects.filter(created_at__lt=timezone.now() - RETENTION).delete()
    return deleted
