# automotive_api/serializers.py
from rest_framework import serializers
from .models import VehicleAsset, TestDriveBooking

class VehicleAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleAsset
        fields = ['id', 'showroom', 'vin', 'make', 'model', 'year', 'fuel_type', 'base_msrp', 'status', 'extracted_spec_matrix']


class ScheduleDriveSerializer(serializers.Serializer):
    vehicle_id = serializers.IntegerField(required=True)
    scheduled_timestamp = serializers.DateTimeField(required=True)
    preferred_sales_advisor = serializers.CharField(max_length=100, required=False, allow_blank=True)