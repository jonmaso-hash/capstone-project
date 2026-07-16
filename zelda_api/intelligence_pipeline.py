
# zelda_api/intelligence_pipeline.py
"""
Zelda Intelligence Pipeline - Unified V2
Single authoritative pipeline with:
- Dynamic confidence scoring (0-100, not flat 75%)
- Chunk deduplication
- Truth Synthesis Engine integration
- Explicit Truth Delta trigger after memo generation
"""
import logging
import re
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from .vector_models import DocumentSource, DocumentChunk, IntelligenceInsight, IntelligenceMemo, BusinessValuationReport
from .chunking import DocumentChunker
from .embeddings import embedding_engine
from .retrieval import retriever
import json
from django.conf import settings

logger = logging.getLogger(__name__)


def _log_anthropic_usage(response, document_source, call_type):
    """
    Logs input/output token counts for a successful Anthropic call — token
    counts rather than a hardcoded $/token estimate, since pricing changes
    over time and a stale hardcoded number would be worse than no number.
    Flows into the persistent log file (logs/django.log) automatically.
    document_source is optional — calls not tied to a specific document
    (e.g. the natural-language query extraction) pass None.
    """
    try:
        usage = getattr(response, 'usage', None)
        if usage:
            subject = f"document {document_source.id}" if document_source is not None else "ad-hoc request"
            logger.info(
                f"[Anthropic usage] {call_type} for {subject}: "
                f"input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}"
            )
    except Exception as e:
        logger.warning(f"Failed to log Anthropic usage: {str(e)}")


class ZeldaIntelligencePipelineV2:
    """Zelda Intelligence Pipeline v2 - Production Ready"""
    
    def __init__(self):
        self.chunker = DocumentChunker(chunk_size_tokens=400, overlap_tokens=50)
        self.embedding_engine = embedding_engine
        self.retriever = retriever
        self.used_chunks = set()  # Track used chunks to prevent duplication
    
    def process_document(self, document_source: DocumentSource, raw_text: str) -> Dict:
        """Process document through complete pipeline + Truth Delta trigger"""
        logger.info(f"Starting pipeline v2 for {document_source.filename}")
        
        try:
            # Store preview
            document_source.raw_text_preview = raw_text[:1000]
            document_source.raw_text_full = raw_text
            document_source.total_word_count = len(raw_text.split())
            document_source.save()
            
            # STEP 1: CHUNKING
            logger.info(f"Chunking: {document_source.filename}")
            document_source.status = 'chunking'
            document_source.save()
            
            chunks_result = self._chunk_document(document_source, raw_text)
            if 'error' in chunks_result:
                raise Exception(chunks_result['error'])
            
            document_source.status = 'chunked'
            document_source.save()
            
            # STEP 2: EMBEDDING
            logger.info(f"Embedding: {document_source.filename}")
            document_source.status = 'embedding'
            document_source.save()
            
            embedding_result = self._embed_chunks(document_source)
            if 'error' in embedding_result:
                raise Exception(embedding_result['error'])
            
            document_source.status = 'embedded'
            document_source.save()
            
            # STEP 3: ANALYSIS
            logger.info(f"Analyzing: {document_source.filename}")
            document_source.status = 'analyzing'
            document_source.save()
            
            self.used_chunks = set()  # Reset tracking
            analysis_result = self._analyze_document(document_source, raw_text)
            if 'error' in analysis_result:
                raise Exception(analysis_result['error'])
            
            # STEP 4: MEMO GENERATION
            logger.info(f"Generating memo: {document_source.filename}")
            memo_result = self._generate_memo(document_source, analysis_result)
            if 'error' in memo_result:
                raise Exception(memo_result['error'])
            
            # STEP 5: TRIGGER TRUTH DELTA
            logger.info(f"Triggering Truth Delta: {document_source.filename}")
            self._trigger_truth_delta(document_source)
            
            # Mark complete
            document_source.status = 'analyzed'
            document_source.confidence_score = memo_result.get('completeness_score', 0)
            document_source.processed_at = timezone.now()
            document_source.save()
            
            logger.info(f"Pipeline complete for {document_source.filename}")
            
            return {
                'status': 'success',
                'document_id': document_source.id,
                'chunks_created': chunks_result.get('chunk_count', 0),
                'insights_extracted': len(analysis_result.get('insights', [])),
                'memo_id': memo_result.get('memo_id'),
                'truth_delta_queued': True,
            }
        
        except Exception as e:
            logger.error(f"Pipeline error: {str(e)}")
            document_source.status = 'error'
            document_source.error_message = str(e)
            document_source.save()
            return {'status': 'error', 'error': str(e)}

    def process_valuation_document(self, document_source: DocumentSource, raw_text: str) -> Dict:
        """
        Parallel path for document_type='business_valuation': reuses the
        generic chunk/embed/analyze steps, then generates a
        BusinessValuationReport instead of a fundraising-shaped
        IntelligenceMemo. No Truth Delta trigger — valuation isn't a
        fundraising claim to verify.
        """
        logger.info(f"Starting valuation pipeline for {document_source.filename}")

        try:
            document_source.raw_text_preview = raw_text[:1000]
            document_source.raw_text_full = raw_text
            document_source.total_word_count = len(raw_text.split())
            document_source.save()

            logger.info(f"Chunking: {document_source.filename}")
            document_source.status = 'chunking'
            document_source.save()

            chunks_result = self._chunk_document(document_source, raw_text)
            if 'error' in chunks_result:
                raise Exception(chunks_result['error'])

            document_source.status = 'chunked'
            document_source.save()

            logger.info(f"Embedding: {document_source.filename}")
            document_source.status = 'embedding'
            document_source.save()

            embedding_result = self._embed_chunks(document_source)
            if 'error' in embedding_result:
                raise Exception(embedding_result['error'])

            document_source.status = 'embedded'
            document_source.save()

            logger.info(f"Analyzing: {document_source.filename}")
            document_source.status = 'analyzing'
            document_source.save()

            self.used_chunks = set()
            analysis_result = self._analyze_document(document_source, raw_text)
            if 'error' in analysis_result:
                raise Exception(analysis_result['error'])

            logger.info(f"Generating valuation report: {document_source.filename}")
            valuation_result = self._generate_valuation_report(document_source, analysis_result)
            if 'error' in valuation_result:
                raise Exception(valuation_result['error'])

            document_source.status = 'analyzed'
            document_source.confidence_score = valuation_result.get('confidence_score', 0)
            document_source.processed_at = timezone.now()
            document_source.save()

            logger.info(f"Valuation pipeline complete for {document_source.filename}")

            return {
                'status': 'success',
                'document_id': document_source.id,
                'chunks_created': chunks_result.get('chunk_count', 0),
                'insights_extracted': len(analysis_result.get('insights', [])),
                'valuation_report_id': valuation_result.get('report_id'),
            }

        except Exception as e:
            logger.error(f"Valuation pipeline error: {str(e)}")
            document_source.status = 'error'
            document_source.error_message = str(e)
            document_source.save()
            return {'status': 'error', 'error': str(e)}

    # --- Pipeline Methods ---
    
    def _chunk_document(self, document_source: DocumentSource, raw_text: str) -> Dict:
        """Step 1: Chunk document"""
        try:
            # DELETE existing chunks to allow reprocessing
            DocumentChunk.objects.filter(document=document_source).delete()
            logger.info(f"Cleared existing chunks for {document_source.id}")

            chunks = self.chunker.chunk(raw_text)
            chunk_objects = []

            for idx, (chunk_text, page_num, section_title) in enumerate(chunks):
                chunk_obj = DocumentChunk.objects.create(
                    document=document_source,
                    chunk_index=idx,
                    page_number=page_num,
                    section_title=section_title,
                    raw_text=chunk_text,
                    token_count=len(chunk_text.split()),
                    relevance_score=0.5,
                )
                chunk_objects.append(chunk_obj)

            logger.info(f"Created {len(chunk_objects)} chunks")
            return {'status': 'success', 'chunk_count': len(chunk_objects), 'chunks': chunk_objects}

        except Exception as e:
            return {'error': f'Chunking error: {str(e)}'}
    
    def _embed_chunks(self, document_source: DocumentSource) -> Dict:
        """Step 2: Generate embeddings"""
        import json
        try:
            chunks = DocumentChunk.objects.filter(document=document_source)
            embedded_count = 0
            
            for chunk in chunks:
                try:
                    embedding = self.embedding_engine.embed_text(chunk.raw_text)
                    if embedding is not None:
                        # Ensure valid JSON before storing
                        chunk.embedding_vector = json.dumps(
                            [float(x) for x in embedding]
                        )
                        chunk.save()
                        embedded_count += 1
                except Exception as e:
                    logger.warning(f"Failed to embed chunk {chunk.id}: {str(e)}")
            
            logger.info(f"Embedded {embedded_count} chunks")
            return {'status': 'success', 'embedded_count': embedded_count}
    
        except Exception as e:
            return {'error': f'Embedding error: {str(e)}'}
    
    def _analyze_document(self, document_source: DocumentSource, raw_text: str) -> Dict:
        """Step 3: Extract insights with dynamic confidence"""
        try:
            IntelligenceInsight.objects.filter(document=document_source).delete()
            
            insights = []
            chunks = list(DocumentChunk.objects.filter(document=document_source).order_by('chunk_index'))
            
            analysis_categories = {
                'Problem': 'problem challenge issue pain solution healthcare fragmented',
                'Market': 'market tam sam opportunity size addressable healthcare',
                'Revenue': 'revenue arr mrr pricing monetization income annual recurring subscription',
                'Team': 'team founder ceo experience background skill leadership',
                'Product': 'product feature technology platform service offering',
                # 'revenue' deliberately excluded — Revenue already has its
                # own category, and including it here meant every revenue
                # sentence ALSO triggered a duplicate Traction insight for
                # the same figure (invisible until the category_mapping
                # wiring bug was fixed and Traction claims started reaching
                # ClaimedDatapoint at all, at which point it surfaced as a
                # real precision regression in the evaluation harness).
                'Traction': 'customers users growth adopted retention metric',
                'Funding': 'funding raise capital investment ask series round raised',
                'Risk': 'risks challenges competition threats barrier regulatory',
            }
            
            for category, keywords in analysis_categories.items():
                best_insight = None
                best_confidence = 0
                
                # Search each chunk independently
                for chunk in chunks:
                    result, confidence = self._smart_extract(category, chunk.raw_text, keywords)
                    if result and confidence > best_confidence:
                        best_confidence = confidence
                        best_insight = (result, confidence, chunk)
                
                if best_insight:
                    insight_text, confidence, source_chunk = best_insight
                    
                    insight = IntelligenceInsight.objects.create(
                        document=document_source,
                        insight_type='statement',
                        category=category,
                        insight_text=insight_text,
                        confidence_score=confidence,
                        source_attribution=f"Extracted from: {source_chunk.section_title or 'document'}",
                    )
                    insight.source_chunks.set([source_chunk])
                    self.used_chunks.add(source_chunk.id)
                    insights.append(insight)
            
            logger.info(f"Extracted {len(insights)} insights with dynamic confidence")
            return {
                'insights': insights,
                'confidence': min(len(insights) / 8.0, 1.0),
            }
        
        except Exception as e:
            return {'error': f'Analysis error: {str(e)}'}
    
    def _extract_insight_with_confidence(
        self,
        document_source,
        category: str,
        raw_text: str,
        keywords: str
    ) -> Optional[IntelligenceInsight]:
        """Extract insight with DYNAMIC confidence scoring"""
        try:
            insight_text, confidence = self._smart_extract(category, raw_text, keywords)
            
            if not insight_text:
                return None
            
            insight = IntelligenceInsight.objects.create(
                document=document_source,
                insight_type='statement',
                category=category,
                insight_text=insight_text,
                confidence_score=confidence,
                source_attribution="Extracted from document content",
            )
            
            # Link to relevant chunks with deduplication
            keyword_list = keywords.split()
            relevant_chunks = DocumentChunk.objects.filter(
                document=document_source
            ).filter(
                raw_text__icontains=keyword_list[0] if keyword_list else category
            ).exclude(id__in=self.used_chunks)[:2]
            
            insight.source_chunks.set(relevant_chunks)
            
            for chunk in relevant_chunks:
                self.used_chunks.add(chunk.id)
            
            return insight
        
        except Exception as e:
            logger.warning(f"Failed to extract {category}: {str(e)}")
            return None
    
    def _smart_extract(self, category: str, text: str, keywords: str) -> Tuple[Optional[str], float]:
        """
        Smart extraction with DYNAMIC confidence scoring.
        Confidence logic:
        - Explicit number match: 95%
        - Exact phrase match: 85%
        - Keyword match with context: 70%
        - Generic/inferred: 45%
        """
        keyword_list = keywords.split()
        sentences = re.split(r'(?<!\d)[.!?](?!\d)|\n', text)

        best_match = None
        best_confidence = 0

        for sentence in sentences:
            sentence_lower = sentence.lower()

            matching_keywords = sum(1 for kw in keyword_list if kw.lower() in sentence_lower)

            if matching_keywords == 0:
                continue

            clean_sentence = sentence.strip()

            # Skip short fragments
            if len(clean_sentence) < 10:
                continue

            # Skip header/metadata blocks — label: value patterns with no sentence structure
            if re.match(r'^(HQ|Company Size|Years in Business|Founded|Location|Employees|Email|Phone|Website)\s*:', clean_sentence, re.IGNORECASE):
                continue

            # Skip sentences that are mostly label:value pairs (colon density check)
            colon_count = clean_sentence.count(':')
            word_count = len(clean_sentence.split())
            if colon_count >= 2 and word_count < 20:
                continue

            # Skip sentences that contain the company name + metadata noise
            if re.search(r'(HQ|Company Size|Years in Business).{0,60}(HQ|Company Size|Years in Business)', clean_sentence, re.IGNORECASE):
                continue

            confidence = self._calculate_confidence(category, clean_sentence, text)

            if confidence > best_confidence or (
                confidence == best_confidence and 
                re.search(r'\$[\d,]+[MBK]?', clean_sentence) and 
                not re.search(r'\$[\d,]+[MBK]?', best_match or '')
            ):
                best_confidence = confidence
                cleaned_value = self._extract_clean_value(category, clean_sentence)
                best_match = cleaned_value[:500]

        if not best_match:
            fallback = self._get_smart_fallback(category, text)
            if fallback is None:
                return None, 0.0
            return fallback, 35.0

        return best_match, best_confidence

    def _extract_clean_value(self, category: str, sentence: str) -> str:
        """
        Extract clean, focused value from noisy sentence. The sentence
        passed in has already matched this category's keywords in
        _smart_extract's main loop, so every branch here is narrowing an
        already-grounded sentence, not introducing new content.

        (An unconditional `return cleaned[:200]` used to sit right after
        the 'Funding' branch, making every branch below it — Revenue,
        Traction, Team, Market — permanently unreachable dead code, so
        every category except Funding silently fell through to the raw
        200-char sentence truncation regardless of whether a cleaner
        extraction was available.)
        """
        cleaned = re.sub(r'^[A-Z][a-z]+\s*:\s*', '', sentence).strip()

        # Shared numeric token: digits (with optional decimal) plus an
        # optional multiplier — either abbreviated (K/M/B) or spelled out
        # (thousand/million/billion), since real prose overwhelmingly uses
        # the latter ("$2.4 million"). The old `[\d,]+[MBK]?` version had
        # no decimal support at all, so "$2.4 million" matched only as
        # far as "$2" — truncating both the digits AND the multiplier
        # word before _extract_numeric_value ever saw it downstream,
        # silently turning a $2.4M claim into a $2 claim.
        amount = r'\$[\d,]*\.?\d+\s*(?:thousand|million|billion|[KkMmBb])?'

        if category == 'Funding':
            match = re.search(rf'(seeking.{{0,40}}{amount}|{amount}.{{0,40}}(series|round|raised|funding))', cleaned, re.IGNORECASE)
            if match:
                return match.group().strip()

        if category == 'Revenue':
            # Extract: "$5M ARR" or "subscription model"
            match = re.search(rf'({amount})\s*(?:arr|mrr|revenue|recurring)?[^.]{{0,80}}', cleaned, re.IGNORECASE)
            if match:
                return match.group().strip()
            if 'subscription' in cleaned.lower():
                return "Recurring subscription revenue model."

        if category == 'Traction':
            # Extract: "200 hospitals" or "5,000 customers"
            match = re.search(r'([\d,]+)\s*(customers?|users?|clients?|hospitals?|clinics?)[^.]{0,80}', cleaned, re.IGNORECASE)
            if match:
                return match.group().strip()

        if category == 'Team':
            # Extract: "200 employees" or "Founded by..."
            match = re.search(r'(founder.{0,60}|ceo.{0,60}|founded by.{0,60})', cleaned, re.IGNORECASE)
            if match:
                return match.group().strip()

        if category == 'Market':
            # Extract: "$50B TAM" or "large addressable market..."
            match = re.search(rf'({amount})[^.]{{0,80}}(market|tam|opportunity)', cleaned, re.IGNORECASE)
            if match:
                return match.group().strip()

        # No tighter category-specific pattern matched — fall back to the
        # real (already keyword-matched) sentence itself, truncated.
        return cleaned[:200]
    
    def _calculate_confidence(self, category: str, sentence: str, full_text: str) -> float:
        """Calculate DYNAMIC confidence based on content analysis."""
        sentence_lower = sentence.lower()

        category_number_patterns = {
            'Funding': r'(seeking.{0,20}\$[\d,]+[MBK]|\$[\d,]+[MBK].{0,40}(raised|capital|funding|proceeds|round)|(use of proceeds))',
            'Revenue': r'(current revenue|\$[\d,\.]+[MBK]|recurring subscription|saas|enterprise)',
            'Traction': r'(current revenue|prior capital|\$[\d,\.]+[MBK]|momentum|series.c)',
            'Team': r'(founder|ceo|co-founder|chief executive|managing partner|leadership team|founded by)\s*[:\&]?\s*[A-Z][a-z]+',
            'Market': r'(addressable|tam|sam|market).{0,60}(hospitals|clinics|providers|healthcare)',
            'Product': r'(centralizes|coordinates|saas|enterprise|one platform|care delivery)',
            'Problem': r'(fragmented|inefficien|lack.{0,20}visibility|increase costs|reduce patient)',
            'Risk': r'(competition|regulatory|adoption|churn|compliance|barrier)',
    }

        pattern = category_number_patterns.get(category)
        if pattern and re.search(pattern, sentence_lower):
            return 95.0

        exact_phrases = {
            'Funding': ['use of proceeds', 'seeking:', '$20m series', 'funding round', 'series-c funding'],
            'Revenue': ['recurring subscription', 'subscription revenue', 'business model', 'saas'],
            'Team': ['founder & ceo', 'founded by', 'ceo:', 'chief executive', 'co-founder', 'managing partner', 'general partner'],
            'Market': ['addressable market', 'market opportunity', 'healthcare technology market'],
            'Traction': ['current revenue', 'operational momentum', 'prior capital'],
            'Product': ['centralizes', 'one platform', 'workforce coordination', 'care delivery'],
            'Problem': ['fragmented', 'unified operational', 'administrative inefficien'],
            'Risk': ['execution risk', 'competition', 'regulatory'],
                }

        for cat, phrases in exact_phrases.items():
            if cat.lower() == category.lower():
                if any(phrase in sentence_lower for phrase in phrases):
                    return 85.0

        keyword_count = len(re.findall(r'\b\w+\b', sentence_lower))
        if keyword_count >= 10:
            return 70.0

        if full_text.count(sentence[:30]) > 1:
            return 60.0

        return 50.0
    
    
    def _get_smart_fallback(self, category: str, text: str) -> Optional[str]:
        """
        Fallback used only when no sentence anywhere in the document
        matched this category's keywords at all (the main loop in
        _smart_extract already exhausted every sentence). Returns None —
        no claim — unless a narrowly-scoped, literal fact can still be
        pulled from the text. Never fabricates a generic or
        cross-contaminated claim.

        This replaces a version that always returned a templated string:
        several branches grabbed the FIRST dollar figure anywhere in the
        whole document — regardless of what it actually described — and
        wrapped it in a category-specific sentence. On a real document
        whose only dollar figure was a revenue claim, the Funding fallback
        fabricated "Secured $415 in Series funding from institutional
        investors" — a funding claim with zero basis in the source text.
        Other branches had no numeric grounding at all and just returned
        a fixed generic sentence ("Qualified team with relevant industry
        experience.") regardless of document content. Both patterns
        violate the basic rule for a verification system: never assert a
        fact the source document doesn't support. Precision over recall —
        it's fine, and expected, for a document with no funding
        information to produce no funding claim.
        """
        fallbacks = {
            'Problem': self._extract_problem_fallback(text),
            'Market': self._extract_market_fallback(text),
            'Revenue': self._extract_revenue_fallback(text),
            'Team': self._extract_team_fallback(text),
            'Product': self._extract_product_fallback(text),
            'Traction': self._extract_traction_fallback(text),
            'Funding': self._extract_funding_fallback(text),
            'Risk': self._extract_risk_fallback(text),
        }
        return fallbacks.get(category)

    @staticmethod
    def _find_amount_with_context(text: str, context_keywords: List[str]) -> Optional[str]:
        """
        Returns the first SENTENCE that contains both a dollar figure and
        at least one of the given context words — never a dollar figure
        borrowed from an unrelated sentence elsewhere in the document.
        Used by the Market/Revenue/Funding fallbacks specifically because
        a bare number, without knowing what it refers to, isn't a claim
        that can be safely attributed to any one category.
        """
        for sentence in re.split(r'(?<!\d)[.!?](?!\d)|\n', text):
            if not re.search(r'\$[\d,\.]+[MBK]?', sentence):
                continue
            if any(kw in sentence.lower() for kw in context_keywords):
                return sentence.strip()[:200]
        return None

    def _extract_problem_fallback(self, text: str) -> Optional[str]:
        # Purely narrative — no literal fact to extract in isolation, and
        # the primary keyword-sentence pass already found nothing.
        return None

    def _extract_market_fallback(self, text: str) -> Optional[str]:
        return self._find_amount_with_context(text, ['market', 'tam', 'sam', 'addressable', 'opportunity'])

    def _extract_revenue_fallback(self, text: str) -> Optional[str]:
        return self._find_amount_with_context(text, ['revenue', 'arr', 'mrr', 'recurring'])

    def _extract_team_fallback(self, text: str) -> Optional[str]:
        # A headcount figure is a self-contained, literal fact when
        # present — safe to report on its own, unlike a bare dollar
        # amount which needs context to know what it refers to.
        match = re.search(r'(\d[\d,]*)\s*employees?', text, re.IGNORECASE)
        return f"{match.group(1)} employees mentioned in the document." if match else None

    def _extract_product_fallback(self, text: str) -> Optional[str]:
        return None

    def _extract_traction_fallback(self, text: str) -> Optional[str]:
        match = re.search(r'([\d,]+)\s*(customers?|users?|companies?|clients?)', text, re.IGNORECASE)
        return match.group().strip() if match else None

    def _extract_funding_fallback(self, text: str) -> Optional[str]:
        return self._find_amount_with_context(text, ['raised', 'funding', 'financing', 'round', 'series', 'capital', 'investment'])

    def _extract_risk_fallback(self, text: str) -> Optional[str]:
        return None
    
    # --- Memo builders ---
    
    def _generate_memo(self, document_source: DocumentSource, analysis_result: Dict) -> Dict:
        """Step 4: Generate intelligence memo using Claude with evidence-grounded prompt"""
        try:
            IntelligenceMemo.objects.filter(document=document_source).delete()

            insights = IntelligenceInsight.objects.filter(
                document=document_source
            ).order_by('-confidence_score')

            structured_context = self._build_structured_context(document_source, insights)
            memo_sections = self._call_claude_for_memo(document_source, structured_context, insights)

            if 'error' in memo_sections:
                # Without this check, the update_or_create below would use
                # its .get(..., default) fallbacks and silently write a
                # "successful" memo full of placeholder text — the caller
                # (process_document) already checks for this key and marks
                # the document status='error', but only if we raise here.
                raise Exception(memo_sections['error'])

            memo, created = IntelligenceMemo.objects.update_or_create(
                document=document_source,
                defaults={
                    'executive_summary':  memo_sections.get('executive_summary', 'Not generated.'),
                    'problem_solution':   memo_sections.get('problem_solution', 'Not disclosed in pitch deck.'),
                    'market_analysis':    memo_sections.get('market_analysis', 'Not disclosed in pitch deck.'),
                    'team_assessment':    memo_sections.get('team_assessment', 'Not disclosed in pitch deck.'),
                    'financial_analysis': memo_sections.get('financial_analysis', 'Not disclosed in pitch deck.'),
                    'risk_assessment':    memo_sections.get('risk_assessment', 'Not disclosed in pitch deck.'),
                    'investment_thesis':  memo_sections.get('investment_thesis', 'Insufficient data.'),
                    'investment_readiness':     memo_sections.get('investment_readiness', 'Not assessed.'),
                    'questions_for_management': memo_sections.get('questions_for_management', 'Not assessed.'),
                    'completeness_score': analysis_result.get('confidence', 0),
                    'citations_count':    sum(i.source_chunks.count() for i in insights),
                }
            )

            memo.insights_used.set(insights)
            memo.recommendation = memo_sections.get('recommendation', 'NEEDS_REVIEW')
            memo.save()

            logger.info(f"Claude memo generated for document {document_source.id}")

            return {
                'memo_id': memo.id,
                'sections_count': 9,
                'completeness_score': memo.completeness_score,
            }

        except Exception as e:
            logger.error(f"Memo generation error: {str(e)}")
            return {'error': f'Memo error: {str(e)}'}

    def _trigger_truth_delta(self, document_source: DocumentSource) -> None:
        """
        Step 5: Queue Truth Delta claim extraction + verification for this document.
        Runs async via Celery — failure here must not fail the pipeline, since the
        memo has already been generated successfully by this point.
        """
        try:
            from .truth_delta_tasks import extract_claims_from_insights
            extract_claims_from_insights.delay(document_source.id)
            logger.info(f"Truth Delta queued for document {document_source.id}")
        except Exception as e:
            logger.warning(f"Truth Delta trigger failed for document {document_source.id}: {str(e)}")

    def _generate_valuation_report(self, document_source: DocumentSource, analysis_result: Dict) -> Dict:
        """Parallel to _generate_memo: generates a BusinessValuationReport instead."""
        try:
            insights = IntelligenceInsight.objects.filter(
                document=document_source
            ).order_by('-confidence_score')

            structured_context = self._build_structured_context(document_source, insights)
            sections = self._call_claude_for_valuation(document_source, structured_context, insights)

            if 'error' in sections:
                # Same reasoning as _generate_memo's identical check — without
                # this, update_or_create's .get(..., default) fallbacks would
                # silently write a "successful" report full of placeholder text.
                raise Exception(sections['error'])

            report, created = BusinessValuationReport.objects.update_or_create(
                document=document_source,
                defaults={
                    'business_overview':  sections.get('business_overview', 'Not generated.'),
                    'financial_summary':  sections.get('financial_summary', 'Not disclosed in submitted documents.'),
                    'risk_report':        sections.get('risk_report', 'Not disclosed in submitted documents.'),
                    'valuation_summary':  sections.get('valuation_summary', 'Insufficient data to estimate a valuation.'),
                    'valuation_low':      sections.get('valuation_low'),
                    'valuation_high':     sections.get('valuation_high'),
                    'confidence_score':   analysis_result.get('confidence', 0),
                }
            )

            logger.info(f"Claude valuation report generated for document {document_source.id}")

            return {
                'report_id': report.id,
                'confidence_score': report.confidence_score,
            }

        except Exception as e:
            logger.error(f"Valuation report generation error: {str(e)}")
            return {'error': f'Valuation report error: {str(e)}'}

    def _call_claude_for_valuation(self, doc: DocumentSource, facts: dict, insights) -> dict:
        """Call Claude API to generate an evidence-grounded business valuation report."""
        import anthropic
        import json

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        insights_list = "\n".join([
            f"{i+1}. [{ins.category} | {ins.confidence_score:.0f}% confidence] {ins.insight_text}"
            for i, ins in enumerate(insights[:25])
        ])

        missing = "\n".join([f"• {m}" for m in facts.get('missing_fields', [])]) or "• None identified"
        traction = "\n".join([f"• {t}" for t in facts.get('traction_signals', [])]) or "• None extracted"

        facts_display = json.dumps({
            k: v for k, v in facts.items()
            if k not in ('missing_fields', 'traction_signals') and v is not None
        }, indent=2)

        system_prompt = """You are a senior M&A analyst preparing an evidence-grounded business
    valuation report for a business owner considering a sale.

    ABSOLUTE RULES:
    1. Every factual claim MUST come from the extracted facts or insights provided below.
    2. Never invent numbers, projections, or metrics not present in the source data.
    3. Never use vague phrases like "healthy business" or "strong potential" without
    immediately citing specific evidence.
    4. If information is missing, write exactly: "Not disclosed in submitted documents."
    5. Write as a skeptical but fair analyst — evidence-driven, not promotional.
    6. Every section must be grounded in the provided insights or facts.
    7. valuation_low and valuation_high MUST be plain numbers (no currency symbols, no commas)
    derived from standard valuation methods (revenue multiple, EBITDA multiple, etc.) applied
    to the disclosed financials — never guess a number with no basis in the source data."""

        user_prompt = f"""Prepare a business valuation report for {facts['company']}.

    ## STRUCTURED FACTS (extracted from submitted financial documents)
    {facts_display}

    ## TRACTION SIGNALS DETECTED
    {traction}

    ## ZELDA INSIGHTS (extracted with confidence scores)
    {insights_list}

    ## INFORMATION NOT FOUND IN SUBMITTED DOCUMENTS
    {missing}

    ---

    Write the report using ONLY the above information. Return a JSON object with these exact keys:
    business_overview, financial_summary, risk_report, valuation_summary, valuation_low,
    valuation_high, confidence

    ### Instructions per section:

    business_overview: 2-3 sentences. What the business does, its stage/maturity, and its market.
    Cite specific numbers. No editorializing.

    financial_summary: Current revenue, margins, growth rate, and any other disclosed
    financial metrics. Format as bullet points. For any missing item write
    "Not disclosed in submitted documents."

    risk_report: List 3-5 specific risks based on what the documents reveal AND omit.
    Omissions are risk signals. Be specific to this business, not generic.

    valuation_summary: Explain the valuation method(s) used (e.g. revenue multiple) and how
    they were applied to the disclosed financials to reach the low/high range. If insufficient
    data exists to estimate a valuation, say so explicitly and explain what's missing.

    valuation_low / valuation_high: plain numbers (e.g. 250000), not strings with currency
    symbols. Use null for both if there isn't enough disclosed financial data to estimate a range.

    confidence: integer 0-100 reflecting how much of the valuation is grounded in real disclosed
    numbers versus assumption.

    Return ONLY valid JSON. No markdown, no backticks, no preamble."""

        from zelda_api.circuit_breaker import call_with_breaker

        try:
            response = call_with_breaker(
                'claude_api', client.messages.create,
                model="claude-sonnet-4-6",
                max_tokens=4000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            _log_anthropic_usage(response, doc, 'valuation report')

            raw = response.content[0].text.strip()

            if raw.startswith('```'):
                raw = re.sub(r'^```(?:json)?\n?', '', raw)
                raw = re.sub(r'\n?```$', '', raw)

            return json.loads(raw)

        except json.JSONDecodeError as e:
            logger.error(f"Claude valuation JSON parse error: {str(e)}")
            return {'error': f'Valuation report encountered a parsing error: {str(e)}'}
        except Exception as e:
            logger.error(f"Claude API error in valuation report generation: {str(e)}")
            return {'error': f'Valuation report generation failed: {str(e)}'}

    def _build_structured_context(self, doc: DocumentSource, insights) -> dict:
        """Extract structured facts from insights for Claude context"""
        import re

        facts = {
            'company': doc.source_entity,
            'document_type': doc.get_document_type_display(),
            'revenue': None,
            'arr': None,
            'mrr': None,
            'raise_amount': None,
            'team_size': None,
            'customers': None,
            'retention': None,
            'growth_rate': None,
            'burn_rate': None,
            'market_size': None,
            'use_of_proceeds': None,
            'traction_signals': [],
            'missing_fields': [],
        }

        # Try to pull from Application model if linked
        try:
            from matchmaking.models import Application
            app = Application.objects.filter(user=doc.uploaded_by).first()
            if app:
                if app.current_revenue:
                    facts['revenue'] = str(app.current_revenue)
                if app.raising_amount:
                    facts['raise_amount'] = str(app.raising_amount)
                if app.team_size:
                    facts['team_size'] = str(app.team_size)
                if app.monthly_burn_rate:
                    facts['burn_rate'] = str(app.monthly_burn_rate)
        except Exception:
            pass

        # Extract from insights via regex
        revenue_pattern = re.compile(
            r'\$[\d,]+(?:\.\d+)?[KMBkm]?\s*(?:ARR|MRR|revenue|recurring)?|'
            r'(?:ARR|MRR|revenue)\s*(?:of\s*)?\$[\d,]+(?:\.\d+)?[KMBkm]?',
            re.IGNORECASE
        )
        customer_pattern = re.compile(
            r'(\d+)\s*(?:paying\s*)?(?:customers|clients|users|clinics|practices|hospitals)',
            re.IGNORECASE
        )
        retention_pattern = re.compile(r'(\d+(?:\.\d+)?%)\s*(?:retention|churn)', re.IGNORECASE)
        growth_pattern = re.compile(r'(\d+(?:\.\d+)?%)\s*(?:growth|MoM|YoY|month)', re.IGNORECASE)

        for insight in insights:
            text = insight.insight_text or ''

            if not facts['arr']:
                m = revenue_pattern.search(text)
                if m:
                    facts['arr'] = m.group(0).strip()

            m = customer_pattern.search(text)
            if m:
                facts['traction_signals'].append(m.group(0).strip())

            if not facts['retention']:
                m = retention_pattern.search(text)
                if m:
                    facts['retention'] = m.group(1)

            if not facts['growth_rate']:
                m = growth_pattern.search(text)
                if m:
                    facts['growth_rate'] = m.group(1)

        # Identify missing fields
        checks = {
            'arr':             'Revenue / ARR / MRR',
            'raise_amount':    'Raise amount',
            'market_size':     'Total addressable market size',
            'use_of_proceeds': 'Use of proceeds',
            'burn_rate':       'Monthly burn rate',
            'retention':       'Customer retention / churn rate',
            'growth_rate':     'Growth rate',
        }
        for field, label in checks.items():
            if not facts[field]:
                facts['missing_fields'].append(label)

        return facts
    
    def _call_claude_for_memo(self, doc: DocumentSource, facts: dict, insights) -> dict:
        """Call Claude API to generate evidence-grounded investment memo"""
        import anthropic
        import json

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        # Format insights as numbered evidence list
        insights_list = "\n".join([
            f"{i+1}. [{ins.category} | {ins.confidence_score:.0f}% confidence] {ins.insight_text}"
            for i, ins in enumerate(insights[:25])
        ])

        missing = "\n".join([f"• {m}" for m in facts.get('missing_fields', [])]) or "• None identified"
        traction = "\n".join([f"• {t}" for t in facts.get('traction_signals', [])]) or "• None extracted"

        facts_display = json.dumps({
            k: v for k, v in facts.items()
            if k not in ('missing_fields', 'traction_signals') and v is not None
        }, indent=2)

        system_prompt = """You are a senior analyst at a top-tier venture capital firm preparing 
    an institutional-quality investment memo for a partner meeting.

    ABSOLUTE RULES:
    1. Every factual claim MUST come from the extracted facts or insights provided below.
    2. Never invent numbers, projections, or metrics not present in the source data.
    3. Never use vague phrases like "strong opportunity", "experienced team", or 
    "significant market" without immediately citing specific evidence.
    4. If information is missing, write exactly: "Not disclosed in pitch deck."
    5. Never write "Assessment based on 0 business factors" or any placeholder text.
    6. Write as a skeptical but fair analyst — evidence-driven, not promotional.
    7. Every section must be grounded in the provided insights or facts."""

        user_prompt = f"""Prepare an investment memo for {facts['company']}.

    ## STRUCTURED FACTS (extracted from pitch deck)
    {facts_display}

    ## TRACTION SIGNALS DETECTED
    {traction}

    ## ZELDA INSIGHTS (extracted with confidence scores)
    {insights_list}

    ## INFORMATION NOT FOUND IN DECK
    {missing}

    ---

    Write the memo using ONLY the above information. Return a JSON object with these exact keys:
    executive_summary, problem_solution, market_analysis, team_assessment, 
    financial_analysis, risk_assessment, investment_thesis, investment_readiness,
    questions_for_management, recommendation

    For recommendation use exactly one of: STRONG_INVEST, INVEST, NEEDS_REVIEW, PASS

    ### Instructions per section:

    executive_summary: 2-3 sentences. Company name, what they do, stage, raise amount. 
    Cite specific numbers. No editorializing.

    problem_solution: What problem do they solve? Who is the customer? 
    If not clear from deck, say so explicitly.

    market_analysis: What market? What size did they claim? 
    If no market size stated: "Market size not disclosed in pitch deck."

    team_assessment: Name founders if mentioned. State only credentials cited in deck.
    Do not invent experience. If thin on team detail, say so.

    financial_analysis: Current revenue, burn, raise amount, use of proceeds.
    Format as bullet points. For any missing item write "Not disclosed in pitch deck."

    risk_assessment: List 3-5 specific risks based on what the deck reveals AND omits.
    Omissions are risk signals. Be specific to this company, not generic.

    investment_thesis: Bull case in 2-3 sentences using only disclosed facts.
    If insufficient data: "Insufficient disclosed data to form a complete investment thesis."

    investment_readiness: Score 0-100 and list strengths/weaknesses based only on 
    what IS and IS NOT in the deck. Format:
    Score: XX/100
    Strengths: [bullet list]
    Needs Validation: [bullet list]
    Recommendation: [one sentence]

    questions_for_management: List every important question this deck does NOT answer.
    Make each question specific to THIS company, not generic.
    Base on the missing fields listed above plus analytical gaps you identify.
    Return as a bullet list. Quality over quantity.

    Return ONLY valid JSON. No markdown, no backticks, no preamble."""

        from zelda_api.circuit_breaker import call_with_breaker

        try:
            response = call_with_breaker(
                'claude_api', client.messages.create,
                model="claude-sonnet-4-6",
                max_tokens=4000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            _log_anthropic_usage(response, doc, 'memo')

            raw = response.content[0].text.strip()

            # Strip markdown fences if present
            if raw.startswith('```'):
                raw = re.sub(r'^```(?:json)?\n?', '', raw)
                raw = re.sub(r'\n?```$', '', raw)

            return json.loads(raw)

        except json.JSONDecodeError as e:
            logger.error(f"Claude memo JSON parse error: {str(e)}")
            return {'error': f'Memo generation encountered a parsing error: {str(e)}'}
        except Exception as e:
            logger.error(f"Claude API error in memo generation: {str(e)}")
            return {'error': f'Memo generation failed: {str(e)}'}
    
    
    def _determine_recommendation(self, insights, confidence: float) -> str:
        """Kept for backwards compatibility — now set by Claude directly"""
        if confidence >= 80:
            return 'STRONG_INVEST'
        elif confidence >= 65:
            return 'INVEST'
        elif confidence >= 45:
            return 'NEEDS_REVIEW'
        return 'PASS'
    # Global instance
intelligence_pipeline = ZeldaIntelligencePipelineV2()


# --- "ASK ZELDA" NATURAL-LANGUAGE FOUNDER SEARCH ---
# Standalone (not a pipeline method) — unlike memo/valuation generation, this
# has no DocumentSource/insights to operate on. Kept in this file anyway so
# every real Anthropic call site stays discoverable in one place.

ASK_ZELDA_ALLOWED_FIELDS = {
    'sector': 'string',
    'stage': 'string',
    'geography': 'string',
    'raising_amount': 'number',
    'monthly_burn_rate': 'number',
    'years_in_business': 'number',
    'current_revenue': 'number',
    'team_size': 'number',
    'prior_amount_raised': 'number',
}

# Buyer-side equivalent — the same allowlist/relax/query machinery below
# works unchanged against SellerApplication once given this field map
# instead, since it only ever looks up field names by string.
ASK_ZELDA_SELLER_ALLOWED_FIELDS = {
    'industry': 'string',
    'geography': 'string',
    'asking_price': 'number',
    'annual_revenue': 'number',
    'ebitda': 'number',
    'years_in_business': 'number',
    'team_size': 'number',
}

_ASK_ZELDA_EXTRACTION_PROMPTS = {
    'founder': """You translate a natural-language founder search into
structured constraints. You do NOT answer the question yourself — you only
extract what to filter on.

Allowed fields: sector, stage, geography, raising_amount, monthly_burn_rate,
years_in_business, current_revenue, team_size, prior_amount_raised.

For each fact mentioned, emit one constraint:
{"field": <allowed field>, "qualifier": "at_least"|"at_most"|"exact"|"about", "value": <number or string>}

Qualifier guidance:
- "at least X" / "over X" / "above X" / "minimum X" -> at_least
- "at most X" / "under X" / "only X" / "no more than X" / "maximum X" -> at_most
- a plain stated amount with no hedge (e.g. "seeking $3,000,000") -> about
- an exact discrete fact (e.g. "founded 5 years ago", "team of 8") -> exact
- string fields (sector/stage/geography) always use qualifier "exact" — ignore hedges for these

Never invent a field not in the allowed list, and never invent a value not
stated or clearly implied by the question.

If the question contains no identifiable founder-search criteria, return
{"constraints": []}.

Return ONLY valid JSON: {"constraints": [...]}. No markdown, no backticks, no preamble.""",

    'seller': """You translate a natural-language search for a business-for-sale
listing into structured constraints. You do NOT answer the question yourself
— you only extract what to filter on.

Allowed fields: industry, geography, asking_price, annual_revenue, ebitda,
years_in_business, team_size.

For each fact mentioned, emit one constraint:
{"field": <allowed field>, "qualifier": "at_least"|"at_most"|"exact"|"about", "value": <number or string>}

Qualifier guidance:
- "at least X" / "over X" / "above X" / "minimum X" -> at_least
- "at most X" / "under X" / "only X" / "no more than X" / "maximum X" -> at_most
- a plain stated amount with no hedge (e.g. "priced around $9,500,000") -> about
- an exact discrete fact (e.g. "founded 8 years ago", "team of 45") -> exact
- string fields (industry/geography) always use qualifier "exact" — ignore hedges for these

Never invent a field not in the allowed list, and never invent a value not
stated or clearly implied by the question. Note "EBITDA under $5M" maps to
field "ebitda", qualifier "at_most" — never invent a "profit" or "earnings"
field name that isn't in the allowed list.

If the question contains no identifiable business-search criteria, return
{"constraints": []}.

Return ONLY valid JSON: {"constraints": [...]}. No markdown, no backticks, no preamble.""",
}


def _call_claude_for_query_extraction(question: str, target: str = 'founder') -> dict:
    """
    Translate a free-text search into an allowlisted constraint list, for
    either a founder search (target='founder', the default — what an
    investor asks) or a seller/business-for-sale search (target='seller'
    — what a buyer asks). Claude never sees the database and never writes
    the text shown to the user — it only extracts what to filter on. The
    actual query results and result count (computed by Django from real
    data) are what get displayed, so there's nothing here for the model
    to hallucinate about.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    system_prompt = _ASK_ZELDA_EXTRACTION_PROMPTS.get(target, _ASK_ZELDA_EXTRACTION_PROMPTS['founder'])

    from zelda_api.circuit_breaker import call_with_breaker

    try:
        response = call_with_breaker(
            'claude_api', client.messages.create,
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": question}],
        )
        _log_anthropic_usage(response, None, 'nl query extraction')

        raw = response.content[0].text.strip()

        if raw.startswith('```'):
            raw = re.sub(r'^```(?:json)?\n?', '', raw)
            raw = re.sub(r'\n?```$', '', raw)

        parsed = json.loads(raw)
        if not isinstance(parsed, dict) or not isinstance(parsed.get('constraints'), list):
            return {'constraints': []}
        return parsed

    except json.JSONDecodeError as e:
        logger.error(f"Ask Zelda JSON parse error: {str(e)}")
        return {'constraints': []}


def _apply_constraints_to_queryset(queryset, constraints, relax=False, allowed_fields=None):
    """
    Applies an allowlisted, type-checked constraint list to a queryset.
    Constraints come from Claude's output — untrusted input, not a trusted
    internal call — so an unknown field or a value that won't coerce to the
    expected type is silently skipped rather than raised. Only field names
    from allowed_fields (defaults to ASK_ZELDA_ALLOWED_FIELDS, the founder
    schema) ever reach the ORM, and every value goes through Django's
    normal parameterized filtering — no raw SQL, no way for Claude to name
    an arbitrary field or inject a query fragment. Pass
    ASK_ZELDA_SELLER_ALLOWED_FIELDS to run the identical logic against a
    SellerApplication queryset instead — this function only ever looks
    fields up by name, so it's schema-agnostic.

    "about" is deliberately resolved to a tolerance band here, on the
    server, rather than left to Claude — keeps the behavior deterministic
    and testable independent of what the model returns.

    relax=True widens every numeric band (used by _search_with_relaxation's
    "closest match" fallback below) — about's +/-15% band widens to +/-30%,
    at_least/at_most gain a 20% slack margin, and an "exact" numeric value
    becomes a +/-15% band instead of a hard equality check, so a founder
    just outside a strict cutoff still surfaces as a close match. String
    constraints (sector/stage/geography) are never relaxed — widening those
    would change *what kind* of founder is being searched for, not just
    how strict the match is.
    """
    if allowed_fields is None:
        allowed_fields = ASK_ZELDA_ALLOWED_FIELDS

    for constraint in constraints:
        if not isinstance(constraint, dict):
            continue

        field = constraint.get('field')
        field_type = allowed_fields.get(field)
        if field_type is None:
            continue

        value = constraint.get('value')
        qualifier = constraint.get('qualifier', 'exact')

        if field_type == 'string':
            if not isinstance(value, str) or not value.strip():
                continue
            queryset = queryset.filter(**{f'{field}__icontains': value.strip()})
            continue

        # field_type == 'number'
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue

        slack = 0.20 if relax else 0.0
        about_band = 0.30 if relax else 0.15

        if qualifier == 'at_least':
            queryset = queryset.filter(**{f'{field}__gte': value * (1 - slack)})
        elif qualifier == 'at_most':
            queryset = queryset.filter(**{f'{field}__lte': value * (1 + slack)})
        elif qualifier == 'about':
            queryset = queryset.filter(**{f'{field}__gte': value * (1 - about_band), f'{field}__lte': value * (1 + about_band)})
        else:  # 'exact', or an unrecognized qualifier — safest fallback
            if relax:
                queryset = queryset.filter(**{f'{field}__gte': value * 0.85, f'{field}__lte': value * 1.15})
            else:
                queryset = queryset.filter(**{f'{field}__exact': value})

    return queryset


def _constraint_label(constraint):
    """Human-readable description of one constraint, for relaxation messages."""
    field = constraint.get('field', '').replace('_', ' ')
    value = constraint.get('value', '')
    qualifier = constraint.get('qualifier', 'exact')
    if qualifier == 'at_least':
        return f"{field} of at least {value}"
    elif qualifier == 'at_most':
        return f"{field} of at most {value}"
    return f"{field} of {value}"


def _search_with_relaxation(queryset, constraints, limit=10, allowed_fields=None):
    """
    Runs the constraint list as given first. If that returns zero results,
    progressively relaxes the search instead of just reporting "no
    matches": first widening numeric tolerances (see relax=True above),
    then dropping numeric constraints one at a time — most-recently-stated
    first — and finally dropping string constraints too if nothing else
    works. String constraints are dropped last because they define *what
    kind* of founder (or business, for a seller search — pass
    ASK_ZELDA_SELLER_ALLOWED_FIELDS) was asked for; numeric constraints
    (burn rate/asking price, years in business, etc.) are what usually
    over-narrows a search.

    Every relaxation step is reported back so a "closest match" response
    never silently substitutes a different search than what was asked for.

    Returns (matches, dropped_labels, widened_only):
    - dropped_labels: human-readable constraints that were removed to find
      a result (empty if nothing was dropped)
    - widened_only: True if results came only from widening numeric
      tolerances, without dropping anything
    """
    if allowed_fields is None:
        allowed_fields = ASK_ZELDA_ALLOWED_FIELDS

    matches = list(_apply_constraints_to_queryset(queryset, constraints, allowed_fields=allowed_fields)[:limit])
    if matches:
        return matches, [], False

    matches = list(_apply_constraints_to_queryset(queryset, constraints, relax=True, allowed_fields=allowed_fields)[:limit])
    if matches:
        return matches, [], True

    numeric_indices = [
        i for i, c in enumerate(constraints)
        if isinstance(c, dict) and allowed_fields.get(c.get('field')) == 'number'
    ]
    remaining = list(constraints)
    dropped = []
    for idx in reversed(numeric_indices):
        dropped.append(remaining.pop(idx))
        matches = list(_apply_constraints_to_queryset(queryset, remaining, relax=True, allowed_fields=allowed_fields)[:limit])
        if matches:
            return matches, [_constraint_label(c) for c in dropped], False

    while remaining:
        dropped.append(remaining.pop())
        matches = list(_apply_constraints_to_queryset(queryset, remaining, allowed_fields=allowed_fields)[:limit])
        if matches:
            return matches, [_constraint_label(c) for c in dropped], False

    return [], [], False