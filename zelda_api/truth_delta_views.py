# zelda_api/truth_delta_views.py
"""
Truth Delta Verification API Endpoints
Returns credibility verification and Truth Delta score
"""
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication, TokenAuthentication

from .vector_models import DocumentSource
from .truth_delta_models import (
    TruthDeltaScore, TruthDeltaAnalysis, ClaimedDatapoint, ObservedDatapoint
)
from .truth_delta_engine import TruthDeltaOrchestrator
from .truth_delta_sources import DataSourceManager

logger = logging.getLogger(__name__)


class TruthDeltaScoreView(APIView):
    """
    GET /api/v1/zelda/documents/{id}/truth-delta/
    
    Returns the Truth Delta verification score for a document.
    Shows claimed vs observed data and overall credibility score.
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
            
            # Get or calculate score
            try:
                score = doc.truth_delta_score
            except TruthDeltaScore.DoesNotExist:
                return Response(
                    {
                        "status": "not_analyzed",
                        "message": "Truth Delta verification has not been run yet",
                        "document_id": doc.id,
                        "action_required": "Run verification first"
                    },
                    status=status.HTTP_202_ACCEPTED
                )
            
            # Build response
            response_data = {
                'document_id': doc.id,
                'document_name': doc.source_entity,
                'overall_truth_score': score.overall_truth_score,
                'credibility_risk': score.credibility_risk,
                'verification_rate': score.verification_rate,
                'discrepancy_rate': score.discrepancy_rate,
                
                'claims_analyzed': score.claims_analyzed,
                'claims_verified': score.claims_verified,
                'claims_flagged': score.claims_flagged,
                
                'flag_breakdown': {
                    'verified': score.green_count,      # No discrepancy
                    'caution': score.yellow_count,      # Minor
                    'warning': score.orange_count,      # Medium
                    'critical': score.red_count,        # Major
                },
                
                'summary': score.summary,
                'key_findings': score.key_findings,
                
                'recommendation_impact': {
                    'original': 'From IntelligenceMemo (if available)',
                    'adjusted': score.recommendation_adjustment or 'None'
                },
                
                'analyzed_at': score.analyzed_at.isoformat(),
                'updated_at': score.updated_at.isoformat(),
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        except DocumentSource.DoesNotExist:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class TruthDeltaAnalysisView(APIView):
    """
    GET /api/v1/zelda/documents/{id}/truth-delta/analyses/
    
    Returns detailed analysis of each claim vs observed data.
    Shows which claims are verified, flagged, and why.
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
            
            # Get all analyses
            analyses = TruthDeltaAnalysis.objects.filter(document=doc).order_by('-flag_level')
            
            if not analyses.exists():
                return Response(
                    {
                        "message": "No analysis data available",
                        "status": "not_analyzed"
                    },
                    status=status.HTTP_202_ACCEPTED
                )
            
            # Build detailed analysis
            analyses_data = []
            for analysis in analyses:
                analyses_data.append({
                    'analysis_id': analysis.id,
                    'category': analysis.claimed.category,
                    'claimed': {
                        'value': analysis.claimed.claimed_value,
                        'numeric': analysis.claimed.claimed_value_numeric,
                        'unit': analysis.claimed.unit,
                        'source': analysis.claimed.source_chunk,
                    },
                    'observed': {
                        'value': analysis.observed.observed_value if analysis.observed else None,
                        'numeric': analysis.observed.observed_value_numeric if analysis.observed else None,
                        'unit': analysis.observed.unit if analysis.observed else None,
                        'source': analysis.observed.source.source_name if analysis.observed else None,
                    },
                    'discrepancy': {
                        'percent': analysis.discrepancy_percent,
                        'level': analysis.discrepancy_level,
                        'direction': 'inflated' if analysis.is_inflated else 'deflated',
                    },
                    'flag': {
                        'level': analysis.flag_level,
                        'explanation': analysis.explanation,
                        'importance': analysis.importance_weight,
                    },
                    'verified': analysis.is_verified,
                    'verified_by': analysis.verified_by.username if analysis.verified_by else None,
                })
            
            return Response({
                'document_id': doc.id,
                'total_analyses': analyses.count(),
                'analyses': analyses_data,
            }, status=status.HTTP_200_OK)
        
        except DocumentSource.DoesNotExist:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class TruthDeltaVerifyView(APIView):
    """
    POST /api/v1/zelda/documents/{id}/truth-delta/verify/
    
    Trigger Truth Delta verification for a document.
    Fetches external data and calculates credibility score.
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
            
            logger.info(f"Starting Truth Delta verification for document {document_id}")
            
            # Queue async verification task
            from .truth_delta_tasks import verify_document_truth_delta
            task = verify_document_truth_delta.delay(document_id)
            
            return Response({
                'status': 'verification_queued',
                'document_id': document_id,
                'task_id': task.id,
                'message': 'Truth Delta verification has been queued for processing',
                'polling_url': f'/api/v1/zelda/documents/{document_id}/truth-delta/'
            }, status=status.HTTP_202_ACCEPTED)
        
        except DocumentSource.DoesNotExist:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class FlaggedClaimsView(APIView):
    """
    GET /api/v1/zelda/documents/{id}/truth-delta/flags/
    
    Returns only the flagged claims (yellow, orange, red).
    Useful for quick diligence review.
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
            
            # Get flagged analyses only
            flagged = TruthDeltaAnalysis.objects.filter(
                document=doc
            ).exclude(flag_level='green').order_by('-flag_level', '-discrepancy_percent')
            
            if not flagged.exists():
                return Response({
                    'status': 'all_verified',
                    'message': 'No claims flagged - all verified',
                    'flagged_count': 0,
                }, status=status.HTTP_200_OK)
            
            flagged_data = []
            for analysis in flagged:
                flagged_data.append({
                    'flag_icon': self._get_flag_icon(analysis.flag_level),
                    'category': analysis.claimed.category.upper(),
                    'claimed': analysis.claimed.claimed_value,
                    'observed': analysis.observed.observed_value if analysis.observed else 'Unknown',
                    'discrepancy': f"{analysis.discrepancy_percent:.1f}%",
                    'flag': analysis.flag_level,
                    'severity': self._get_severity_name(analysis.flag_level),
                    'explanation': analysis.explanation,
                })
            
            return Response({
                'document_id': doc.id,
                'flagged_count': flagged.count(),
                'by_level': {
                    'yellow': flagged.filter(flag_level='yellow').count(),
                    'orange': flagged.filter(flag_level='orange').count(),
                    'red': flagged.filter(flag_level='red').count(),
                },
                'flags': flagged_data,
            }, status=status.HTTP_200_OK)
        
        except DocumentSource.DoesNotExist:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @staticmethod
    def _get_flag_icon(flag_level: str) -> str:
        icons = {
            'green': '✅',
            'yellow': '⚠️',
            'orange': '🟠',
            'red': '🚨',
        }
        return icons.get(flag_level, '❓')
    
    @staticmethod
    def _get_severity_name(flag_level: str) -> str:
        names = {
            'green': 'Verified',
            'yellow': 'Caution',
            'orange': 'Warning',
            'red': 'Critical',
        }
        return names.get(flag_level, 'Unknown')


class CredibilityReportView(APIView):
    """
    GET /api/v1/zelda/documents/{id}/truth-delta/report/
    
    Returns a formatted credibility report for investor review.
    Executive summary with key findings.
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
            
            try:
                score = doc.truth_delta_score
            except TruthDeltaScore.DoesNotExist:
                return Response(
                    {"error": "Verification not completed"},
                    status=status.HTTP_202_ACCEPTED
                )
            
            # Get flagged claims
            flagged = TruthDeltaAnalysis.objects.filter(
                document=doc
            ).exclude(flag_level='green')
            
            # Build markdown report
            report = self._build_markdown_report(score, flagged)
            
            return Response({
                'document_id': doc.id,
                'report': report,
                'timestamp': score.analyzed_at.isoformat(),
            }, status=status.HTTP_200_OK)
        
        except DocumentSource.DoesNotExist:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @staticmethod
    def _build_markdown_report(score, flagged):
        """Generate markdown-formatted credibility report"""
        
        report = f"""
# Truth Delta Credibility Report

## Overall Assessment
- **Credibility Risk**: {score.credibility_risk.upper()}
- **Truth Score**: {score.overall_truth_score:.1f}/100
- **Claims Analyzed**: {score.claims_analyzed}
- **Claims Verified**: {score.claims_verified}
- **Claims Flagged**: {score.claims_flagged}

## Summary
{score.summary}

## Key Findings
{score.key_findings}

## Flag Breakdown
- ✅ Verified: {score.green_count}
- ⚠️  Caution (5-20%): {score.yellow_count}
- 🟠 Warning (20-50%): {score.orange_count}
- 🚨 Critical (>50%): {score.red_count}

## Recommendation Impact
{score.recommendation_adjustment or "No adjustment to investment recommendation"}

---
*Generated: {score.analyzed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}*
"""
        return report