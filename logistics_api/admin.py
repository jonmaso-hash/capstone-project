# logistics_api/admin.py
from django.contrib import admin
from .models import WarehouseNode, InventoryItem, FreightShipment

@admin.register(WarehouseNode)
class WarehouseNodeAdmin(admin.ModelAdmin):
    list_display = ('name', 'facility_code', 'location_city', 'total_cubic_capacity_meters', 'created_at')
    search_fields = ('name', 'facility_code', 'location_city')


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'warehouse', 'quantity_on_hand', 'reorder_threshold', 'unit_cost')
    list_filter = ('warehouse', 'quantity_on_hand')
    search_fields = ('sku', 'name', 'warehouse__facility_code')
    ordering = ('sku',)


@admin.register(FreightShipment)
class FreightShipmentAdmin(admin.ModelAdmin):
    list_display = ('tracking_number', 'shipment_type', 'carrier', 'destination_node', 'status', 'estimated_delivery')
    list_filter = ('shipment_type', 'status', 'carrier', 'estimated_delivery')
    search_fields = ('tracking_number', 'origin_facility', 'destination_node__name')
    ordering = ('-estimated_delivery',)