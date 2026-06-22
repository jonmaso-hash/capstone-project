# zelda_api/signals.py
"""
Django signals for Zelda Intelligence Pipeline.
Automatically triggers pipeline when documents are uploaded or created.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .vector_models import DocumentSource
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
        
        # TODO: Send error alert to user
        # TODO: Send to monitoring/logging service
        # TODO: Implement retry logic


def ready():
    """
    Called when the app is ready.
    Used in apps.py to register signals.
    """
    pass