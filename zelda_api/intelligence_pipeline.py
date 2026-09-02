
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

    # Categories where a number is a claim ABOUT the subject company —
    # narrative categories (Problem/Product/Risk) are exempt from the
    # third-party-attribution check below, since "risk: competition from
    # larger incumbents" is legitimate content, not a misattributed number.
    NUMERIC_CATEGORIES = {'Revenue', 'Funding', 'Team', 'Traction', 'Market'}

    # A number attributed to a competitor/rival/peer isn't a claim about
    # THIS company, however well the sentence otherwise matches a
    # category's keywords (e.g. "Our competitor reported $200M in
    # revenue" must never become a revenue claim about us). Pragmatic
    # phrase-proximity check, not full entity resolution — escalate to
    # real NER/entity-linking only if false positives persist despite
    # this (see evaluation_corpus.py's solstice_competitor_revenue_trap).
    THIRD_PARTY_ATTRIBUTION_PATTERN = re.compile(
        r'\b(competitor|competitors|rival|rivals|peer|peers|another company|other companies|industry leader|according to \S+)\b',
        re.IGNORECASE,
    )

    # 'growth' is a genuine, useful Traction signal on its own (e.g.
    # "212% YoY growth in customers"), but the same word shows up
    # constantly in ordinary revenue prose ("$270B... driven by growth
    # in Azure"). Found via the 98-document evaluation corpus: every
    # real false positive of this shape was a revenue sentence carrying
    # a dollar figure that also happened to mention "growth" in passing.
    # Only suppressed when 'growth' is the SOLE reason a sentence
    # matched Traction at all — a sentence with a genuine
    # customer/user-specific word alongside "growth" is unaffected.
    REVENUE_DOLLAR_CONTEXT_PATTERN = re.compile(
        r'\brevenue\b.{0,60}\$[\d,\.]|\$[\d,\.]+.{0,60}\brevenue\b',
        re.IGNORECASE,
    )

    # The 8 fixed categories every document is analyzed against — hoisted
    # to a class constant (was a local dict inside _analyze_document) so
    # confidence_breakdown.py can share the exact same canonical category
    # list rather than re-deriving or hardcoding its own, which would
    # silently drift if this list ever changes.
    ANALYSIS_CATEGORIES = {
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

            for category, keywords in self.ANALYSIS_CATEGORIES.items():
                best_insight = None
                best_confidence = 0

                # Search each chunk independently. On a tie, prefer whichever
                # chunk's result has a dollar figure — mirrors _smart_extract's
                # own within-chunk tie-break (its two candidate sentences
                # never cross a chunk boundary, so that logic alone doesn't
                # cover this case). Without it, a qualitative sentence like
                # "Recurring subscription revenue model." (95 confidence, no
                # number) permanently wins over a later chunk's "Current
                # Revenue: $4.5M" (also 95) purely because its chunk happens
                # to come first — found live when a Qibby Saves valuation
                # used that qualitative sentence as the Revenue insight and
                # the actual $4.5M figure never surfaced at all.
                for chunk in chunks:
                    result, confidence, provenance = self._smart_extract(category, chunk.raw_text, keywords)
                    if not result:
                        continue
                    is_better = confidence > best_confidence or (
                        confidence == best_confidence and best_insight is not None and
                        re.search(r'\$[\d,]+[MBK]?', result) and
                        not re.search(r'\$[\d,]+[MBK]?', best_insight[0])
                    )
                    if is_better:
                        best_confidence = confidence
                        best_insight = (result, confidence, chunk, provenance)

                if best_insight:
                    insight_text, confidence, source_chunk, provenance = best_insight

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
                    # In-memory only, never persisted — see _smart_extract's
                    # docstring. Read by evaluate_claim_extraction --verbose.
                    insight.extraction_provenance = provenance
                    insights.append(insight)
            
            logger.info(f"Extracted {len(insights)} insights with dynamic confidence")
            # Local import: confidence_breakdown imports this module at
            # load time, so importing it back at module scope here would
            # be circular. Quality-weighted average across all 8 canonical
            # categories (missing ones count as 0), not just "how many
            # categories got any insight" — see compute_overall_confidence's
            # docstring for why that distinction matters.
            from .confidence_breakdown import compute_overall_confidence
            return {
                'insights': insights,
                'confidence': compute_overall_confidence(insights),
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
            insight_text, confidence, _provenance = self._smart_extract(category, raw_text, keywords)

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
    
    def _smart_extract(self, category: str, text: str, keywords: str) -> Tuple[Optional[str], float, Optional[Dict]]:
        """
        Smart extraction with DYNAMIC confidence scoring.
        Confidence logic:
        - Explicit number match: 95%
        - Exact phrase match: 85%
        - Keyword match with context: 70%
        - Generic/inferred: 45%

        Also returns a provenance dict — {'rule', 'matched_keywords',
        'matched_sentence'} — alongside the usual (value, confidence).
        This is debugging/evaluation metadata, not new production
        storage: nothing here is written to IntelligenceInsight or any
        other model field, it only rides along in-memory for
        evaluate_claim_extraction --verbose to surface. When "Revenue
        precision dropped" is the only signal a regression gives you,
        finding the cause means re-deriving which rule fired and on
        which sentence by hand; carrying that through as it's computed
        (this function already knows it) is a lot cheaper than that.
        """
        keyword_list = keywords.split()
        sentences = re.split(r'(?<!\d)[.!?](?!\d)|\n', text)

        best_match = None
        best_confidence = 0
        best_provenance = None

        for sentence in sentences:
            sentence_lower = sentence.lower()

            # Word-boundary match, not substring containment — the old
            # `kw in sentence_lower` check meant Team's keyword "team"
            # matched inside "teams" (e.g. "...for enterprise AI teams"
            # in a funding sentence, with nothing to do with headcount),
            # and Funding's short keyword "ask" matched inside unrelated
            # words like "task"/"basket". Found via the 98-document
            # evaluation corpus, where precision dropped once sector
            # diversity exposed how often this fired.
            matched_keywords = [kw for kw in keyword_list if re.search(rf'\b{re.escape(kw.lower())}\b', sentence_lower)]

            if not matched_keywords:
                continue

            clean_sentence = sentence.strip()

            if category in self.NUMERIC_CATEGORIES and self.THIRD_PARTY_ATTRIBUTION_PATTERN.search(clean_sentence):
                continue

            if category == 'Traction' and matched_keywords == ['growth'] and self.REVENUE_DOLLAR_CONTEXT_PATTERN.search(clean_sentence):
                continue

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
                best_provenance = {
                    'rule': 'primary_match', 'matched_keywords': matched_keywords, 'matched_sentence': clean_sentence,
                }

        if not best_match:
            fallback = self._get_smart_fallback(category, text)
            if fallback is None:
                return None, 0.0, None
            return fallback, 35.0, {'rule': 'fallback', 'matched_keywords': [], 'matched_sentence': fallback}

        return best_match, best_confidence, best_provenance

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
        that can be safely attributed to any one category. Also skips any
        sentence attributing its number to a competitor/rival/peer — see
        THIRD_PARTY_ATTRIBUTION_PATTERN.
        """
        for sentence in re.split(r'(?<!\d)[.!?](?!\d)|\n', text):
            if ZeldaIntelligencePipelineV2.THIRD_PARTY_ATTRIBUTION_PATTERN.search(sentence):
                continue
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
                    'key_strengths':      memo_sections.get('key_strengths', ''),
                    'key_concerns':       memo_sections.get('key_concerns', ''),
                    'what_would_change_decision': memo_sections.get('what_would_change_decision', ''),
                    'bull_case':          memo_sections.get('bull_case', ''),
                    'base_case':          memo_sections.get('base_case', ''),
                    'bear_case':          memo_sections.get('bear_case', ''),
                    'zelda_advantage':    memo_sections.get('zelda_advantage', ''),
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
                'sections_count': 16,
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
            if k not in ('missing_fields', 'traction_signals', '_provenance') and v is not None
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

    @staticmethod
    def _values_agree(document_value: str, profile_value: str) -> bool:
        """
        Whether a document-extracted string ("$20M", "200 employees") and
        a profile-sourced string ("20000000.00", "120") represent the same
        real-world quantity. Reuses truth_delta_tasks' numeric-value parser
        (already handles "$1M"/"$416 billion"/"500 customers" etc.) rather
        than a fresh one, so "K/M/B" parsing stays consistent with how the
        rest of the app already reads these figures. Compared with a small
        relative tolerance (1%) rather than exact equality, since "$4.5M"
        parsed against a profile figure of 4,500,001 shouldn't read as a
        genuine conflict over a rounding artifact.
        """
        from .truth_delta_tasks import _extract_numeric_value
        document_num = _extract_numeric_value(document_value)
        profile_num = _extract_numeric_value(profile_value)
        if document_num is None or profile_num is None:
            return False
        if profile_num == 0:
            return document_num == 0
        return abs(document_num - profile_num) / abs(profile_num) <= 0.01

    def _build_structured_context(self, doc: DocumentSource, insights) -> dict:
        """
        Extract structured facts from insights for Claude context.

        Provenance precedence: when both the uploader's own (company-
        matched) founder profile AND the document itself state a value for
        the same field, the DOCUMENT wins — profile fields can go stale (a
        founder's saved team_size from months ago) while the deck actually
        being analyzed right now is the more current source of truth.
        facts['_provenance'] records, per reconciled field, which source
        won and — for document-sourced values — the confidence of the
        insight that backs it, so a claim can be traced to real evidence
        instead of asserted flatly. Stripped from facts_display before it
        reaches Claude (see _call_claude_for_valuation/_call_claude_for_memo).
        """
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
            '_provenance': {},
        }

        # Try to pull from the uploader's own Application model — but ONLY
        # if it's actually about the company this document is analyzing.
        # A real bug, found live: the uploader's own founder profile fields
        # were trusted unconditionally, regardless of whose deck they'd
        # actually just uploaded. An admin account with its own unrelated
        # "Gmail" founder profile (raising_amount=$50,000) uploaded a
        # standalone valuation for "Qibby Saves LLC" — the Gmail profile's
        # $50,000 leaked into the Qibby report as "capital currently being
        # raised," alongside the correctly-extracted "$20M Series-C" from
        # the deck's own insight text, a glaring, credibility-damaging
        # inconsistency. This only matters for third-party/standalone
        # valuation uploads (an investor or admin analyzing someone else's
        # company) — a founder uploading their own deck through their own
        # dashboard still gets their verified fields, since the company
        # names naturally match there.
        # Kept separate from `facts` (not written in directly) so the
        # document-extraction pass below can reconcile the two sources
        # afterward with a clear precedence rule, rather than the profile
        # value silently pre-populating `facts` and never being checked
        # against what the document itself says.
        profile_values = {}
        try:
            from matchmaking.models import Application, _normalize_company_string
            app = Application.objects.filter(user=doc.uploaded_by).first()
            normalized_doc_company = _normalize_company_string(doc.source_entity)
            normalized_app_company = _normalize_company_string(app.company_name) if app else ''
            company_matches = bool(normalized_doc_company) and bool(normalized_app_company) and (
                normalized_doc_company in normalized_app_company or normalized_app_company in normalized_doc_company
            )
            if app and company_matches:
                if app.current_revenue:
                    profile_values['revenue'] = str(app.current_revenue)
                if app.raising_amount:
                    profile_values['raise_amount'] = str(app.raising_amount)
                if app.team_size:
                    profile_values['team_size'] = str(app.team_size)
                if app.monthly_burn_rate:
                    facts['burn_rate'] = str(app.monthly_burn_rate)
        except Exception:
            pass

        # Extract from insights via regex. The keyword is mandatory on both
        # alternatives — a bare dollar figure with no adjacent revenue
        # keyword must NOT match, otherwise any dollar amount elsewhere in
        # the deck (a funding ask, prior capital raised, a use-of-proceeds
        # line item) gets misread as ARR. This is a real bug that was
        # caught live: "Current Revenue: $4.5M" alongside "Seeking: $20M
        # Series-C funding" produced a valuation built on $20M ARR instead
        # of the deck's actual $4.5M, because the old pattern's trailing
        # `(?:ARR|MRR|revenue|recurring)?` was optional, so it matched the
        # unrelated $20M figure first.
        revenue_pattern = re.compile(
            r'(?:current\s+)?(?:ARR|MRR|revenue|recurring\s+revenue)\s*(?:of|is|was|:)?\s*\$[\d,]+(?:\.\d+)?[KMBkm]?|'
            r'\$[\d,]+(?:\.\d+)?[KMBkm]?\s*(?:in\s+)?(?:ARR|MRR|revenue|recurring\s+revenue)',
            re.IGNORECASE
        )
        # Distinct from revenue_pattern's keyword set on purpose — "seeking
        # $20M" / "$20M Series-C" describe a raise, not revenue, and must
        # never satisfy revenue_pattern's own match.
        raise_amount_pattern = re.compile(
            r'(?:seeking|raising|ask(?:ing)?)[^\$\n]{0,25}\$[\d,]+(?:\.\d+)?[KMBkm]?|'
            r'\$[\d,]+(?:\.\d+)?[KMBkm]?[^\n]{0,20}(?:series[\s-][a-z0-9]+|funding\s+round|raise)',
            re.IGNORECASE
        )
        team_size_pattern = re.compile(r'\d+[\s\-]*(?:employees|person\s+team|team\s+members|people|staff)', re.IGNORECASE)
        # _extract_clean_value's own Revenue branch (see _calculate_confidence
        # / _extract_clean_value) already strips a Revenue-category insight
        # down to close to a bare dollar figure (e.g. "Current Revenue:
        # $4.5M" -> "$4.5M" with no adjacent keyword left at all) before it
        # ever reaches this function — so requiring the keyword adjacency
        # revenue_pattern needs for OTHER categories would make a genuine
        # Revenue-category insight's own figure unmatchable. Safe to use a
        # bare-figure pattern only when the insight's category already is
        # 'Revenue' (that's the disambiguator revenue_pattern's keyword
        # requirement exists to substitute for on other categories).
        bare_amount_pattern = re.compile(r'\$[\d,]+(?:\.\d+)?[KMBkm]?', re.IGNORECASE)
        customer_pattern = re.compile(
            r'(\d+)\s*(?:paying\s*)?(?:customers|clients|users|clinics|practices|hospitals)',
            re.IGNORECASE
        )
        retention_pattern = re.compile(r'(\d+(?:\.\d+)?%)\s*(?:retention|churn)', re.IGNORECASE)
        growth_pattern = re.compile(r'(\d+(?:\.\d+)?%)\s*(?:growth|MoM|YoY|month)', re.IGNORECASE)

        # Revenue-category insights first (see _analyze_document's fixed
        # categories) — a Funding or Traction insight can still mention a
        # dollar figure alongside an unrelated word the tightened regex
        # allows through, so preferring the insight actually about revenue
        # avoids cross-category mismatches even with the stricter pattern.
        revenue_insights = [i for i in insights if i.category == 'Revenue']
        other_insights = [i for i in insights if i.category != 'Revenue']

        # Tracks which insight backed each document-extracted value, so the
        # reconciliation step below can record real provenance (confidence,
        # not just "yes/no it came from the document").
        document_source_insight = {}

        for insight in revenue_insights + other_insights:
            text = insight.insight_text or ''

            if not facts['arr']:
                pattern = bare_amount_pattern if insight.category == 'Revenue' else revenue_pattern
                m = pattern.search(text)
                if m:
                    facts['arr'] = m.group(0).strip()
                    document_source_insight['revenue'] = insight

            if not facts['raise_amount']:
                m = raise_amount_pattern.search(text)
                if m:
                    facts['raise_amount'] = m.group(0).strip()
                    document_source_insight['raise_amount'] = insight

            if not facts['team_size']:
                m = team_size_pattern.search(text)
                if m:
                    facts['team_size'] = m.group(0).strip()
                    document_source_insight['team_size'] = insight

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

        # Reconcile document-extracted vs. profile-sourced values for the
        # three fields that can come from either. Four mutually-exclusive
        # states, richer than a flat "which source won" flag:
        #   confirmed      — both sources exist and agree (numerically).
        #   document_only  — only the document has a value.
        #   profile_only   — only the profile has a value.
        #   conflict       — both exist and disagree; document is still
        #                    selected (see this method's docstring), but
        #                    the disagreement itself is preserved rather
        #                    than silently discarded, so a real mismatch
        #                    (a stale profile field vs. what the deck
        #                    currently says) is visible for debugging or a
        #                    future "these sources disagree" warning,
        #                    rather than only ever being inferable from
        #                    which single value happened to end up in the
        #                    prompt. 'revenue' is exposed under its own key
        #                    but extracted into 'arr' above (kept as a
        #                    separate field for backward compatibility
        #                    with existing callers of that name), so it
        #                    needs the alias below.
        document_field_alias = {'revenue': 'arr'}
        for field in ('revenue', 'raise_amount', 'team_size'):
            document_value = facts[document_field_alias.get(field, field)]
            profile_value = profile_values.get(field)
            source_insight = document_source_insight.get(field)

            if document_value and profile_value:
                facts[field] = document_value
                status = 'confirmed' if self._values_agree(document_value, profile_value) else 'conflict'
                facts['_provenance'][field] = {
                    'status': status,
                    'source': 'document',
                    'document_value': document_value,
                    'profile_value': profile_value,
                    'document_id': doc.id,
                    'confidence': source_insight.confidence_score if source_insight else None,
                }
            elif document_value:
                facts[field] = document_value
                facts['_provenance'][field] = {
                    'status': 'document_only',
                    'source': 'document',
                    'document_value': document_value,
                    'profile_value': None,
                    'document_id': doc.id,
                    'confidence': source_insight.confidence_score if source_insight else None,
                }
            elif profile_value:
                facts[field] = profile_value
                facts['_provenance'][field] = {
                    'status': 'profile_only',
                    'source': 'profile',
                    'document_value': None,
                    'profile_value': profile_value,
                    'document_id': None,
                    'confidence': None,
                }

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
            if k not in ('missing_fields', 'traction_signals', '_provenance') and v is not None
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
    key_strengths, key_concerns, what_would_change_decision,
    bull_case, base_case, bear_case, zelda_advantage,
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

    key_strengths: 2-4 bullet points, each citing one specific disclosed fact or insight
    (not a generic quality like "strong team") that supports investing. If fewer than 2
    genuine strengths are evidenced, list only what is actually supported — never pad
    with generic praise.

    key_concerns: 2-4 bullet points, each citing a specific gap, omission, or disclosed
    weakness relevant to the investment decision. Reuse risk_assessment's evidence but
    frame each as "why this matters to the decision," not a restated risk list. If two
    disclosed facts contradict each other, name that contradiction specifically.

    what_would_change_decision: 1-2 sentences naming the single most important missing
    piece of evidence that, if disclosed and favorable, would most change this
    recommendation. Be specific ("audited financials showing gross margin" not "more
    information"). If the deck is already comprehensive, say so explicitly.

    bull_case: 2-3 sentences making the strongest evidence-grounded case FOR investing,
    using the most favorable reasonable reading of the disclosed facts. Cite only real
    evidence — never invent upside the deck doesn't support.

    base_case: 2-3 sentences describing the most likely outcome if disclosed facts and
    current trajectory hold — neither the best nor worst case.

    bear_case: 2-3 sentences making the strongest evidence-grounded case AGAINST
    investing, citing specific disclosed gaps or weaknesses — not generic startup risk.

    zelda_advantage: 1-2 sentences on what this evidence-grounded pass specifically
    surfaced (a cross-checked claim, a contradiction, a notable omission) that a plain
    AI summary of the same deck would likely miss. This is NOT platform marketing — if
    nothing distinctive was found, say exactly: "No material discrepancies identified
    beyond what is stated in the deck."

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