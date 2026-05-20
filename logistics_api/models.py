# logistics_api/models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class WarehouseNode(models.Model):
    name = models.CharField(max_length=255)
    facility_code = models.CharField(max_length=50, unique=True, help_text="Unique facility identifier (e.g., WH-SD-01)")
    location_city = models.CharField(max_length=150)
    total_cubic_capacity_meters = models.FloatField(default=1000.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'logistics_api'
        verbose_name = "Warehouse Node"
        verbose_name_plural = "Warehouse Nodes"

    def __str__(self):
        return f"{self.name} ({self.facility_code})"


class InventoryItem(models.Model):
    warehouse = models.ForeignKey(WarehouseNode, on_delete=models.CASCADE, related_name='stocks')
    sku = models.CharField(max_length=100, unique=True, verbose_name="SKU Stock Keeping Unit")
    name = models.CharField(max_length=255)
    quantity_on_hand = models.IntegerField(default=0)
    reorder_threshold = models.IntegerField(default=10, help_text="Triggers safety stock warnings when inventory drops below this number.")
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        app_label = 'logistics_api'
        verbose_name = "Inventory Item"
        verbose_name_plural = "Inventory Items"

    def __str__(self):
        return f"{self.name} [SKU: {self.sku}] - Qty: {self.quantity_on_hand}"


class FreightShipment(models.Model):
    SHIPMENT_TYPES = [
        ('inbound', 'Inbound Supplier Restock'),
        ('outbound', 'Outbound Client Fulfillment'),
    ]
    CARRIER_CHOICES = [
        ('fedex', 'FedEx Freight'),
        ('ups', 'UPS Supply Chain'),
        ('dhl', 'DHL Global Forwarding'),
        ('freight_forwarder', 'Private Third-Party Logistics (3PL)'),
    ]
    STATUS_STAGES = [
        ('manifest_created', 'Manifest Staged'),
        ('transit', 'In Transit across Nodes'),
        ('delivered', 'Delivered & Count Ingested'),
        ('exception', 'Customs / Transit Delay Exception'),
    ]

    shipment_type = models.CharField(max_length=15, choices=SHIPMENT_TYPES, default='outbound')
    tracking_number = models.CharField(max_length=100, unique=True)
    carrier = models.CharField(max_length=30, choices=CARRIER_CHOICES, default='fedex')
    origin_facility = models.CharField(max_length=255)
    destination_node = models.ForeignKey(WarehouseNode, on_delete=models.CASCADE, related_name='incoming_freight')
    status = models.CharField(max_length=20, choices=STATUS_STAGES, default='manifest_created')
    
    # Zelda AI tracking metadata (e.g., dynamic ETAs, risk of customs hold)
    zelda_logistics_telemetry = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="Stores dynamic route optimization data and predictive arrival variance calculations."
    )
    
    shipped_at = models.DateTimeField(blank=True, null=True)
    estimated_delivery = models.DateTimeField(blank=True, null=True)

    class Meta:
        app_label = 'logistics_api'
        verbose_name = "Freight Shipment"
        verbose_name_plural = "Freight Shipments"
        ordering = ['-estimated_delivery']

    def __str__(self):
        return f"Shipment {self.tracking_number} [{self.status.upper()}]"