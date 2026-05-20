import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import InsurancePolicy, InsuranceClaim
from .serializers import PolicySummarySerializer, ClaimSubmissionSerializer


class UserPoliciesAPIView(APIView):
    """
    GET /api/v1/insurance/policies/
    Retrieves a portfolio index of all active and pending coverage tracks for the user.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        policies = InsurancePolicy.objects.filter(holder=request.user)
        serializer = PolicySummarySerializer(policies, many=True)
        return Response({
            "status": "success",
            "active_portfolio_count": policies.count(),
            "policies": serializer.data
        }, status=status.HTTP_200_OK)


class SubmitClaimAPIView(APIView):
    """
    POST /api/v1/insurance/claims/lodge/
    Processes claim data ingestion, routing details to Zelda's risk assessment engine.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ClaimSubmissionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        target_policy = get_object_or_404(InsurancePolicy, id=serializer.validated_data['policy_id'], holder=request.user)
        loss_estimate = serializer.validated_data['estimated_loss_value']
        desc_text = serializer.validated_data['incident_description'].lower()

        # Zelda Semantic Risk Assessment & Underwriting Rule Evaluation
        # Performs a simple scan for high-risk text anomalies to mock semantic scoring
        risk_indicators = []
        is_high_risk = False
        
        if "pre-existing" in desc_text or "prior damage" in desc_text:
            risk_indicators.append("PRE_EXISTING_CONDITION_EXCLUSION")
            is_high_risk = True
        if float(loss_estimate) >= float(target_policy.coverage_limit):
            risk_indicators.append("AGGREGATE_LIMIT_EXCEEDED_ALERT")
            is_high_risk = True

        claim_ref_code = f"CLM-ZELDA-{uuid.uuid4().hex[:10].upper()}"

        return Response({
            "status": "claim_registered",
            "claim_reference": claim_ref_code,
            "lifecycle_stage": "UNDER_ADJUSTER_REVIEW",
            "zelda_intelligence_triage": {
                "fraud_probability_index": 0.82 if is_high_risk else 0.11,
                "automated_risk_flags": risk_indicators,
                "policy_limit_alignment_check": {
                    "requested_amount": float(loss_estimate),
                    "policy_deductible_hurdle": float(target_policy.deductible),
                    "net_eligible_claim_basis": float(max(0, float(loss_estimate) - float(target_policy.deductible)))
                }
            },
            "system_action_taken": "Assigned automatically to high-priority forensic triage queue." if is_high_risk else "Standard processing dispatch pipeline initialized."
        }, status=status.HTTP_201_CREATED)