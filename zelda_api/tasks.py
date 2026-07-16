# zelda_api/tasks.py
"""
Celery async tasks for Zelda Intelligence Pipeline background processing.
Handles document ingestion, chunking, embedding, analysis, and memo generation
asynchronously to prevent blocking HTTP requests.
"""
import logging
from celery import shared_task
from django.utils import timezone
from .vector_models import DocumentSource
from .intelligence_pipeline import intelligence_pipeline
from .vector_models import DocumentChunk

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_document_pipeline(self, document_id: int, raw_text: str):
    """
    Main async task: Process a document through the complete Zelda Intelligence Pipeline.
    Handles chunking → embedding → analysis → memo generation.
    """
    try:
        logger.info(f"[Celery] Starting pipeline processing for document {document_id}")
        
        document = DocumentSource.objects.get(id=document_id)
        
        # 1. CLEANUP: Wipe existing chunks for this document before processing
        # This prevents the UNIQUE constraint error on re-runs or retries
        deleted_count, _ = DocumentChunk.objects.filter(document_id=document_id).delete()
        if deleted_count > 0:
            logger.info(f"[Celery] Purged {deleted_count} existing chunks for document {document_id}")
        
        # 2. Run the complete pipeline
        result = intelligence_pipeline.process_document(document, raw_text)
        
        if result['status'] == 'success':
            logger.info(f"[Celery] Pipeline complete for document {document_id}")
            
            # Send notification if needed
            notify_document_processed.delay(document_id)
            
            return {
                'status': 'success',
                'document_id': document_id,
                'chunks': result['chunks_created'],
                'insights': result['insights_extracted'],
            }
        else:
            logger.error(f"[Celery] Pipeline failed for document {document_id}: {result['error']}")
            raise Exception(result['error'])
        
    except DocumentSource.DoesNotExist:
        logger.error(f"Document {document_id} not found")
        return {'status': 'error', 'error': 'Document not found'}
    
    except Exception as exc:
        logger.error(f"Pipeline error for document {document_id}: {str(exc)}")
        
        # Retry with exponential backoff
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            countdown = 2 ** retry_count  # 2, 4, 8 seconds
            self.retry(exc=exc, countdown=countdown)
        else:
            # Mark document as failed after max retries
            document = DocumentSource.objects.get(id=document_id)
            document.status = 'error'
            document.error_message = f"Pipeline failed after {self.max_retries} retries: {str(exc)}"
            document.save()

            from ops.models import log_failed_task
            log_failed_task('zelda_api.tasks.process_document_pipeline', [document_id, raw_text], str(exc))

            return {'status': 'error', 'error': str(exc), 'retries_exhausted': True}


@shared_task(bind=True, max_retries=3)
def process_valuation_document_task(self, document_id: int, raw_text: str):
    """
    Parallel to process_document_pipeline for document_type='business_valuation':
    chunking → embedding → analysis → valuation report generation. No Truth
    Delta trigger — valuation isn't a fundraising claim to verify.
    """
    try:
        logger.info(f"[Celery] Starting valuation pipeline for document {document_id}")

        document = DocumentSource.objects.get(id=document_id)

        deleted_count, _ = DocumentChunk.objects.filter(document_id=document_id).delete()
        if deleted_count > 0:
            logger.info(f"[Celery] Purged {deleted_count} existing chunks for document {document_id}")

        result = intelligence_pipeline.process_valuation_document(document, raw_text)

        if result['status'] == 'success':
            logger.info(f"[Celery] Valuation pipeline complete for document {document_id}")
            return {
                'status': 'success',
                'document_id': document_id,
                'chunks': result['chunks_created'],
                'insights': result['insights_extracted'],
            }
        else:
            logger.error(f"[Celery] Valuation pipeline failed for document {document_id}: {result['error']}")
            raise Exception(result['error'])

    except DocumentSource.DoesNotExist:
        logger.error(f"Document {document_id} not found")
        return {'status': 'error', 'error': 'Document not found'}

    except Exception as exc:
        logger.error(f"Valuation pipeline error for document {document_id}: {str(exc)}")

        retry_count = self.request.retries
        if retry_count < self.max_retries:
            countdown = 2 ** retry_count
            self.retry(exc=exc, countdown=countdown)
        else:
            document = DocumentSource.objects.get(id=document_id)
            document.status = 'error'
            document.error_message = f"Valuation pipeline failed after {self.max_retries} retries: {str(exc)}"
            document.save()

            from ops.models import log_failed_task
            log_failed_task('zelda_api.tasks.process_valuation_document_task', [document_id, raw_text], str(exc))

            return {'status': 'error', 'error': str(exc), 'retries_exhausted': True}


@shared_task
def process_document_chunking_only(document_id: int, raw_text: str):
    """
    Focused task: Only chunk a document (lighter weight).
    Useful for quick preview generation.
    """
    try:
        document = DocumentSource.objects.get(id=document_id)
        document.status = 'chunking'
        document.save()
        
        result = intelligence_pipeline._chunk_document(document, raw_text)
        
        if 'error' not in result:
            document.status = 'chunked'
            document.save()
            return {'status': 'success', 'chunks': result['chunk_count']}
        else:
            raise Exception(result['error'])
    
    except Exception as exc:
        logger.error(f"Chunking error for document {document_id}: {str(exc)}")
        document = DocumentSource.objects.get(id=document_id)
        document.status = 'error'
        document.error_message = str(exc)
        document.save()
        return {'status': 'error', 'error': str(exc)}


@shared_task
def embed_document_chunks(document_id: int):
    """
    Focused task: Generate embeddings for an already-chunked document.
    Can be run independently or as part of the full pipeline.
    """
    try:
        document = DocumentSource.objects.get(id=document_id)
        document.status = 'embedding'
        document.save()
        
        result = intelligence_pipeline._embed_chunks(document)
        
        if 'error' not in result:
            document.status = 'embedded'
            document.save()
            logger.info(f"Embedded {result['embedded_count']} chunks for document {document_id}")
            return {'status': 'success', 'embedded': result['embedded_count']}
        else:
            raise Exception(result['error'])
    
    except Exception as exc:
        logger.error(f"Embedding error for document {document_id}: {str(exc)}")
        document = DocumentSource.objects.get(id=document_id)
        document.status = 'error'
        document.error_message = str(exc)
        document.save()
        return {'status': 'error', 'error': str(exc)}


@shared_task
def analyze_document_insights(document_id: int, raw_text: str):
    """
    Focused task: Run intelligent analysis and extract insights.
    Requires document to already be chunked and embedded.
    """
    try:
        document = DocumentSource.objects.get(id=document_id)
        document.status = 'analyzing'
        document.save()
        
        result = intelligence_pipeline._analyze_document(document, raw_text)
        
        if 'error' not in result:
            logger.info(f"Extracted {len(result['insights'])} insights for document {document_id}")
            return {'status': 'success', 'insights': len(result['insights'])}
        else:
            raise Exception(result['error'])
    
    except Exception as exc:
        logger.error(f"Analysis error for document {document_id}: {str(exc)}")
        document = DocumentSource.objects.get(id=document_id)
        document.status = 'error'
        document.error_message = str(exc)
        document.save()
        return {'status': 'error', 'error': str(exc)}


@shared_task
def generate_intelligence_memo(document_id: int):
    """
    Focused task: Generate the final intelligence memo.
    Must run after analysis is complete.
    """
    try:
        document = DocumentSource.objects.get(id=document_id)
        
        from .vector_models import IntelligenceInsight
        insights = IntelligenceInsight.objects.filter(document=document)
        
        analysis_result = {
            'confidence': min(len(insights) / 8.0, 1.0),
        }
        
        result = intelligence_pipeline._generate_memo(document, analysis_result)
        
        if 'error' not in result:
            document.status = 'analyzed'
            document.confidence_score = result['completeness_score']
            document.processed_at = timezone.now()
            document.save()
            
            logger.info(f"Memo generated for document {document_id}")
            return {'status': 'success', 'memo_id': result['memo_id']}
        else:
            raise Exception(result['error'])
    
    except Exception as exc:
        logger.error(f"Memo generation error for document {document_id}: {str(exc)}")
        document = DocumentSource.objects.get(id=document_id)
        document.status = 'error'
        document.error_message = str(exc)
        document.save()
        return {'status': 'error', 'error': str(exc)}


@shared_task
def notify_document_processed(document_id: int):
    """
    Notification task: Called when pipeline completes successfully.
    Sends user notification (email, webhook, etc).
    """
    try:
        document = DocumentSource.objects.get(id=document_id)
        user = document.uploaded_by
        
        logger.info(f"Document {document.filename} processed for user {user.username}")
        
        # TODO: Send email notification
        # TODO: Send webhook notification
        # TODO: Update user dashboard
        
        return {'status': 'notified', 'user_id': user.id}
    
    except Exception as exc:
        logger.warning(f"Notification error for document {document_id}: {str(exc)}")


@shared_task
def batch_process_unprocessed_documents():
    """
    Batch task: Find and process all documents that haven't been analyzed yet.
    Can be run on a schedule (e.g., every 30 minutes).
    """
    try:
        unprocessed = DocumentSource.objects.filter(
            status__in=['ingested', 'chunked', 'embedded']
        ).order_by('created_at')[:10]  # Batch of 10
        
        processed_count = 0
        for doc in unprocessed:
            # Queue for processing
            process_document_pipeline.delay(doc.id, doc.raw_text_full or doc.raw_text_preview)
            processed_count += 1
        
        logger.info(f"Queued {processed_count} documents for batch processing")
        return {'status': 'success', 'queued': processed_count}
    
    except Exception as exc:
        logger.error(f"Batch processing error: {str(exc)}")
        return {'status': 'error', 'error': str(exc)}


@shared_task
def cleanup_old_documents(days: int = 30):
    """
    Maintenance task: Clean up old processed documents.
    Run periodically to manage storage.
    """
    try:
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=days)
        
        old_docs = DocumentSource.objects.filter(
            processed_at__lt=cutoff_date,
            status='analyzed'
        )
        
        deleted_count = old_docs.count()
        old_docs.delete()
        
        logger.info(f"Deleted {deleted_count} documents older than {days} days")
        return {'status': 'success', 'deleted': deleted_count}
    
    except Exception as exc:
        logger.error(f"Cleanup error: {str(exc)}")
        return {'status': 'error', 'error': str(exc)}