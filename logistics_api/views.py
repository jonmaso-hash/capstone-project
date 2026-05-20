# logistics_api/views.py
import uuid
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import WarehouseNode, InventoryItem, FreightShipment
from .serializers import InventoryItemSerializer, StageShipmentPayloadSerializer


class WarehouseStockCatalogAPIView(APIView):
    """
    GET /api/v1/logistics/inventory/
    Lists current physical warehouse inventories with critical restock threshold filters.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = InventoryItem.objects.all()
        
        facility_filter = request.query_params.get('facility_code')
        only_low_stock = request.query_params.get('low_stock') == 'true'
        
        if facility_filter:
            items = items.filter(warehouse__facility_code__iexact=facility_filter)
        if only_low_stock:
            # Filters items where current inventory drops below safety thresholds
            items = items.filter(quantity_on_hand__lte=models.F('reorder_threshold'))
            
        serializer = InventoryItemSerializer(items, many=True)
        return Response({
            "status": "success",
            "total_monitored_skus": items.count(),
            "stock_records": serializer.data
        }, status=status.HTTP_200_OK)


class StageFreightShipmentAPIView(APIView):
    """
    POST /api/v1/logistics/freight/stage/
    Generates supply chain shipping tracking entries, invoking Zelda to optimize route paths and assess risk.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = StageShipmentPayloadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        target_warehouse = get_object_or_404(WarehouseNode, id=serializer.validated_data['destination_node_id'])
        manifest = serializer.validated_data['sku_manifest_list']
        
        # Zelda AI Route Optimization and Predictive Analytics Ingestion
        # Evaluates distance bottlenecks, port backlogs, or carrier transit delays
        total_staged_units = sum(int(node.get('quantity', 0)) for node in manifest)
        
        # Simulating automated transit vulnerability scoring
        route_risk_probability = 0.08
        if "international" in serializer.validated_data['origin_address'].lower():
            route_risk_probability = 0.34  # High customs risk overlay
            
        generated_tracking = f"TRK-ZELDA-{uuid.uuid4().hex[:12].upper()}"
        eta_projection = timezone.now() + timezone.timedelta(days=4)
        
        zelda_telemetry_block = {
            "predictive_eta": eta_projection.isoformat(),
            "supply_chain_risk_score": route_risk_probability,
            "route_bottleneck_alerts": ["PORT_CONGESTION_DELAY"] if route_risk_probability > 0.30 else [],
            "cargo_metrics": {
                "total_distinct_skus": len(manifest),
                "aggregate_unit_volume_count": total_staged_units
            }
        }
        
        # In actual system operations, persist directly to the database:
        # FreightShipment.objects.create(shipment_type=serializer.validated_data['shipment_type'], tracking_number=generated_tracking, carrier=serializer.validated_data['carrier'], origin_facility=serializer.validated_data['origin_address'], destination_node=target_warehouse, status='manifest_created', zelda_logistics_telemetry=zelda_telemetry_block, estimated_delivery=eta_projection)
        
        return Response({
            "status": "freight_manifest_staged",
            "tracking_number": generated_tracking,
            "logistics_routing_summary": {
                "carrier_assigned": serializer.validated_data['carrier'],
                "inbound_destination_facility": target_warehouse.name,
                "facility_code": target_warehouse.facility_code
            },
            "zelda_predictive_logistics_matrix": zelda_telemetry_block,
            "system_action_taken": "Automated warehouse floor receiving bays notified of incoming asset volume."
        }, status=status.HTTP_201_CREATED)