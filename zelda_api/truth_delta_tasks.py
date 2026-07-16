# zelda_api/truth_delta_tasks.py
"""
Celery async tasks for Truth Delta verification.
Runs in background to fetch external data and calculate credibility scores.
"""
import hashlib
import logging
from celery import shared_task
from django.utils import timezone
from .vector_models import DocumentSource
from .truth_delta_engine import TruthDeltaEngine
from .truth_delta_models import ClaimedDatapoint

logger = logging.getLogger(__name__)


@shared_task
def extract_claims_from_insights(document_id: int):
    """
    Extract claimed datapoints from intelligence insights.
    Called after IntelligenceInsight objects are created.

    Maps insights to claims that can be verified. The category names here
    must match IntelligenceInsight.category exactly as produced by
    ZeldaIntelligencePipelineV2._analyze_document's analysis_categories
    dict (Problem/Market/Revenue/Team/Product/Traction/Funding/Risk) —
    Problem/Product/Risk are deliberately excluded since they're narrative,
    not numeric, and have nothing for Truth Delta to verify.

    This previously did a fuzzy substring scan against keys ('Customer',
    'Growth', 'Users') that don't match any category _analyze_document
    ever actually generates ('Traction', 'Market' are the real names) —
    so Traction and Market insights, however well-extracted, could never
    become a ClaimedDatapoint and reach Truth Delta at all. A direct
    lookup against the real category names is both a fix and a
    simplification.
    """
    try:
        from .vector_models import IntelligenceInsight

        logger.info(f"[Truth Delta] Extracting claims from insights for document {document_id}")

        document = DocumentSource.objects.get(id=document_id)
        insights = IntelligenceInsight.objects.filter(document=document)

        claims_created = 0

        # Map insight categories to claim categories
        category_mapping = {
            'Revenue': 'revenue',
            'Traction': 'customers',
            'Team': 'employees',
            'Funding': 'funding_raised',
            'Market': 'market_size',
        }

        for insight in insights:
            matched_category = category_mapping.get(insight.category)

            if not matched_category:
                continue
            
            # Extract numeric value from insight text
            numeric_value = _extract_numeric_value(insight.insight_text)
            
            if numeric_value is None:
                logger.debug(f"Could not extract numeric value from insight: {insight.insight_text}")
                continue
            
            # Create claimed datapoint, with full provenance back to the source chunk
            source_chunk_obj = insight.source_chunks.first()
            claim = ClaimedDatapoint.objects.create(
                document=document,
                category=matched_category,
                claimed_value=insight.insight_text[:255],  # Truncate if needed
                claimed_value_numeric=numeric_value,
                unit=insight.metric_unit or '',
                source_chunk=f"Insight: {insight.category}",
                confidence_in_extraction=insight.confidence_score,
                page_number=source_chunk_obj.page_number if source_chunk_obj else None,
                text_excerpt=source_chunk_obj.raw_text if source_chunk_obj else '',
                chunk_hash=hashlib.sha256(source_chunk_obj.raw_text.encode()).hexdigest() if source_chunk_obj else '',
            )
            
            claims_created += 1
            logger.debug(f"Created claim: {claim}")
        
        logger.info(f"[Truth Delta] Created {claims_created} claims from insights")
        
        # Queue verification
        verify_document_truth_delta.delay(document_id)
        
        return {'status': 'success', 'claims_created': claims_created}
    
    except Exception as exc:
        logger.error(f"Error extracting claims: {str(exc)}")
        return {'status': 'error', 'error': str(exc)}


# Helper functions

def _extract_numeric_value(text: str) -> float:
    """
    Extract first numeric value from text.
    Handles formats like: "$1M", "$416 billion", "500 customers", "200% growth", etc.

    The multiplier is read only from a token immediately adjacent to the
    matched digits — never from anywhere else in the sentence. Scanning
    the whole string (an earlier version of this function) meant a
    sentence merely containing the letter "M" (e.g. "...Marketing spend
    of $500...") would spuriously multiply an unrelated number by
    1,000,000.

    Recognizes both the abbreviated form (K/M/B, e.g. "$1M") and the
    spelled-out word (thousand/million/billion, e.g. "$416 billion") —
    real prose (SEC filings, investor updates) overwhelmingly uses the
    spelled-out form, which a K/M/B-only check silently drops: "$416
    billion" would parse as bare "416" with no multiplier, since the
    letter right after "billion" always defeats the old single-letter
    adjacency check. That's not a missing claim (which recall would
    catch) — it's a claim that looks successful but is off by a factor
    of a billion, which is worse.
    """
    import re

    if not text:
        return None

    # Percentages first, so "200%" never also picks up a stray multiplier
    # from elsewhere in the sentence.
    percent_match = re.search(r'([\d,]*\.?\d+)\s*%', text)
    if percent_match:
        try:
            return float(percent_match.group(1).replace(',', ''))
        except ValueError:
            pass

    # Currency/count, with an optional multiplier directly after the
    # digits — either the single-letter form or the spelled-out word.
    # The trailing negative lookahead rejects ambiguous adjacent-letter
    # cases (e.g. "1Mbps", "$50 billionaire") rather than guessing.
    match = re.search(
        r'\$?([\d,]*\.?\d+)\s*(thousand\b|million\b|billion\b|[kmb])?(?![a-zA-Z])',
        text, re.IGNORECASE,
    )
    if not match:
        return None

    try:
        numeric_value = float(match.group(1).replace(',', ''))
    except ValueError:
        return None

    suffix = (match.group(2) or '').lower()
    if suffix in ('k', 'thousand'):
        numeric_value *= 1_000
    elif suffix in ('m', 'million'):
        numeric_value *= 1_000_000
    elif suffix in ('b', 'billion'):
        numeric_value *= 1_000_000_000

    return numeric_value

@shared_task
def verify_document_truth_delta(document_id):
    engine = TruthDeltaEngine()
    result = engine.verify_document(document_id)
    
    # Return JSON-serializable dict, not a Django model object
    if result is None:
        return {'status': 'no_claims', 'document_id': document_id}
    
    return {
        'status': 'success',
        'document_id': document_id,
        'report_id': result.id if hasattr(result, 'id') else None,
    }