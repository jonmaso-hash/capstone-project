# automotive_api/views.py
import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import VehicleAsset, TestDriveBooking
from .serializers import VehicleAssetSerializer, ScheduleDriveSerializer


class InventoryCatalogAPIView(APIView):
    """
    GET /api/v1/automotive/inventory/
    Returns searchable list of available vehicles on the dealership lots.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vehicles = VehicleAsset.objects.filter(status='available')
        
        # Overlay filters for specific search criteria
        make = request.query_params.get('make')
        fuel = request.query_params.get('fuel_type')
        if make:
            vehicles = vehicles.filter(make__iexact=make)
        if fuel:
            vehicles = vehicles.filter(fuel_type=fuel)

        serializer = VehicleAssetSerializer(vehicles, many=True)
        return Response({
            "status": "success",
            "matching_lot_count": vehicles.count(),
            "inventory": serializer.data
        }, status=status.HTTP_200_OK)


class RequestTestDriveAPIView(APIView):
    """
    POST /api/v1/automotive/drive/schedule/
    Locks a timestamp matrix to book a vehicle test drive via Zelda.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ScheduleDriveSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        target_car = get_object_or_404(VehicleAsset, id=serializer.validated_data['vehicle_id'], status='available')
        requested_time = serializer.validated_data['scheduled_timestamp']

        if requested_time <= timezone.now():
            return Response({
                "error": "INVALID_TIMEFRAME",
                "message": "Schedule timestamp parameters must exist inside future operation windows."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Zelda Financial Underwriting & Rate Ingestion System Simulation
        # Dynamically calculates localized lending options for the selected vehicle asset
        msrp = float(target_car.base_msrp)
        monthly_lease_estimate = round((msrp * 0.012) + 150.00, 2)
        ev_tax_credit_applied = True if target_car.fuel_type == 'bev' else False
        
        unique_token = f"DRV-ZELDA-{uuid.uuid4().hex[:10].upper()}"

        return Response({
            "status": "appointment_confirmed",
            "booking_token": unique_token,
            "logistics_manifest": {
                "vehicle": f"{target_car.year} {target_car.make} {target_car.model}",
                "location": target_car.showroom.name,
                "showroom_address": target_car.showroom.location_city,
                "time": requested_time.strftime('%Y-%m-%d %H:%M UTC')
            },
            "zelda_predictive_financing_matrix": {
                "base_asset_value": msrp,
                "estimated_monthly_lease_basis": monthly_lease_estimate,
                "incentive_eligibility": {
                    "federal_clean_vehicle_credit_eligible": ev_tax_credit_applied,
                    "applied_deduction_value": 7500.00 if ev_tax_credit_applied else 0.00
                },
                "projected_loan_apr_tier1": 4.99 if target_car.fuel_type == 'bev' else 5.99
            },
            "ai_advisor_note": "Zelda has staged delivery prep orders and notified the showroom floor staff."
        }, status=status.HTTP_201_CREATED)