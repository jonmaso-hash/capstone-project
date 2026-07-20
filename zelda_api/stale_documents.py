# zelda_api/stale_documents.py
"""
Detects DocumentSource rows stuck mid-pipeline — queued or partway through
chunking/embedding/analyzing for longer than STALE_THRESHOLD_MINUTES with no
error recorded. This is exactly the failure mode that let a real valuation
silently never appear: no Celery worker was consuming the queue, so the
document sat at status='ingested' forever with nothing in FailedTaskLog —
that log only fires on an actual task *exception*, not an absence. A
periodic scan is the only way to surface "nothing ever ran" at all. See
ops/views.py::failed_tasks for the sibling "task actually ran and failed"
case this doesn't overlap with.
"""
from datetime import timedelta

from django.utils import timezone

# Every non-terminal status a document can sit in mid-pipeline — 'analyzed'
# and 'error' are terminal outcomes, deliberately excluded.
PENDING_STATUSES = ['ingested', 'chunking', 'chunked', 'embedding', 'embedded', 'analyzing']
STALE_THRESHOLD_MINUTES = 5


def find_stale_documents(threshold_minutes=STALE_THRESHOLD_MINUTES):
    """DocumentSource queryset, oldest-stuck-first — updated_at (not
    created_at) is what matters, since that's the last time this document's
    status actually changed."""
    from .vector_models import DocumentSource

    cutoff = timezone.now() - timedelta(minutes=threshold_minutes)
    return DocumentSource.objects.filter(
        status__in=PENDING_STATUSES, updated_at__lt=cutoff,
    ).select_related('uploaded_by').order_by('updated_at')
