# marketplace_api/serializers.py
from rest_framework import serializers
from .models import DigitalProduct

class DigitalProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = DigitalProduct
        fields = ['id', 'seller', 'title', 'category', 'price', 'download_url', 'compiled_spec_manifest', 'created_at']


class CheckoutPayloadSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(required=True)
    payment_method_nonce = serializers.CharField(required=True, max_length=100)
    coupon_code = serializers.CharField(max_length=30, required=False, allow_blank=True)