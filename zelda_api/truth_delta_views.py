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
from .truth_delta_models import TruthDeltaReport

logger = logging.getLogger(__name__)


class TruthDeltaVerifyView(APIView):
    """
    POST /api/v1/zelda/documents/{id}/truth-delta/verify/

    Trigger Truth Delta verification for a document.
    Fetches external data and calculates credibility score.
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


class TruthDeltaScoreView(APIView):
    """
    GET /api/v1/zelda/documents/{id}/truth-delta/

    Returns the Truth Delta verification score for a document.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, TokenAuthentication]

    def get(self, request, document_id):
        try:
            report = TruthDeltaReport.objects.get(document_id=document_id)
            return Response({
                "overall_truth_score": report.overall_truth_score,
                "credibility_risk": report.credibility_risk,
                "summary": report.summary,
            })
        except TruthDeltaReport.DoesNotExist:
            return Response({"error": "Report not found"}, status=404)
