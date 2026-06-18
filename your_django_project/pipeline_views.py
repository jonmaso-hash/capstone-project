# zelda_api/pipeline_views.py
"""
Zelda Intelligence Pipeline API Views
These views use the centralized intelligence pipeline for document processing.
Replaces old scan_pitch_deck-based endpoints with RAG-powered analysis.
"""
import logging
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.authentication import SessionAuthentication, TokenAuthentication

from .vector_models import DocumentSource, IntelligenceMemo, IntelligenceInsight, DocumentChunk
from .intelligence_pipeline import intelligence_pipeline
from .retrieval import retriever, context_assembler
from .tasks import process_document_pipeline

logger = logging.getLogger(__name__)


class DocumentIngestView(APIView):
    """
    POST /api/v1/zelda/documents/ingest/
    
    Ingest a document and queue for intelligence pipeline processing.
    Handles PDF, PPTX, TXT files and extracts text automatically.
    
    Returns DocumentSource with processing status and polling endpoint.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {"error": "No file provided. Use form-data key 'file'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        source_entity = request.data.get('source_entity', 'Unknown')
        document_type = request.data.get('document_type', 'other')
        
        try:
            # Extract text from file (using existing utils)
            from .utils import extract_text_from_file
            extracted_text = extract_text_from_file(uploaded_file)
            
            if not extracted_text:
                return Response(
                    {"error": "Failed to extract text from file"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create DocumentSource record
            doc = DocumentSource.objects.create(
                filename=uploaded_file.name,
                document_type=document_type,
                source_entity=source_entity,
                uploaded_by=request.user,
                raw_text_preview=extracted_text[:1000],
                total_word_count=len(extracted_text.split()),
                status='ingested'
            )
            
            # Queue for pipeline processing (async)
            process_document_pipeline.delay(doc.id, extracted_text)
            
            return Response({
                'status': 'ingested',
                'document_id': doc.id,
                'filename': doc.filename,
                'source_entity': doc.source_entity,
                'polling_url': f'/api/v1/zelda/documents/{doc.id}/status/',
                'memo_url': f'/api/v1/zelda/documents/{doc.id}/memo/',
                'message': 'Document queued for intelligent analysis. Check polling_url for status.'
            }, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            logger.error(f"Document ingestion error: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DocumentStatusView(APIView):
    """
    GET /api/v1/zelda/documents/{document_id}/status/
    
    Poll the processing status of a document through the pipeline.
    Provides real-time updates on chunking, embedding, analysis progress.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, document_id):
        try:
            doc = DocumentSource.objects.get(id=document_id)
            
            # Check authorization
            if doc.uploaded_by != request.user and not request.user.is_staff:
                return Response(
                    {"error": "Not authorized"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Build status response
            response = {
                'document_id': doc.id,
                'filename': doc.filename,
                'status': doc.status,
                'confidence_score': doc.confidence_score,
                'created_at': doc.created_at.isoformat(),
            }
            
            # Add progress details
            if doc.status in ['chunking', 'chunked', 'embedding', 'embedded', 'analyzing']:
                chunks = doc.chunks.count()
                response['progress'] = {
                    'chunks_created': chunks,
                    'embeddings_generated': doc.chunks.filter(embedding_vector__isnull=False).count(),
                    'insights_extracted': doc.insights.count(),
                }
            
            # Add error if failed
            if doc.status == 'error':
                response['error'] = doc.error_message
            
            # Add memo link if complete
            if doc.status == 'analyzed' and hasattr(doc, 'memo'):
                response['memo_available'] = True
                response['memo_id'] = doc.memo.id
                response['memo_recommendation'] = doc.memo.recommendation
            
            return Response(response, status=status.HTTP_200_OK)
        
        except DocumentSource.DoesNotExist:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class DocumentMemoView(APIView):
    """
    GET /api/v1/zelda/documents/{document_id}/memo/
    
    Retrieve the generated intelligence memo with full source attribution.
    Only available after pipeline completes successfully.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]
    
    def get(self, request, document_id):
        try:
            doc = DocumentSource.objects.get(id=document_id)
            
            # Check authorization
            if doc.uploaded_by != request.user and not request.user.is_staff:
                return Response(
                    {"error": "Not authorized"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if not hasattr(doc, 'memo'):
                return Response(
                    {"error": "Memo not yet generated. Check status endpoint."},
                    status=status.HTTP_202_ACCEPTED
                )
            
            memo = doc.memo
            
            # Serialize memo with full citations
            response = {
                'memo_id': memo.id,
                'document_id': doc.id,
                'document_name': doc.source_entity,
                'recommendation': memo.recommendation,
                'completeness_score': memo.completeness_score,
                'citations_count': memo.citations_count,
                'sections': {
                    'executive_summary': memo.executive_summary,
                    'problem_solution': memo.problem_solution,
                    'market_analysis': memo.market_analysis,
                    'team_assessment': memo.team_assessment,
                    'financial_analysis': memo.financial_analysis,
                    'risk_assessment': memo.risk_assessment,
                    'investment_thesis': memo.investment_thesis,
                },
                'insights_cited': [
                    {
                        'category': i.category,
                        'text': i.insight_text,
                        'confidence': i.confidence_score,
                        'sources': list(i.source_chunks.values_list('page_number', flat=True)),
                    }
                    for i in memo.insights_used.all()
                ],
                'generated_at': memo.created_at.isoformat(),
            }
            
            return Response(response, status=status.HTTP_200_OK)
        
        except DocumentSource.DoesNotExist:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class DocumentChunksView(APIView):
    """
    GET /api/v1/zelda/documents/{document_id}/chunks/
    
    Retrieve all chunks for a document with embeddings and relevance scores.
    Useful for debugging and understanding the chunking strategy.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, document_id):
        try:
            doc = DocumentSource.objects.get(id=document_id)
            
            if doc.uploaded_by != request.user and not request.user.is_staff:
                return Response(
                    {"error": "Not authorized"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            chunks = doc.chunks.all().order_by('chunk_index')
            
            chunks_data = [
                {
                    'chunk_id': c.id,
                    'chunk_index': c.chunk_index,
                    'page': c.page_number,
                    'section': c.section_title,
                    'text': c.raw_text[:300] + '...' if len(c.raw_text) > 300 else c.raw_text,
                    'token_count': c.token_count,
                    'is_key_insight': c.is_key_insight,
                    'relevance_score': c.relevance_score,
                    'has_embedding': c.embedding_vector is not None,
                    'insights_count': c.insights.count(),
                }
                for c in chunks
            ]
            
            return Response({
                'document_id': doc.id,
                'total_chunks': chunks.count(),
                'chunks': chunks_data,
            }, status=status.HTTP_200_OK)
        
        except DocumentSource.DoesNotExist:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class DocumentInsightsView(APIView):
    """
    GET /api/v1/zelda/documents/{document_id}/insights/
    
    Retrieve all extracted insights with source attribution.
    Each insight links back to the chunks it was derived from.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, document_id):
        try:
            doc = DocumentSource.objects.get(id=document_id)
            
            if doc.uploaded_by != request.user and not request.user.is_staff:
                return Response(
                    {"error": "Not authorized"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            insights = doc.insights.all().order_by('-confidence_score')
            
            insights_data = [
                {
                    'insight_id': i.id,
                    'category': i.category,
                    'type': i.insight_type,
                    'text': i.insight_text,
                    'confidence': i.confidence_score,
                    'metric': f"{i.metric_value} {i.metric_unit}".strip() if i.metric_value else None,
                    'source_chunks': list(i.source_chunks.values_list('chunk_index', flat=True)),
                    'source_attribution': i.source_attribution,
                    'created_at': i.created_at.isoformat(),
                }
                for i in insights
            ]
            
            return Response({
                'document_id': doc.id,
                'insights_count': insights.count(),
                'insights': insights_data,
            }, status=status.HTTP_200_OK)
        
        except DocumentSource.DoesNotExist:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class DocumentSearchView(APIView):
    """
    POST /api/v1/zelda/documents/{document_id}/search/
    
    Vector semantic search within a document.
    Returns most relevant chunks with similarity scores.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, document_id):
        try:
            doc = DocumentSource.objects.get(id=document_id)
            
            if doc.uploaded_by != request.user and not request.user.is_staff:
                return Response(
                    {"error": "Not authorized"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            query = request.data.get('query', '').strip()
            if not query:
                return Response(
                    {"error": "Query required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Vector search within document
            results = retriever.retrieve(query, doc)
            
            return Response({
                'document_id': doc.id,
                'query': query,
                'results_count': len(results),
                'results': results,
            }, status=status.HTTP_200_OK)
        
        except DocumentSource.DoesNotExist:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class DocumentRAGView(APIView):
    """
    POST /api/v1/zelda/documents/{document_id}/rag/
    
    Retrieval-Augmented Generation: Get context for a query from document chunks.
    Returns assembled context with source citations for AI prompting.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, document_id):
        try:
            doc = DocumentSource.objects.get(id=document_id)
            
            if doc.uploaded_by != request.user and not request.user.is_staff:
                return Response(
                    {"error": "Not authorized"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            query = request.data.get('query', '').strip()
            top_k = request.data.get('top_k', 5)
            
            if not query:
                return Response(
                    {"error": "Query required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Retrieve context for RAG
            retriever_temp = retriever.__class__(top_k=top_k)
            results = retriever_temp.retrieve(query, doc)
            
            # Assemble context
            context_text = "Retrieved Context:\n\n"
            for i, result in enumerate(results, 1):
                context_text += f"[Source {i} - Page {result['page']}, {result['section']}]\n"
                context_text += result['text']
                context_text += f"\n[Relevance: {result['relevance']:.1%}]\n\n"
            
            return Response({
                'document_id': doc.id,
                'query': query,
                'context': context_text,
                'source_count': len(results),
                'sources': [
                    {
                        'chunk_id': r['id'],
                        'page': r['page'],
                        'section': r['section'],
                        'relevance': r['relevance'],
                    }
                    for r in results
                ],
            }, status=status.HTTP_200_OK)
        
        except DocumentSource.DoesNotExist:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )
            