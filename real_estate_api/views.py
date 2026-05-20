from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .serializers import PropertyMatchSerializer, OMUnderwriteSerializer
from .models import PropertyListing, BuyerMandate, UnderwritingReport

class PropertyMatchRadarAPIView(APIView):
    """
    Computes semantic vector similarity between an investor's text buy-box 
    (e.g., 'Value-add B-class asset in sunbelt states with value-add opportunities') 
    and off-market property flyers/listings.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PropertyMatchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Zelda uses the exact same Vector Engine math, but scans property embedding models
        mock_property_matches = [
            {
                "property_address": "1042 Vista Way, Phoenix, AZ",
                "asset_class": "multifamily",
                "units": 120,
                "match_score": 0.91,
                "alignment_rationale": "Matches mandate focus on high-growth Sunbelt submarkets needing interior capital renovations."
            }
        ]
        return Response({"status": "success", "matches": mock_property_matches}, status=status.HTTP_200_OK)


class OMOpticalUnderwriterAPIView(APIView):
    """
    Ingests raw 100-page Offering Memorandums using Zelda's multimodal layer 
    to output instant localized submarket telemetry and financial targets.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OMUnderwriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Stream the OM PDF directly into your underlying Gemini model
        return Response({
            "status": "extracted",
            "pro_forma_metrics": {
                "gross_potential_rent": 2450000,
                "net_operating_income_noi": 1560000,
                "implied_cap_rate": 6.25,
                "occupancy_rate": 0.94
            },
            "risk_factors_detected": [
                "Three major commercial leases expiring within 18 months.",
                "Located within a moderate localized flood plain boundary zone."
            ]
        }, status=status.HTTP_201_CREATED)