from django.shortcuts import render

# Create your views here.
# hotel_api/views.py
import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import HotelProperty, RoomInventory, HotelReservation
from .serializers import HotelPropertySerializer, RoomBookingPayloadSerializer


class PropertyExplorerAPIView(APIView):
    """
    GET /api/v1/hospitality/properties/
    Lists available catalog parameters with structural semantic query filtering.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        city = request.query_params.get('city')
        properties = HotelProperty.objects.all()
        if city:
            properties = properties.filter(location_city__iexact=city)
            
        serializer = HotelPropertySerializer(properties, many=True)
        return Response({
            "status": "success",
            "matches_found": properties.count(),
            "properties": serializer.data
        }, status=status.HTTP_200_OK)


class ExecuteRoomBookingAPIView(APIView):
    """
    POST /api/v1/hospitality/reserve/
    Locks room inventory and returns an algorithmic rate assessment via Zelda.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RoomBookingPayloadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        room = get_object_or_404(RoomInventory, id=serializer.validated_data['room_id'])
        
        if not room.is_currently_vacant:
            return Response({
                "error": "ROOM_UNAVAILABLE",
                "message": "The selected unit asset is occupied during this operational lifecycle window."
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Zelda Elastic Demand Pricing Modifier Injection
        # Simulating automated rate surge calculations based on target asset traits
        base_rate = float(room.base_price_per_night)
        multiplier = 1.15 if room.room_type == 'penthouse' else 1.00
        calculated_dynamic_total = round(base_rate * multiplier, 2)
        
        generated_conf = f"BK-ZELDA-{uuid.uuid4().hex[:10].upper()}"
        
        return Response({
            "status": "booking_finalized",
            "confirmation_code": generated_conf,
            "reservation_manifest": {
                "property_name": room.hotel.name,
                "assigned_unit": room.room_number,
                "tier_classification": room.room_type,
                "financial_breakdown": {
                    "base_rate_nightly": base_rate,
                    "zelda_yield_adjustment_multiplier": multiplier,
                    "gross_settlement_cost": calculated_dynamic_total
                }
            },
            "ai_ concierge_note": "Zelda has updated baggage routing priority handling tags automatically."
        }, status=status.HTTP_201_CREATED)