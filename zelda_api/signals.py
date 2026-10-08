# zelda_api/signals.py
"""
Django signals for Zelda Intelligence Pipeline.
Automatically triggers pipeline when documents are uploaded or created.
"""
import logging
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from .vector_models import DocumentSource, IntelligenceMemo, BusinessValuationReport
from .truth_delta_models import TruthDeltaReport
from .tasks import process_document_pipeline

logger = logging.getLogger(__name__)


@receiver(post_save, sender=DocumentSource)
def trigger_document_processing(sender, instance, created, **kwargs):
    """
    Signal handler: When a DocumentSource is created, queue it for pipeline processing.
    Pipeline is triggered explicitly by pipeline_views.py to avoid double processing.
    """
    if created:
        logger.info(f"DocumentSource created: {instance.filename}")
        # NOTE: Pipeline is intentionally NOT queued here.
        # pipeline_views.py calls process_document_pipeline.delay() directly
        # after extracting the full text from the uploaded file.
        # Queuing here would cause double processing.

@receiver(post_save, sender=DocumentSource)
def handle_document_error(sender, instance, created, update_fields, **kwargs):
    """
    Signal handler: Monitor for pipeline errors.
    Alerts or retries when documents fail processing.
    """
    if not created and instance.status == 'error':
        logger.error(f"Document {instance.filename} status is ERROR")
        logger.error(f"Error message: {instance.error_message}")

        # The user is told on the report page while they are watching it, but
        # nothing durable existed for someone who had already closed the tab.
        # This is that durable signal.
        #
        # No retry here: the pipeline tasks in tasks.py already retry with
        # exponential backoff and only reach status='error' once retries are
        # exhausted, so retrying from a post_save would re-run work that has
        # already been given up on.
        from .terminal_notifications import notify_terminal_state
        notify_terminal_state(instance, succeeded=False)


def _archive_generated_report(document, key, size_bytes):
    from matchmaking.data_room_quota import try_save_report
    if document.is_product_input or document.analysis_orders.exists() or document.valuation_orders.exists():
        return  # Paid clones are archived together with their order after fulfillment.
    try:
        try_save_report(document.uploaded_by, 'document', document.pk, key, size_bytes)
    except Exception:
        logger.exception('Could not save Zelda report %s for document %s in Data Room', key, document.pk)


@receiver(post_save, sender=IntelligenceMemo)
def archive_generated_memo(sender, instance, **kwargs):
    document = instance.document
    if document.document_type != 'pitch_deck' or document.is_external_subject:
        return
    size = sum(len((getattr(instance, field.name) or '').encode('utf-8'))
               for field in instance._meta.fields if isinstance(field, models.TextField))
    _archive_generated_report(document, 'memo', size)


@receiver(post_save, sender=TruthDeltaReport)
def archive_generated_evidence(sender, instance, **kwargs):
    import json
    size = len((instance.summary or '').encode('utf-8')) + len(json.dumps(instance.details).encode('utf-8'))
    _archive_generated_report(instance.document, 'truth_delta', size)


@receiver(post_save, sender=BusinessValuationReport)
def archive_generated_valuation(sender, instance, **kwargs):
    fields = ('business_overview', 'financial_summary', 'risk_report', 'valuation_summary')
    size = sum(len((getattr(instance, field, '') or '').encode('utf-8')) for field in fields)
    _archive_generated_report(instance.document, 'valuation', size)


def ready():
    """
    Called when the app is ready.
    Used in apps.py to register signals.
    """
    pass
