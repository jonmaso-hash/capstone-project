# zelda_api/intelligence_pipeline.py
"""
Zelda Intelligence Pipeline - Central Orchestration
Orchestrates the complete flow:
Document → Chunks → Embeddings → Retrieval → Analysis → Insights → Memo
"""
import logging
from typing import Dict, List, Optional
from django.utils import timezone
from .vector_models import DocumentSource, DocumentChunk, IntelligenceInsight, IntelligenceMemo
from .chunking import DocumentChunker, estimate_tokens
from .embeddings import embedding_engine
from .retrieval import retriever, context_assembler

logger = logging.getLogger(__name__)

class ZeldaIntelligencePipeline:
    """
    The complete Zelda Intelligence Pipeline.
    Transforms raw documents into structured intelligence with source attribution.
    """
    
    def __init__(self):
        self.chunker = DocumentChunker(chunk_size_tokens=400, overlap_tokens=50)
        self.embedding_engine = embedding_engine
        self.retriever = retriever
        self.context_assembler = context_assembler
    
    def process_document(self, document_source: DocumentSource, raw_text: str) -> Dict:
        """
        Process a document end-to-end through the intelligence pipeline.
        
        Args:
            document_source: The DocumentSource instance
            raw_text: The extracted document text
            
        Returns:
            Dict with pipeline results and status
        """
        logger.info(f"Starting intelligence pipeline for {document_source.filename}")
        
        try:
            # Step 1: Store preview
            document_source.raw_text_preview = raw_text[:1000]
            document_source.total_word_count = len(raw_text.split())
            document_source.save()
            
            # Step 2: CHUNKING
            logger.info(f"Chunking document: {document_source.filename}")
            document_source.status = 'chunking'
            document_source.save()
            
            chunks_result = self._chunk_document(document_source, raw_text)
            if 'error' in chunks_result:
                raise Exception(chunks_result['error'])
            
            document_source.status = 'chunked'
            document_source.save()
            logger.info(f"Created {chunks_result['chunk_count']} chunks")
            
            # Step 3: EMBEDDING
            logger.info(f"Generating embeddings for {document_source.filename}")
            document_source.status = 'embedding'
            document_source.save()
            
            embedding_result = self._embed_chunks(document_source)
            if 'error' in embedding_result:
                raise Exception(embedding_result['error'])
            
            document_source.status = 'embedded'
            document_source.save()
            logger.info(f"Embedded {embedding_result['embedded_count']} chunks")
            
            # Step 4: RETRIEVAL & ANALYSIS
            logger.info(f"Running intelligence analysis for {document_source.filename}")
            document_source.status = 'analyzing'
            document_source.save()
            
            analysis_result = self._analyze_document(document_source, raw_text)
            if 'error' in analysis_result:
                raise Exception(analysis_result['error'])
            
            # Step 5: MEMO GENERATION
            logger.info(f"Generating intelligence memo for {document_source.filename}")
            memo_result = self._generate_memo(document_source, analysis_result)
            if 'error' in memo_result:
                raise Exception(memo_result['error'])
            
            # Mark complete
            document_source.status = 'analyzed'
            document_source.confidence_score = memo_result['completeness_score']
            document_source.processed_at = timezone.now()
            document_source.save()
            
            return {
                'status': 'success',
                'document_id': document_source.id,
                'chunks_created': chunks_result['chunk_count'],
                'insights_extracted': len(analysis_result['insights']),
                'memo_sections': memo_result['sections_count'],
                'confidence': document_source.confidence_score,
                'pipeline_complete': True,
            }
            
        except Exception as e:
            logger.error(f"Intelligence pipeline error: {str(e)}")
            document_source.status = 'error'
            document_source.error_message = str(e)
            document_source.save()
            return {
                'status': 'error',
                'error': str(e),
                'document_id': document_source.id,
            }
    
    def _chunk_document(self, document_source: DocumentSource, raw_text: str) -> Dict:
        """
        Step 1: Break document into semantic chunks.
        """
        try:
            chunks_data = self.chunker.chunk(raw_text)
            
            if not chunks_data:
                return {'error': 'No chunks generated from text'}
            
            # Create DocumentChunk records
            chunk_objects = []
            for chunk_index, (chunk_text, page_num, section) in enumerate(chunks_data):
                token_count = estimate_tokens(chunk_text)
                
                chunk = DocumentChunk.objects.create(
                    document=document_source,
                    chunk_index=chunk_index,
                    page_number=page_num,
                    section_title=section,
                    raw_text=chunk_text,
                    token_count=token_count,
                    relevance_score=0.5,  # Will be updated after embedding
                )
                chunk_objects.append(chunk)
            
            # Mark key insights (e.g., chunks with numbers/metrics)
            self._mark_key_insights(chunk_objects)
            
            return {
                'chunk_count': len(chunk_objects),
                'chunks': chunk_objects,
            }
            
        except Exception as e:
            return {'error': f'Chunking error: {str(e)}'}
    
    def _embed_chunks(self, document_source: DocumentSource) -> Dict:
        """
        Step 2: Generate embeddings for all chunks.
        """
        try:
            chunks = DocumentChunk.objects.filter(document=document_source).order_by('chunk_index')
            embedded_count = 0
            
            for chunk in chunks:
                try:
                    embedding = self.embedding_engine.embed_text(chunk.raw_text)
                    
                    if embedding:
                        chunk.embedding_vector = embedding
                        chunk.embedded_at = timezone.now()
                        chunk.save()
                        embedded_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to embed chunk {chunk.id}: {str(e)}")
            
            if embedded_count == 0:
                return {'error': 'Failed to embed any chunks'}
            
            return {
                'embedded_count': embedded_count,
                'total_chunks': chunks.count(),
            }
            
        except Exception as e:
            return {'error': f'Embedding error: {str(e)}'}
    
    def _analyze_document(self, document_source: DocumentSource, raw_text: str) -> Dict:
        """
        Step 3: Run intelligent analysis with retrieval context.
        Extracts insights with source attribution.
        """
        try:
            insights = []
            
            # Analysis categories
            analysis_categories = {
                'TAM': 'total addressable market market opportunity size',
                'SAM': 'serviceable addressable market',
                'Revenue': 'revenue income annual recurring financial metrics',
                'Team': 'team members founders CEO experience',
                'Product': 'product solution features technology',
                'Traction': 'customers users adopted traction growth',
                'Funding': 'funding raise capital investment ask',
                'Risk': 'risks challenges competition threats',
            }
            
            for category, search_query in analysis_categories.items():
                # Retrieve relevant context
                context_chunks, context_text = self.context_assembler.retrieve_for_category(
                    document_source, category
                )
                
                if context_chunks:
                    # Extract insight from context
                    insight = self._extract_insight(
                        category,
                        context_text,
                        context_chunks,
                        document_source
                    )
                    
                    if insight:
                        insights.append(insight)
            
            # Calculate confidence score
            confidence = min(len(insights) / 8.0, 1.0)  # Max 8 categories
            
            return {
                'insights': insights,
                'confidence': confidence,
                'categories_analyzed': len(analysis_categories),
            }
            
        except Exception as e:
            return {'error': f'Analysis error: {str(e)}'}
    
    def _extract_insight(self, category: str, context: str, chunks: List[Dict], 
                        document_source: DocumentSource) -> Optional[IntelligenceInsight]:
        """
        Extract a single insight with source attribution.
        """
        try:
            # Simple extraction logic (can be enhanced with Claude API)
            insight_text = self._simple_extract(category, context)
            
            if not insight_text:
                return None
            
            # Create insight record
            insight = IntelligenceInsight.objects.create(
                document=document_source,
                insight_type='statement',
                category=category,
                insight_text=insight_text,
                confidence_score=0.75,
                source_attribution=f"Retrieved from {len(chunks)} context chunks",
            )
            
            # Link to source chunks
            source_chunk_ids = [c['id'] for c in chunks]
            insight.source_chunks.set(source_chunk_ids)
            
            return insight
            
        except Exception as e:
            logger.warning(f"Failed to extract insight for {category}: {str(e)}")
            return None
    
    def _generate_memo(self, document_source: DocumentSource, analysis_result: Dict) -> Dict:
        """
        Step 4: Generate executive intelligence memo from insights.
        """
        try:
            insights = IntelligenceInsight.objects.filter(document=document_source)
            
            # Build memo sections
            memo, created = IntelligenceMemo.objects.update_or_create(
                document=document_source, # Use the document instance to uniquely identify the memo
                defaults={
                    'executive_summary': self._build_executive_summary(document_source, insights),
                    'problem_solution': self._build_problem_solution(insights),
                    'market_analysis': self._build_market_analysis(insights),
                    'team_assessment': self._build_team_assessment(insights),
                    'financial_analysis': self._build_financial_analysis(insights),
                    'risk_assessment': self._build_risk_assessment(insights),
                    'investment_thesis': self._build_investment_thesis(document_source, insights),
                    'completeness_score': analysis_result['confidence'],
                    'citations_count': sum(i.source_chunks.count() for i in insights),
                }
            )
            
            # Link insights
            memo.insights_used.set(insights)
            
            # Determine recommendation
            memo.recommendation = self._determine_recommendation(insights, analysis_result['confidence'])
            memo.save()
            
            return {
                'memo_id': memo.id,
                'sections_count': 7,
                'completeness_score': memo.completeness_score,
                'recommendation': memo.recommendation,
            }
            
        except Exception as e:
            return {'error': f'Memo generation error: {str(e)}'}
    
    # ────── Helper Methods ──────────────────────────────────────────────────────
    
    def _mark_key_insights(self, chunks: List[DocumentChunk]):
        """Mark chunks that contain metrics/numbers as key insights."""
        import re
        for chunk in chunks:
            # Look for numbers, currency, percentages
            if re.search(r'\$[\d,]+|[\d,]+%|\d+\s*(users|customers|employees)', chunk.raw_text):
                chunk.is_key_insight = True
                chunk.relevance_score = 0.8
                chunk.save()
    
    def _simple_extract(self, category: str, context: str) -> Optional[str]:
        """Improved heuristic extraction: Finds sentences containing category-specific keywords."""
        # Map categories to keywords that should be present in the text
        keywords = {
            'TAM': ['market', 'opportunity', 'addressable', 'size'],
            'SAM': ['serviceable', 'addressable'],
            'Revenue': ['revenue', 'income', '$', 'million', 'growth'],
            'Team': ['founder', 'CEO', 'team', 'experience', 'background'],
            'Product': ['platform', 'solution', 'features', 'technology', 'system'],
            'Traction': ['customers', 'users', 'growth', 'momentum'],
            'Funding': ['funding', 'raise', 'capital', 'series', 'runway'],
            'Risk': ['risk', 'challenges', 'competition', 'inefficiencies']
        }
        
        # Get keywords for current category (default to empty list)
        category_keywords = keywords.get(category, [])
        
        # Split into sentences
        sentences = [s.strip() for s in context.split('.') if len(s) > 20]
        
        # Find the sentence that best matches the category keywords
        best_sentence = None
        max_matches = 0
        
        for s in sentences:
            match_count = sum(1 for kw in category_keywords if kw.lower() in s.lower())
            if match_count > max_matches:
                max_matches = match_count
                best_sentence = s
        
        # Fallback to first sentence if no keyword matches found
        return best_sentence if best_sentence else sentences[0] if sentences else None
    
    def _build_executive_summary(self, document: DocumentSource, insights) -> str:
        """Build executive summary from insights."""
        return f"Analysis of {document.source_entity}. {document.total_word_count} words, {document.chunks.count()} sections analyzed."
    
    def _build_problem_solution(self, insights) -> str:
        """Build problem/solution section from insights."""
        relevant = insights.filter(category__in=['Problem', 'Product'])
        return ' '.join([i.insight_text for i in relevant])[:500] or "Problem and solution not fully detailed in document."
    
    def _build_market_analysis(self, insights) -> str:
        """Build market analysis section."""
        relevant = insights.filter(category__in=['TAM', 'SAM', 'Market'])
        return ' '.join([i.insight_text for i in relevant])[:500] or "Market analysis pending further document review."
    
    def _build_team_assessment(self, insights) -> str:
        """Build team assessment section."""
        relevant = insights.filter(category='Team')
        return ' '.join([i.insight_text for i in relevant])[:500] or "Team background not detailed."
    
    def _build_financial_analysis(self, insights) -> str:
        """Build financial analysis section."""
        relevant = insights.filter(category__in=['Revenue', 'Funding'])
        return ' '.join([i.insight_text for i in relevant])[:500] or "Financial metrics not specified."
    
    def _build_risk_assessment(self, insights) -> str:
        """Build risk assessment section."""
        relevant = insights.filter(category='Risk')
        return ' '.join([i.insight_text for i in relevant])[:500] or "Risks not explicitly identified."
    
    def _build_investment_thesis(self, document: DocumentSource, insights) -> str:
        """Build investment thesis."""
        return f"{document.source_entity} represents an opportunity based on {insights.count()} identified factors."
    
    def _determine_recommendation(self, insights, confidence: float) -> str:
        """Determine investment recommendation."""
        if confidence < 0.3:
            return 'pass'
        elif confidence < 0.5:
            return 'consider'
        elif confidence < 0.75:
            return 'interview'
        else:
            return 'strong_interest'


# Global pipeline instance
intelligence_pipeline = ZeldaIntelligencePipeline()