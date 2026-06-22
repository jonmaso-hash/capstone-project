# zelda_api/truth_delta_tasks.py
"""
Celery async tasks for Truth Delta verification.
Runs in background to fetch external data and calculate credibility scores.
"""
import logging
from celery import shared_task
from django.utils import timezone
from .vector_models import DocumentSource
from .truth_delta_engine import TruthDeltaOrchestrator, TruthDeltaEngine
from .truth_delta_sources import DataSourceManager
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
            
            # Create claimed datapoint
            claim = ClaimedDatapoint.objects.create(
                document=document,
                category=matched_category,
                claimed_value=insight.insight_text[:255],  # Truncate if needed
                claimed_value_numeric=numeric_value,
                unit=insight.metric_unit or '',
                source_chunk=f"Insight: {insight.category}",
                confidence_in_extraction=insight.confidence_score,
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


@shared_task
def batch_verify_documents():
    """
    Batch task: Verify all documents that haven't been analyzed yet.
    Run on a schedule (e.g., every 6 hours).
    """
    try:
        from .truth_delta_models import TruthDeltaScore
        
        # Find documents without verification
        unverified = DocumentSource.objects.exclude(
            id__in=TruthDeltaScore.objects.values_list('document_id')
        ).filter(status='analyzed')[:10]  # Batch of 10
        
        queued_count = 0
        for doc in unverified:
            verify_document_truth_delta.delay(doc.id)
            queued_count += 1
        
        logger.info(f"[Truth Delta] Queued {queued_count} documents for batch verification")
        return {'status': 'success', 'queued': queued_count}
    
    except Exception as exc:
        logger.error(f"Batch verification error: {str(exc)}")
        return {'status': 'error', 'error': str(exc)}


@shared_task
def update_external_data():
    """
    Maintenance task: Refresh external data for all documents.
    Useful when Crunchbase/LinkedIn data updates.
    Run on a schedule (e.g., weekly).
    """
    try:
        from .truth_delta_models import TruthDeltaScore
        
        # Get all verified documents
        verified_docs = TruthDeltaScore.objects.all().values_list('document_id')
        
        updated_count = 0
        for doc_id in verified_docs:
            # Refetch external data
            verify_document_truth_delta.delay(doc_id)
            updated_count += 1
        
        logger.info(f"[Truth Delta] Queued {updated_count} documents for data refresh")
        return {'status': 'success', 'refreshed': updated_count}
    
    except Exception as exc:
        logger.error(f"Data refresh error: {str(exc)}")
        return {'status': 'error', 'error': str(exc)}


@shared_task
def flag_critical_discrepancies():
    """
    Alert task: Find and flag documents with critical discrepancies.
    Could send notifications to analysts.
    """
    try:
        from .truth_delta_models import TruthDeltaScore
        
        # Find critical risk documents
        critical = TruthDeltaScore.objects.filter(credibility_risk='critical')
        
        if critical.exists():
            logger.warning(f"[Truth Delta] Found {critical.count()} documents with CRITICAL risk")
            
            # TODO: Send alerts
            # - Email to diligence team
            # - Slack notification
            # - Flag in admin dashboard
        
        return {'status': 'success', 'critical_count': critical.count()}
    
    except Exception as exc:
        logger.error(f"Critical flagging error: {str(exc)}")
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