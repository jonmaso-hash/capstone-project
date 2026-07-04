# zelda_api/serializers.py
from rest_framework import serializers
from .models import ArticlePost

# 1. MODEL-BASED SERIALIZERS (Pinnacle-compliant)
# These now automatically leverage the Foundry protocol via the model method.
class ArticlePostSerializer(serializers.ModelSerializer):
    foundry_envelope = serializers.SerializerMethodField()

    class Meta:
        model = ArticlePost
        fields = ['id', 'title', 'status', 'foundry_envelope']

    def get_foundry_envelope(self, obj):
        # The serializer doesn't need to know the schema; 
        # it just calls the protocol!
        return obj.to_foundry_envelope()

# 2. INPUT SERIALIZERS (The Interface)
# These remain for incoming requests, but we ensure they are 
# strictly validated before they hit the Zelda logic.
class MemoGenerationSerializer(serializers.Serializer):
    founder_id = serializers.CharField()
    tone = serializers.CharField(default="professional")

    def validate_founder_id(self, value):
        # Standardized validation logic
        clean_id = value.replace("#F-", "")
        if not clean_id.isdigit():
            raise serializers.ValidationError("Founder ID must be a valid numeric ID or formatted as #F-<number>")
        return int(clean_id)

# 3. GENERIC FOUNDRY ENVELOPE SERIALIZER
# Use this for read-only responses that need to return the standardized format
class FoundryEnvelopeSerializer(serializers.Serializer):
    origin = serializers.CharField()
    timestamp = serializers.DateTimeField()
    intelligence_score = serializers.FloatField()
    payload = serializers.DictField()
    risk_flags = serializers.DictField()
    
class DirectUploadDocumentSerializer(serializers.Serializer):
    """
    Handles live document file streams injected directly into the Zelda ingestion ecosystem.
    """
    file = serializers.FileField(required=True, help_text="The raw file payload (PDF, DOCX, TXT).")
    document_purpose = serializers.CharField(required=False, max_length=100, default="resume_screening")
    
    def validate_file(self, value):
        # Pinnacle safety layer: Ensure file size doesn't exceed 10MB
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 10MB.")
        return value
    
class MarketAnalyticsSerializer(serializers.Serializer):
    """
    Validates structural telemetry data, filtering options, and time-series 
    parameters used for target market indexing calculations within Zelda AI.
    """
    metric_scope = serializers.CharField(required=True, max_length=50, help_text="e.g., 'talent_supply', 'salary_index'")
    target_sectors = serializers.ListField(child=serializers.CharField(max_length=100), required=False, default=list)
    lookback_days = serializers.IntegerField(required=False, default=30, min_value=1, max_value=365)
    include_confidence_intervals = serializers.BooleanField(required=False, default=True)
    
class VectorMatchSerializer(serializers.Serializer):
    """
    Validates payload schemas used for deep semantic text array 
    and vector embeddings comparisons within the Zelda matching pipeline.
    """
    source_vector_text = serializers.CharField(required=True, min_length=10)
    target_skills_keywords = serializers.ListField(child=serializers.CharField(max_length=100), required=True)
    threshold_cutoff = serializers.FloatField(required=False, default=0.50, min_value=0.0, max_value=1.0)
    
# C:\Users\jonathan\Desktop\KCV\zelda_api\serializers.py

# ... keep your existing serializers, including DirectUploadDocumentSerializer, 
# MarketAnalyticsSerializer, and VectorMatchSerializer ...

# CREATE THIS SERIALIZER TO FIX THE IMPORT ERROR:
class DocumentAnalysisSerializer(serializers.Serializer):
    """
    Validates input payloads for parsing, keyword scanning, and 
    structural data extraction from candidate resumes or texts.
    """
    raw_text = serializers.CharField(required=True, min_length=20)
    extraction_depth = serializers.ChoiceField(choices=[('standard', 'Standard'), ('deep', 'Deep Scan')], default='standard')
    include_entities = serializers.BooleanField(required=False, default=True)
    
class WebCrawlSerializer(serializers.Serializer):
    """
    Validates configuration payloads and target URLs for the 
    Zelda real-time web scraping and external document ingestion pipeline.
    """
    target_url = serializers.URLField(required=True, help_text="The source URL to crawl and scrape text from.")
    max_depth = serializers.IntegerField(required=False, default=1, min_value=1, max_value=3)
    extract_contact_info = serializers.BooleanField(required=False, default=False)
    custom_selectors = serializers.ListField(child=serializers.CharField(max_length=50), required=False, default=list)