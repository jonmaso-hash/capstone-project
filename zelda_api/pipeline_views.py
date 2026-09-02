# zelda_api/pipeline_views.py
"""
Zelda Intelligence Pipeline API Views
These views use the centralized intelligence pipeline for document processing.
Replaces old scan_pitch_deck-based endpoints with RAG-powered analysis.
"""
import logging
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from .truth_delta_tasks import verify_document_truth_delta as initiate_truth_delta_verification
from .vector_models import DocumentSource, IntelligenceMemo, IntelligenceInsight, DocumentChunk, BusinessValuationReport
from .intelligence_pipeline import intelligence_pipeline
from .retrieval import retriever, context_assembler
from .tasks import process_document_pipeline, process_valuation_document_task

logger = logging.getLogger(__name__)


class DocumentIngestView(APIView):
    """
    POST /api/v1/zelda/documents/ingest/
    
    Ingest a document, queue for Zelada intelligence processing,
    and trigger the Truth Delta verification engine.
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

        # Unlike every model-backed upload path (pitch_deck, cim_document,
        # data_room), this view builds a DocumentSource by hand with no
        # ModelForm/full_clean() — so MaxFileSizeValidator never ran here,
        # and an arbitrarily large file would be read entirely into memory
        # by PyPDF2/python-pptx before anything rejected it. Same 25MB cap
        # used elsewhere for pitch decks/CIMs.
        from matchmaking.validators import MaxFileSizeValidator
        try:
            MaxFileSizeValidator(max_mb=25)(uploaded_file)
        except ValidationError as e:
            return Response({"error": str(e.message)}, status=status.HTTP_400_BAD_REQUEST)

        source_entity = request.data.get('source_entity', 'Unknown')
        document_type = request.data.get('document_type', 'other')

        valuation_tier = None
        if document_type == 'business_valuation':
            # No upload-time gate — everyone can always generate a
            # valuation. valuation_tier decides whether DocumentValuationView
            # renders it in full or redacts it to a free preview.
            from .quotas import valuation_tier_for_new_upload
            valuation_tier = valuation_tier_for_new_upload(request.user)
        else:
            from .quotas import has_credits_for, upgrade_message
            if not has_credits_for(request.user, 'memo'):
                return Response(
                    {"error": upgrade_message(request.user), "code": "quota_exceeded"},
                    status=status.HTTP_402_PAYMENT_REQUIRED
                )

        try:
            # Extract text from file
            from .utils import extract_text_from_file
            extracted_text, page_count = extract_text_from_file(uploaded_file)

            if not extracted_text:
                return Response(
                    {"error": "Failed to extract text from file"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 1. Create DocumentSource record
            doc = DocumentSource.objects.create(
                filename=uploaded_file.name,
                document_type=document_type,
                source_entity=source_entity,
                uploaded_by=request.user,
                raw_text_preview=extracted_text[:1000],
                raw_text_full=extracted_text,
                total_word_count=len(extracted_text.split()),
                total_pages=page_count,
                status='ingested',
                **({'valuation_tier': valuation_tier} if valuation_tier else {}),
            )
            
            # 2. Queue for processing — valuation requests take a parallel path
            # (no Truth Delta trigger, different memo shape) from the standard
            # fundraising pipeline.
            if document_type == 'business_valuation':
                process_valuation_document_task.delay(doc.id, extracted_text)
            else:
                process_document_pipeline.delay(doc.id, extracted_text)

            # 3. BRIDGE: Trigger Truth Delta verification engine (async)
            # This makes the connection you requested.
            #initiate_truth_delta_verification.delay(doc.id)
            
            response_data = {
                'status': 'ingested',
                'document_id': doc.id,
                'filename': doc.filename,
                'source_entity': doc.source_entity,
                'polling_url': f'/api/v1/zelda/documents/{doc.id}/status/',
            }
            if document_type == 'business_valuation':
                response_data['valuation_url'] = f'/api/v1/zelda/documents/{doc.id}/valuation/'
                response_data['message'] = 'Document queued for business valuation analysis.'
            else:
                response_data['memo_url'] = f'/api/v1/zelda/documents/{doc.id}/memo/'
                response_data['verification_url'] = f'/api/v1/zelda/documents/{doc.id}/truth-delta/'
                response_data['message'] = 'Document queued for both Zelda Intelligence and Truth Delta verification.'

            return Response(response_data, status=status.HTTP_201_CREATED)
        
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
            # Check authorization
            # Allow: document owner, staff, or any authenticated investor
            viewer_is_investor = (
                getattr(request.user, 'accounts_investor_profile', None) is not None or
                getattr(request.user, 'match_investor_profile', None) is not None
            )
            if doc.uploaded_by != request.user and not request.user.is_staff and not viewer_is_investor:
                return Response(
                    {"error": "Not authorized"},
                    status=status.HTTP_403_FORBIDDEN
                )

            if doc.is_hidden_by_staff and doc.uploaded_by != request.user and not request.user.is_staff:
                return Response(
                    {"error": "This document is currently under review and isn't visible yet."},
                    status=status.HTTP_403_FORBIDDEN
                )

            if not hasattr(doc, 'memo'):
                return Response(
                    {"error": "Memo not yet generated. Check status endpoint."},
                    status=status.HTTP_202_ACCEPTED
                )

            memo = doc.memo

            # Free discovery signal for the founder even when the memo
            # content itself is Premium-locked below — "an investor showed
            # interest" should never be paywalled.
            if doc.uploaded_by != request.user and viewer_is_investor:
                from matchmaking.models import Application, log_investor_event
                founder_app = Application.objects.filter(user=doc.uploaded_by).first()
                if founder_app:
                    log_investor_event(request.user, founder_app, 'memo_view')

            from .truth_delta_models import _owner_is_premium
            memo_unlocked = request.user.is_staff or _owner_is_premium(doc.uploaded_by)

            if not memo_unlocked:
                return Response({
                    'memo_id': memo.id,
                    'document_id': doc.id,
                    'document_name': doc.source_entity,
                    'locked': True,
                    'is_owner': doc.uploaded_by == request.user,
                    'generated_at': memo.created_at.isoformat(),
                }, status=status.HTTP_200_OK)

            # Serialize memo with full citations
            response = {
                'memo_id': memo.id,
                'document_id': doc.id,
                'document_name': doc.source_entity,
                'locked': False,
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
                    'investment_readiness': memo.investment_readiness,
                    'key_strengths': memo.key_strengths,
                    'key_concerns': memo.key_concerns,
                    'what_would_change_decision': memo.what_would_change_decision,
                    'bull_case': memo.bull_case,
                    'base_case': memo.base_case,
                    'bear_case': memo.bear_case,
                    'zelda_advantage': memo.zelda_advantage,
                    'questions_for_management': memo.questions_for_management,
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
            from .disclaimers import DUE_DILIGENCE_DISCLAIMER
            response['disclaimer'] = DUE_DILIGENCE_DISCLAIMER

            return Response(response, status=status.HTTP_200_OK)

        except DocumentSource.DoesNotExist:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class DocumentValuationView(APIView):
    """
    GET /api/v1/zelda/documents/{document_id}/valuation/

    Retrieve the generated business valuation report. Owner-or-staff only —
    unlike DocumentMemoView, there's no "any investor" carve-out, since a
    valuation report is a personal financial document, not matchmaking
    content meant for a matching audience.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def get(self, request, document_id):
        try:
            doc = DocumentSource.objects.get(id=document_id)

            if doc.uploaded_by != request.user and not request.user.is_staff:
                return Response(
                    {"error": "Not authorized"},
                    status=status.HTTP_403_FORBIDDEN
                )

            if not hasattr(doc, 'valuation_report'):
                return Response(
                    {"error": "Valuation report not yet generated. Check status endpoint."},
                    status=status.HTTP_202_ACCEPTED
                )

            report = doc.valuation_report

            # Computed fresh from the document's current insights rather
            # than trusting the stored confidence_score field, so this
            # works retroactively on reports generated before the
            # confidence formula/breakdown existed — no reprocessing
            # (and no extra Claude cost) needed for historical reports.
            from .confidence_breakdown import compute_confidence_breakdown, compute_overall_confidence, compute_financial_completeness
            from .intelligence_pipeline import ZeldaIntelligencePipelineV2
            from .valuation_preview import build_valuation_response
            insights = list(doc.insights.all())
            confidence_breakdown = compute_confidence_breakdown(insights)
            overall_confidence = compute_overall_confidence(insights) if insights else report.confidence_score
            facts = ZeldaIntelligencePipelineV2()._build_structured_context(doc, insights)
            financial_completeness = compute_financial_completeness(facts)

            response = build_valuation_response(
                doc, report, insights, confidence_breakdown, overall_confidence,
                financial_completeness, doc.valuation_tier,
            )
            if doc.valuation_tier == 'preview':
                from .quotas import valuation_unlock_price
                purchase_type, price = valuation_unlock_price(request.user)
                response['unlock_purchase_type'] = purchase_type
                response['unlock_price'] = price
            else:
                from .valuation_trend import get_previous_full_valuation, compute_valuation_trend, compute_valuation_drivers
                previous_doc, previous_report = get_previous_full_valuation(doc)
                if previous_report:
                    trend = compute_valuation_trend(report, previous_report)
                    if trend:
                        response['trend'] = trend
                        previous_facts = ZeldaIntelligencePipelineV2()._build_structured_context(
                            previous_doc, list(previous_doc.insights.all()),
                        )
                        drivers = compute_valuation_drivers(facts, previous_facts)
                        if drivers:
                            response['valuation_drivers'] = drivers

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
    authentication_classes = [SessionAuthentication, TokenAuthentication]

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
    authentication_classes = [SessionAuthentication, TokenAuthentication]

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
    authentication_classes = [SessionAuthentication, TokenAuthentication]

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
    authentication_classes = [SessionAuthentication, TokenAuthentication]

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