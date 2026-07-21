# zelda_api/entity_verification_tasks.py
"""Celery task for Entity Integrity verification — runs alongside Truth Delta's own verify task."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


# WHOIS talks to third-party registry servers that can accept a connection and
# then never answer, so the call needs a ceiling or one bad domain pins a worker
# indefinitely. soft_time_limit raises SoftTimeLimitExceeded (an ordinary
# Exception) inside the task, which lookup_domain_creation_date's except block
# catches like any other failure -- so a hung lookup degrades to "Domain lookup
# unavailable right now." and the report still saves. time_limit is the hard
# backstop if something hangs outside that handler.
@shared_task(soft_time_limit=30, time_limit=45)
def verify_entity_integrity(document_id):
    from .vector_models import DocumentSource
    from .entity_verification import build_entity_verification_report

    try:
        document = DocumentSource.objects.get(id=document_id)
    except DocumentSource.DoesNotExist:
        logger.error(f"[Entity Integrity] Document {document_id} not found")
        return {'status': 'error', 'error': 'Document not found'}

    report = build_entity_verification_report(document)
    report.save()

    return {'status': 'success', 'document_id': document_id, 'report_id': report.id}