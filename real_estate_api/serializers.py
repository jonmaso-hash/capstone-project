from rest_framework import serializers

class PropertyMatchSerializer(serializers.Serializer):
    buyer_mandate_id = serializers.IntegerField(required=True)
    asset_class = serializers.ChoiceField(choices=['multifamily', 'industrial', 'retail', 'office'], required=True)
    target_cap_rate_min = serializers.FloatField(default=5.0)

class OMUnderwriteSerializer(serializers.Serializer):
    om_pdf = serializers.FileField(required=True)
    extract_rent_roll = serializers.BooleanField(default=True)