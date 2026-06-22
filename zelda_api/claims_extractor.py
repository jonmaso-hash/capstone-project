import re
import logging
from .truth_delta_models import ClaimedDatapoint

logger = logging.getLogger(__name__)

class ClaimsExtractor:
    """
    Parses intelligence insights to identify verifiable data points (claims).
    Robustly adapts to whichever version of ClaimedDatapoint is active in Django.
    """
    def extract_claims_from_insights(self, document, insights=None):
        """
        Extracts claimed datapoints from insights for a document.
        If insights are not passed, fetches them from the database.
        """
        if insights is None:
            from .vector_models import IntelligenceInsight
            insights = IntelligenceInsight.objects.filter(document=document)

        extracted_count = 0
        
        # Check model field structure dynamically to prevent migration/schema crashes
        has_raw_text = hasattr(ClaimedDatapoint, 'raw_text')
        has_claimed_value = hasattr(ClaimedDatapoint, 'claimed_value')
        
        for insight in insights:
            # Bug #4 Fix: Use insight_text instead of content
            insight_text = getattr(insight, 'insight_text', '')
            if not insight_text:
                # Fallback to content if insight_text is empty or doesn't exist
                insight_text = getattr(insight, 'content', '')

            if not insight_text:
                continue

            # Identify if there is a claim to extract (e.g., contains financial/percentage info)
            if '$' in insight_text or '%' in insight_text:
                try:
                    # Extract numeric values
                    numeric_value = self._extract_numeric_value(insight_text)
                    
                    # Populate based on which schema is active
                    create_kwargs = {
                        'document': document,
                    }
                    
                    if has_raw_text:
                        create_kwargs['raw_text'] = insight_text
                        create_kwargs['claim_type'] = "Financial" if '$' in insight_text else "Performance"
                        if hasattr(ClaimedDatapoint, 'source_insight'):
                            create_kwargs['source_insight'] = insight
                    
                    if has_claimed_value:
                        # Map category dynamically
                        category = self._map_category(getattr(insight, 'category', 'other'))
                        create_kwargs['category'] = category
                        create_kwargs['claimed_value'] = insight_text[:255]
                        create_kwargs['claimed_value_numeric'] = numeric_value
                        create_kwargs['unit'] = getattr(insight, 'metric_unit', '') or ('$' if '$' in insight_text else '%')
                        create_kwargs['source_chunk'] = f"Insight: {getattr(insight, 'category', 'General')}"
                        create_kwargs['confidence_in_extraction'] = getattr(insight, 'confidence_score', 0.7)
                    
                    ClaimedDatapoint.objects.create(**create_kwargs)
                    extracted_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to create ClaimedDatapoint for insight {insight.id}: {str(e)}")
                    
        return extracted_count

    def _extract_numeric_value(self, text: str) -> float:
        """Helper to extract raw numeric value from text string."""
        if not text:
            return None
        patterns = [
            r'\$?([\d,\.]+)(?:\s*[KkMmBb])?',  # $1M, 1,000, 0.5, etc
            r'([\d,\.]+)\s*%',                 # 200%, 0.5%, etc
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    value_str = match.group(1).replace(',', '')
                    numeric_value = float(value_str)
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

    def _map_category(self, category_str: str) -> str:
        """Maps generic categories to ClaimedDatapoint choice values."""
        cat_lower = category_str.lower()
        if 'revenue' in cat_lower or 'arr' in cat_lower:
            return 'revenue'
        elif 'customer' in cat_lower:
            return 'customers'
        elif 'growth' in cat_lower:
            return 'growth_rate'
        elif 'employee' in cat_lower or 'team' in cat_lower:
            return 'employees'
        elif 'funding' in cat_lower:
            return 'funding_raised'
        elif 'user' in cat_lower:
            return 'user_count'
        return 'other'

# Expose singleton instance for Class import:
# "from .claims_extractor import claims_extractor"
claims_extractor = ClaimsExtractor()

# Expose legacy function import:
# "from .claims_extractor import extract_claims_from_insights"
def extract_claims_from_insights(document, insights):
    return claims_extractor.extract_claims_from_insights(document, insights)