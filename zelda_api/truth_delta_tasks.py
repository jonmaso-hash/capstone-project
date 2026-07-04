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
    
    Maps insights to claims that can be verified:
    - Revenue insight → Claimed revenue
    - Employee count insight → Claimed employee count
    - Growth rate insight → Claimed growth rate
    - etc.
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
            'Customer': 'customers',
            'Growth': 'growth_rate',
            'Team': 'employees',
            'Funding': 'funding_raised',
            'Users': 'user_count',
        }
        
        for insight in insights:
            # Try to match insight to a claim category
            matched_category = None
            for key, category in category_mapping.items():
                if key.lower() in insight.category.lower():
                    matched_category = category
                    break
            
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
    Handles formats like: "$1M", "500 customers", "200% growth", etc.
    """
    import re
    
    if not text:
        return None
    
    # Try to find numeric value with optional currency/percent
    patterns = [
        r'\$?([\d,\.]+)(?:\s*[KkMmBb])?',  # $1M, 1,000, 0.5, etc
        r'([\d,\.]+)\s*%',                   # 200%, 0.5%, etc
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                # Remove commas and convert
                value_str = match.group(1).replace(',', '')
                numeric_value = float(value_str)
                
                # Handle K, M, B multipliers
                if 'K' in text or 'k' in text:
                    numeric_value *= 1_000
                if 'M' in text or 'm' in text:
                    numeric_value *= 1_000_000
                if 'B' in text or 'b' in text:
                    numeric_value *= 1_000_000_000
                
                return numeric_value
            except ValueError:
                continue
    
    return None

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