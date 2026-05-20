from rest_framework import serializers

class LeadICPScoreSerializer(serializers.Serializer):
    company_url = serializers.URLField(required=True)
    icp_definition_text = serializers.CharField(required=True, max_length=1000)

class CompetitorAuditSerializer(serializers.Serializer):
    competitor_urls = serializers.ListField(child=serializers.URLField(), min_length=1)