# zelda_api/entity_verification_tasks.py
"""Celery tasks for Entity Integrity — see zelda_api/entity_verification.py."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


# WHOIS and website fetches talk to third-party servers that can accept a
# connection and then never answer, so every check needs a ceiling or one bad
# host pins a worker indefinitely. The website fetch has its own timeouts
# (safe_fetch.py); soft_time_limit raises SoftTimeLimitExceeded inside the task
# as the backstop, and a report left pending by it stops being shared after
# entity_verification.PENDING_SHARE_WINDOW.
@shared_task(soft_time_limit=60, time_limit=90)
def run_entity_check(report_id):
    from .entity_verification import run_identity_check
    from .entity_verification_models import EntityVerificationReport

    report = EntityVerificationReport.objects.filter(pk=report_id).first()
    if report is None:
        logger.error(f"[Entity Integrity] Report {report_id} not found")
        return {'status': 'error', 'error': 'Report not found'}
    run_identity_check(report)
    return {'status': 'success', 'report_id': report.id}


@shared_task(soft_time_limit=60, time_limit=90)
def verify_entity_integrity(document_id):
    """The owner's Truth Delta Verify button: check the business the document belongs to."""
    from .vector_models import DocumentSource
    from .entity_verification import build_entity_verification_report, identity_check_now, subject_for_document

    try:
        document = DocumentSource.objects.get(id=document_id)
    except DocumentSource.DoesNotExist:
        logger.error(f"[Entity Integrity] Document {document_id} not found")
        return {'status': 'error', 'error': 'Document not found'}

    subject = subject_for_document(document)
    if subject is None:
        # An uploader with no business profile still gets the original domain-age report.
        report = build_entity_verification_report(document)
        report.save()
    else:
        report = identity_check_now(subject, document=document)

    return {'status': 'success', 'document_id': document_id, 'report_id': report.id}
