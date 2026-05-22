from rest_framework import serializers

class VectorMatchSerializer(serializers.Serializer):
    q = serializers.CharField(required=True, max_length=255)
    founders = serializers.BooleanField(default=True)
    investors = serializers.BooleanField(default=True)
    bulletins = serializers.BooleanField(default=True)

class DocumentAnalysisSerializer(serializers.Serializer):
    document_url = serializers.URLField(required=False, allow_blank=True)
    file_type = serializers.ChoiceField(choices=['pdf', 'docx', 'txt'], default='pdf')
    extract_financials = serializers.BooleanField(default=True)

class WebCrawlSerializer(serializers.Serializer):
    target_url = serializers.URLField(required=True)
    generate_memo = serializers.BooleanField(default=False)

class DirectUploadDocumentSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)
    document_type = serializers.ChoiceField(choices=['pitch_deck', 'cap_table', 'financial_model'], default='pitch_deck')

class MarketAnalyticsSerializer(serializers.Serializer):
    timeframe_days = serializers.IntegerField(default=30, min_value=7, max_value=365)
    include_sector_breakdown = serializers.BooleanField(default=True)

class MemoGenerationSerializer(serializers.Serializer):
    founder_id = serializers.CharField()  # Change from IntegerField to CharField
    tone = serializers.CharField(default="professional")

    def validate_founder_id(self, value):
        # Strip "#F-" if present to get the internal integer ID
        clean_id = value.replace("#F-", "")
        if not clean_id.isdigit():
            raise serializers.ValidationError("Founder ID must be a valid numeric ID or formatted as #F-<number>")
        return int(clean_id)