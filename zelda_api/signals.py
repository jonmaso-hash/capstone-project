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


def ready():
    """
    Called when the app is ready.
    Used in apps.py to register signals.
    """
    pass