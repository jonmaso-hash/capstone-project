from rest_framework import serializers
from .models import PowerGridAsset, GenerationLog

class RealTimeTelemetrySerializer(serializers.Serializer):
    asset_id = serializers.IntegerField(required=True)
    # Changed min_value from 0.0 to 0 to eliminate DRF fields float warning
    current_output_mw = serializers.FloatField(required=True, min_value=0)
    # Changed min_value and max_value to clean integers
    grid_frequency_hz = serializers.FloatField(default=60.0, min_value=55, max_value=65)
    
    # The Gatekeeper
    idempotency_key = serializers.UUIDField(required=True)

    def validate(self, data):
        """Reject duplicate packets before ingestion."""
        if GenerationLog.objects.filter(idempotency_key=data['idempotency_key']).exists():
            raise serializers.ValidationError({"idempotency_key": "Telemetry batch already ingested."})
        return data
    
class PowerGridAssetSerializer(serializers.Serializer):
    """
    Validates structural telemetry data schemas, grid asset registry attributes,
    and industrial power distribution nodes managed within the Energy API ecosystem.
    """
    asset_id = serializers.CharField(required=True, max_length=100, help_text="Unique hardware or virtual node ID.")
    asset_name = serializers.CharField(required=True, max_length=255)
    asset_type = serializers.ChoiceField(
        choices=[('substation', 'Substation'), ('transformer', 'Transformer'), ('battery_bank', 'Battery Storage')], 
        default='substation'
    )
    operational_status = serializers.CharField(required=False, max_length=50, default='nominal')
    current_load_mw = serializers.FloatField(required=False, default=0.0)