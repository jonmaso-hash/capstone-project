# zelda_api/management/commands/process_zelda_documents.py
"""
Django management command: process_zelda_documents
Manually trigger the Zelda Intelligence Pipeline for documents.

Usage:
    python manage.py process_zelda_documents --document-id 5
    python manage.py process_zelda_documents --status chunked
    python manage.py process_zelda_documents --all
    python manage.py process_zelda_documents --sync  # Process synchronously
"""
import logging
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from zelda_api.vector_models import DocumentSource
from zelda_api.intelligence_pipeline import intelligence_pipeline
from zelda_api.tasks import process_document_pipeline

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process documents through the Zelda Intelligence Pipeline'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--document-id',
            type=int,
            help='Process a specific document by ID'
        )
        parser.add_argument(
            '--status',
            type=str,
            help='Process all documents with a specific status (e.g., "chunked")'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Process all unprocessed documents'
        )
        parser.add_argument(
            '--sync',
            action='store_true',
            help='Process synchronously instead of async (blocking)'
        )
        parser.add_argument(
            '--source-entity',
            type=str,
            help='Process documents from a specific source entity'
        )
    
    def handle(self, *args, **options):
        use_sync = options.get('sync', False)
        
        # Determine which documents to process
        if options['document_id']:
            documents = DocumentSource.objects.filter(id=options['document_id'])
            if not documents.exists():
                raise CommandError(f"Document {options['document_id']} not found")
        
        elif options['status']:
            documents = DocumentSource.objects.filter(status=options['status'])
            if not documents.exists():
                self.stdout.write(
                    self.style.WARNING(f"No documents found with status '{options['status']}'")
                )
                return
        
        elif options['source_entity']:
            documents = DocumentSource.objects.filter(source_entity=options['source_entity'])
            if not documents.exists():
                self.stdout.write(
                    self.style.WARNING(f"No documents found for source '{options['source_entity']}'")
                )
                return
        
        elif options['all']:
            documents = DocumentSource.objects.exclude(status='analyzed')
        
        else:
            raise CommandError(
                "Must specify --document-id, --status, --source-entity, or --all"
            )
        
        # Process documents
        count = documents.count()
        self.stdout.write(
            self.style.SUCCESS(f"Processing {count} document(s)...")
        )
        
        processed = 0
        failed = 0
        
        for doc in documents:
            try:
                self.stdout.write(f"  • {doc.filename} ({doc.source_entity})", ending='')
                
                if use_sync:
                    # Synchronous processing (blocking)
                    result = intelligence_pipeline.process_document(
                        doc,
                        doc.raw_text_preview
                    )
                    
                    if result['status'] == 'success':
                        self.stdout.write(
                            self.style.SUCCESS(' ✓ Complete'),
                            ending='\n'
                        )
                        processed += 1
                    else:
                        self.stdout.write(
                            self.style.ERROR(f' ✗ Error: {result.get("error", "Unknown")}'),
                            ending='\n'
                        )
                        failed += 1
                else:
                    # Async processing (queue)
                    process_document_pipeline.delay(doc.id, doc.raw_text_preview)
                    self.stdout.write(
                        self.style.SUCCESS(' ✓ Queued'),
                        ending='\n'
                    )
                    processed += 1
            
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f' ✗ Exception: {str(e)}'),
                    ending='\n'
                )
                failed += 1
        
        # Summary
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(f"✓ Processed: {processed}")
        )
        if failed > 0:
            self.stdout.write(
                self.style.ERROR(f"✗ Failed: {failed}")
            )
        
        if not use_sync:
            self.stdout.write(
                self.style.WARNING("(Running in async mode - tasks queued for processing)")
            )