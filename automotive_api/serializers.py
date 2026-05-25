# automotive_api/serializers.py
from rest_framework import serializers
from .models import VehicleAsset, TestDriveBooking

class VehicleAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleAsset
        fields = [
            'id', 'showroom', 'vin', 'make', 'model', 
            'year', 'fuel_type', 'base_msrp', 'status', 
            'extracted_spec_matrix'
        ]


class ScheduleDriveSerializer(serializers.Serializer):
    vehicle_id = serializers.IntegerField(required=True)
    scheduled_timestamp = serializers.DateTimeField(required=True)
    preferred_sales_advisor = serializers.CharField(max_length=100, required=False, allow_blank=True)
    
    # Idempotency enforcement
    idempotency_key = serializers.UUIDField(required=True)

    def validate(self, data):
        """Proactive enforcement against duplicate bookings."""
        if TestDriveBooking.objects.filter(idempotency_key=data.get('idempotency_key')).exists():
            raise serializers.ValidationError({
                "idempotency_key": "This booking request has already been processed."
            })
        return data