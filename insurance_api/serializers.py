# insurance_api/serializers.py
from rest_framework import serializers
from .models import InsurancePolicy, InsuranceClaim

class PolicySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = InsurancePolicy
        fields = ['id', 'policy_number', 'policy_type', 'coverage_limit', 'deductible', 'premium_annual', 'status', 'issued_at']


class ClaimSubmissionSerializer(serializers.Serializer):
    policy_id = serializers.IntegerField(required=True)
    incident_description = serializers.CharField(required=True, min_length=20, max_length=5000)
    estimated_loss_value = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=1.00)
    supporting_document_urls = serializers.ListField(child=serializers.URLField(), required=False, default=list)