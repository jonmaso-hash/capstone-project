from rest_framework import serializers
from .models import PowerGridAsset, GenerationLog

class PowerGridAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = PowerGridAsset
        fields = ['id', 'asset_name', 'asset_type', 'grid_region', 'nameplate_capacity_mw', 'status', 'last_reported_at']


class RealTimeTelemetrySerializer(serializers.Serializer):
    asset_id = serializers.IntegerField(required=True)
    current_output_mw = serializers.FloatField(required=True, min_value=0.0)
    grid_frequency_hz = serializers.FloatField(default=60.0, min_value=55.0, max_value=65.0)
    override_grid_curtailment = serializers.BooleanField(default=False)