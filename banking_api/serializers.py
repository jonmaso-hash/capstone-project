# banking_api/serializers.py
from rest_framework import serializers
from .models import Transaction

class TransactionSerializer(serializers.ModelSerializer):
    # 1. Enforcement: Mandatory fields for compliance
    idempotency_key = serializers.UUIDField(required=True)
    
    # 2. Exposure: Expose the standardized Foundry Envelope
    foundry_envelope = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            'id', 'account_id', 'amount', 'currency', 
            'idempotency_key', 'foundry_envelope'
        ]

    def validate(self, data):
        """
        Proactive Enforcement: Check for duplicate transactions 
        before any processing begins.
        """
        if Transaction.objects.filter(idempotency_key=data.get('idempotency_key')).exists():
            raise serializers.ValidationError({
                "idempotency_key": "This transaction has already been processed."
            })
        return data

    def get_foundry_envelope(self, obj):
        """
        Interface: Delegates normalization to the Protocol.
        This keeps the serializer clean and decoupled.
        """
        return obj.to_foundry_envelope()