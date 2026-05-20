from rest_framework import serializers
from .models import LedgerAccount

class AccountSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerAccount
        fields = ['account_number', 'account_type', 'balance', 'currency', 'created_at']

class FundTransferSerializer(serializers.Serializer):
    source_account = serializers.CharField(max_length=32, required=True)
    destination_account = serializers.CharField(max_length=32, required=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    memo = serializers.CharField(max_length=255, required=False, default="Zelda Automated Ledger Transfer")

    def validate(self, data):
        if data['source_account'] == data['destination_account']:
            raise serializers.ValidationError("Source and destination accounts cannot be identical.")
        return data