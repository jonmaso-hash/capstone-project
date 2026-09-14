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


@shared_task
def delete_stored_file(name):
    """
    Retry for an uploaded file whose removal after a deletion failed (see
    shared_utils/file_cleanup.py). Requeued from the ops Failed Tasks page.
    Safe to run again: deleting a file that is already gone does nothing.
    """
    from django.core.files.storage import default_storage

    default_storage.delete(name)


@shared_task
def delete_stream_user(stream_user_id):
    """
    Retry for a Stream Chat identity whose removal after an account deletion
    failed (see accounts/deletion.py). Requeued from the ops Failed Tasks page.
    """
    from .deletion import remove_stream_identity

    remove_stream_identity(stream_user_id)
