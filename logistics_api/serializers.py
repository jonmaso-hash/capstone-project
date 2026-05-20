# logistics_api/serializers.py
from rest_framework import serializers
from .models import InventoryItem, FreightShipment

class InventoryItemSerializer(serializers.ModelSerializer):
    warehouse_code = serializers.CharField(source='warehouse.facility_code', read_only=True)

    class Meta:
        model = InventoryItem
        fields = ['id', 'warehouse', 'warehouse_code', 'sku', 'name', 'quantity_on_hand', 'reorder_threshold', 'unit_cost']


class StageShipmentPayloadSerializer(serializers.Serializer):
    destination_node_id = serializers.IntegerField(required=True)
    shipment_type = serializers.ChoiceField(choices=['inbound', 'outbound'], default='outbound')
    carrier = serializers.CharField(max_length=30, required=True)
    origin_address = serializers.CharField(max_length=255, required=True)
    sku_manifest_list = serializers.ListField(child=serializers.DictField(), required=True)