from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import PowerGridAsset, GenerationLog
from .serializers import PowerGridAssetSerializer, RealTimeTelemetrySerializer


class GridAssetRegistryAPIView(APIView):
    """
    GET /api/v1/energy/assets/
    Returns a complete structural landscape array of registered generation assets.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        assets = PowerGridAsset.objects.all()
        # Allow quick query filtering by regional power grid boundaries
        region = request.query_params.get('region')
        if region:
            assets = assets.filter(grid_region__iexact=region)
            
        serializer = PowerGridAssetSerializer(assets, many=True)
        return Response({
            "status": "success",
            "total_monitored_nodes": assets.count(),
            "assets": serializer.data
        }, status=status.HTTP_200_OK)


class GridTelemetryIngestAPIView(APIView):
    """
    POST /api/v1/energy/telemetry/submit/
    Accepts instantaneous generation telemetry updates from grid infrastructure sensors.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RealTimeTelemetrySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        target_asset = get_object_or_404(PowerGridAsset, id=serializer.validated_data['asset_id'])
        output = serializer.validated_data['current_output_mw']
        frequency = serializer.validated_data['grid_frequency_hz']
        
        # Calculate environmental offsetting metrics via baseline asset types
        efficiency_coefficient = 0.43 if target_asset.asset_type in ['solar_farm', 'wind_turbine'] else 0.00
        calculated_offset = round((output * efficiency_coefficient), 4)
        
        # In a real setup, you would execute an atomic database write:
        # GenerationLog.objects.create(asset=target_asset, current_output_mw=output, ...)
        
        return Response({
            "status": "telemetry_ingested",
            "node_identifier": target_asset.asset_name,
            "grid_interconnection": {
                "designated_balancing_authority": target_asset.grid_region,
                "instantaneous_load_utilization_ratio": round((output / target_asset.nameplate_capacity_mw) * 100, 2) if target_asset.nameplate_capacity_mw > 0 else 0
            },
            "sustainability_metrics": {
                "net_carbon_avoidance_metric_tons_hr": calculated_offset,
                "renewable_energy_credit_rec_eligible": True if calculated_offset > 0 else False
            },
            "grid_stability_audit": {
                "frequency_deviation_hz": round(abs(60.0 - frequency), 3),
                "status_assessment": "NOMINAL_STABILITY_LOCK" if 59.9 <= frequency <= 60.1 else "FREQUENCY_SPIKE_WARNING"
            }
        }, status=status.HTTP_201_CREATED)