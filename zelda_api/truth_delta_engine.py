# zelda_api/truth_delta_engine.py
"""
Truth Delta Verification Engine
Compares claimed data vs observed data to detect discrepancies.
Highest-value diligence feature: Answers "Is the founder telling the truth?"
"""
import logging
from typing import Dict, List, Tuple, Optional
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from .truth_delta_models import (
    ClaimedDatapoint, ObservedDatapoint, TruthDeltaAnalysis,
    TruthDeltaScore, VerificationAuditLog
)
from .vector_models import DocumentSource

logger = logging.getLogger(__name__)


class TruthDeltaCalculator:
    """
    Core engine for calculating Truth Delta between claimed and observed data.
    """
    
    # Importance weighting by category (higher = more important)
    CATEGORY_WEIGHTS = {
        'revenue': 1.0,
        'arr': 1.0,
        'customers': 0.9,
        'growth_rate': 0.8,
        'employees': 0.6,
        'funding_raised': 0.7,
        'market_share': 0.7,
        'user_count': 0.8,
        'engagement': 0.5,
        'churn': 0.6,
        'team_size': 0.5,
        'office_locations': 0.3,
        'countries': 0.3,
        'other': 0.4,
    }
    
    # Thresholds for discrepancy levels (in percentage)
    DISCREPANCY_THRESHOLDS = {
        'none': 5,        # 0-5%
        'low': 20,        # 5-20%
        'medium': 50,     # 20-50%
        'high': 100,      # 50-100%
        'critical': 1000  # >100%
    }
    
    @staticmethod
    def calculate_discrepancy(claimed_value: float, observed_value: float) -> Tuple[float, bool, bool]:
        """
        Calculate percentage discrepancy between claimed and observed values.
        
        Returns:
            (discrepancy_percent, is_inflated, is_deflated)
        """
        if claimed_value == 0 and observed_value == 0:
            return 0.0, False, False
        
        if observed_value == 0:
            # Claimed value when nothing observed = total inflation
            return 100.0, True, False
        
        if claimed_value == 0:
            # Claimed 0 but something observed = deflation
            return 100.0, False, True
        
        # Calculate absolute percentage difference
        difference = abs(claimed_value - observed_value)
        # Use observed as baseline (what actually happened)
        discrepancy_percent = (difference / observed_value) * 100
        
        is_inflated = claimed_value > observed_value
        is_deflated = claimed_value < observed_value
        
        return min(discrepancy_percent, 999.9), is_inflated, is_deflated
    
    @staticmethod
    def get_discrepancy_level(discrepancy_percent: float) -> str:
        """Categorize discrepancy into severity levels."""
        if discrepancy_percent <= 5:
            return 'none'
        elif discrepancy_percent <= 20:
            return 'low'
        elif discrepancy_percent <= 50:
            return 'medium'
        elif discrepancy_percent <= 100:
            return 'high'
        else:
            return 'critical'
    
    @staticmethod
    def get_flag_level(discrepancy_percent: float, is_inflated: bool, is_deflated: bool) -> str:
        """Determine flag level based on discrepancy."""
        if discrepancy_percent <= 5:
            return 'green'  # Verified
        elif discrepancy_percent <= 20:
            return 'yellow'  # Caution
        elif discrepancy_percent <= 50:
            return 'orange'  # Warning
        else:
            return 'red'  # Critical
    
    @staticmethod
    def generate_explanation(
        category: str,
        claimed_value: str,
        observed_value: str,
        discrepancy_percent: float,
        is_inflated: bool,
        flag_level: str
    ) -> str:
        """Generate human-readable explanation of discrepancy."""
        
        direction = "higher" if is_inflated else "lower"
        
        explanations = {
            'green': f"Claim verified: {category} is accurate within margin of error.",
            'yellow': f"Minor discrepancy: Claimed {claimed_value}, observed {observed_value} ({discrepancy_percent:.1f}% difference). May be timing or reporting difference.",
            'orange': f"Significant discrepancy: Claimed {claimed_value} but observed {observed_value} ({discrepancy_percent:.1f}% {direction}). Requires clarification.",
            'red': f"Major red flag: Claimed {claimed_value} vs observed {observed_value} ({discrepancy_percent:.1f}% {direction}). Potential misrepresentation or data error.",
        }
        
        return explanations.get(flag_level, "Discrepancy flagged for review.")
    
    @classmethod
    def analyze_pair(
        cls,
        claimed: ClaimedDatapoint,
        observed: Optional[ObservedDatapoint]
    ) -> Optional[TruthDeltaAnalysis]:
        """
        Compare a single claimed datapoint to observed data.
        
        Returns:
            TruthDeltaAnalysis if created, None if cannot compare
        """
        
        # Cannot analyze if no observed data
        if not observed:
            logger.info(f"No observed data for {claimed.category}, skipping analysis")
            return None
        
        # Cannot analyze if missing numeric values
        if claimed.claimed_value_numeric is None or observed.observed_value_numeric is None:
            logger.warning(f"Missing numeric values for {claimed.category}")
            return None
        
        # Calculate discrepancy
        disc_percent, is_inflated, is_deflated = cls.calculate_discrepancy(
            claimed.claimed_value_numeric,
            observed.observed_value_numeric
        )
        
        # Categorize and flag
        disc_level = cls.get_discrepancy_level(disc_percent)
        flag_level = cls.get_flag_level(disc_percent, is_inflated, is_deflated)
        
        # Generate explanation
        explanation = cls.generate_explanation(
            claimed.category,
            claimed.claimed_value,
            observed.observed_value,
            disc_percent,
            is_inflated,
            flag_level
        )
        
        # Create analysis record
        analysis = TruthDeltaAnalysis.objects.create(
            document=claimed.document,
            claimed=claimed,
            observed=observed,
            discrepancy_percent=disc_percent,
            discrepancy_level=disc_level,
            is_inflated=is_inflated,
            is_deflated=is_deflated,
            flag_level=flag_level,
            explanation=explanation,
            importance_weight=cls.CATEGORY_WEIGHTS.get(claimed.category, 0.5)
        )
        
        logger.info(f"Created analysis: {analysis}")
        return analysis
    
    @classmethod
    def calculate_overall_score(cls, document: DocumentSource) -> TruthDeltaScore:
        """
        Calculate the overall Truth Delta Score for a document.
        This is the final credibility metric.
        """
        
        # Get all claims
        claims = ClaimedDatapoint.objects.filter(document=document)
        
        if not claims.exists():
            logger.warning(f"No claims found for document {document.id}")
            return None
        
        # Get all analyses
        analyses = TruthDeltaAnalysis.objects.filter(document=document)
        
        # Count by flag level
        green_count = analyses.filter(flag_level='green').count()
        yellow_count = analyses.filter(flag_level='yellow').count()
        orange_count = analyses.filter(flag_level='orange').count()
        red_count = analyses.filter(flag_level='red').count()
        
        total_analyzed = analyses.count()
        claims_flagged = yellow_count + orange_count + red_count
        
        # Calculate weighted truth score
        truth_score = cls._calculate_weighted_score(
            green_count, yellow_count, orange_count, red_count, total_analyzed
        )
        
        # Determine overall credibility risk
        if red_count > 0:
            credibility_risk = 'critical'
        elif orange_count >= 2 or (orange_count + red_count > total_analyzed * 0.3):
            credibility_risk = 'high'
        elif yellow_count > total_analyzed * 0.5:
            credibility_risk = 'medium'
        else:
            credibility_risk = 'low'
        
        # Generate summary
        summary = cls._generate_summary(
            total_analyzed, green_count, yellow_count, orange_count, red_count,
            credibility_risk
        )
        
        # Get key findings
        key_findings = cls._extract_key_findings(analyses)
        
        # Create or update score record
        score, created = TruthDeltaScore.objects.update_or_create(
            document=document,
            defaults={
                'overall_truth_score': truth_score,
                'claims_analyzed': claims.count(),
                'claims_verified': green_count,
                'claims_flagged': claims_flagged,
                'green_count': green_count,
                'yellow_count': yellow_count,
                'orange_count': orange_count,
                'red_count': red_count,
                'credibility_risk': credibility_risk,
                'summary': summary,
                'key_findings': key_findings,
            }
        )
        
        logger.info(f"Calculated Truth Delta Score: {truth_score:.1f}% for document {document.id}")
        return score
    
    @staticmethod
    def _calculate_weighted_score(
        green: int, yellow: int, orange: int, red: int, total: int
    ) -> float:
        """
        Calculate weighted truth score (0-100).
        Green = 100pts, Yellow = 70pts, Orange = 40pts, Red = 0pts
        """
        if total == 0:
            return 0.0
        
        weighted_sum = (green * 100) + (yellow * 70) + (orange * 40) + (red * 0)
        max_possible = total * 100
        
        score = (weighted_sum / max_possible) * 100
        return min(score, 100.0)
    
    @staticmethod
    def _generate_summary(
        total: int, green: int, yellow: int, orange: int, red: int, risk: str
    ) -> str:
        """Generate human-readable summary."""
        
        if total == 0:
            return "No claims were verified."
        
        green_pct = (green / total) * 100
        
        summaries = {
            'critical': f"🚨 CRITICAL: {red} major discrepancies found. Only {green_pct:.0f}% of claims verified. Potential intentional misrepresentation.",
            'high': f"⚠️ HIGH RISK: {orange + red} significant discrepancies. {green_pct:.0f}% verified. Founder credibility in question.",
            'medium': f"⚠️ MEDIUM RISK: {yellow + orange} claims need clarification. {green_pct:.0f}% verified. Typical for early-stage.",
            'low': f"✅ LOW RISK: {green_pct:.0f}% of claims verified. Founder appears credible.",
        }
        
        return summaries.get(risk, "Risk assessment incomplete.")
    
    @staticmethod
    def _extract_key_findings(analyses: 'QuerySet') -> str:
        """Extract the most important discrepancies."""
        
        # Get red flags
        red_analyses = analyses.filter(flag_level='red').order_by('-importance_weight')
        
        findings = []
        
        for analysis in red_analyses[:5]:  # Top 5 red flags
            findings.append(
                f"🚩 {analysis.claimed.category.upper()}: "
                f"Claimed {analysis.claimed.claimed_value}, "
                f"observed {analysis.observed.observed_value} "
                f"({analysis.discrepancy_percent:.1f}% discrepancy)"
            )
        
        # Add orange flags if no reds
        if not findings:
            orange_analyses = analyses.filter(flag_level='orange').order_by('-importance_weight')
            for analysis in orange_analyses[:3]:
                findings.append(
                    f"⚠️ {analysis.claimed.category.upper()}: "
                    f"{analysis.discrepancy_percent:.1f}% discrepancy"
                )
        
        return "\n".join(findings) if findings else "No major discrepancies found."


class TruthDeltaOrchestrator:
    """
    Orchestrates the full Truth Delta verification workflow.
    """
    
    def __init__(self, document: DocumentSource):
        self.document = document
        self.calculator = TruthDeltaCalculator()
    
    def run_full_verification(self) -> Dict:
        """
        Run complete Truth Delta verification:
        1. Extract claims from document
        2. Fetch observed data from sources
        3. Compare and analyze
        4. Calculate overall score
        """
        
        logger.info(f"Starting Truth Delta verification for document {self.document.id}")
        
        # Step 1: Claims should already be extracted by intelligence pipeline
        claims = ClaimedDatapoint.objects.filter(document=self.document)
        
        if not claims.exists():
            logger.warning(f"No claims found for document {self.document.id}")
            return {'status': 'error', 'message': 'No claims to verify'}
        
        logger.info(f"Found {claims.count()} claims to verify")
        
        # Step 2: Try to find observed data
        verified_count = 0
        for claim in claims:
            observed = self._find_observed_data(claim)
            if observed:
                # Step 3: Analyze
                self.calculator.analyze_pair(claim, observed)
                verified_count += 1
        
        logger.info(f"Found observed data for {verified_count}/{claims.count()} claims")
        
        # Step 4: Calculate overall score
        score = self.calculator.calculate_overall_score(self.document)
        
        logger.info(f"Truth Delta verification complete. Score: {score.overall_truth_score:.1f}%")
        
        return {
            'status': 'success',
            'claims_analyzed': claims.count(),
            'claims_verified': verified_count,
            'truth_score': score.overall_truth_score if score else 0.0,
            'credibility_risk': score.credibility_risk if score else 'unknown',
        }
    
    def _find_observed_data(self, claim: ClaimedDatapoint) -> Optional[ObservedDatapoint]:
        """
        Try to find observed data for a claim.
        This is where data source integrations happen.
        """
        
        # For now: placeholder that would integrate with Crunchbase, LinkedIn, etc
        # In production, this would:
        # 1. Query Crunchbase API for revenue/customers
        # 2. Query LinkedIn for employee count
        # 3. Scrape news for funding announcements
        # 4. Check domain WHOIS for founding date
        # etc.
        
        logger.debug(f"Looking for observed data for {claim.category}")
        return None  # Placeholder


# Global instance
truth_calculator = TruthDeltaCalculator()
truth_orchestrator_factory = TruthDeltaOrchestrator