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
    
    This automatically transforms:
    - Uploaded file → DocumentSource instance (created=True)
    - Triggers → Async pipeline processing
    """
    if created:
        logger.info(f"DocumentSource created: {instance.filename}")
        
        # Only auto-process if we have extracted text
        if instance.raw_text_preview:
            logger.info(f"Queuing {instance.filename} for pipeline processing")
            
            # Queue async task
            # Note: raw_text_preview is only 1000 chars. For full processing,
            # we'd need to pass the complete extracted text.
            # This is a simplified example - in practice, pass full_text from the view
            process_document_pipeline.delay(
                document_id=instance.id,
                raw_text=instance.raw_text_preview
            )
        else:
            logger.warning(f"No text preview for {instance.filename}, skipping processing")


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