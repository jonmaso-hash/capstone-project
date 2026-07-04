# zelda_api/vector_models.py
"""
Zelda Vector Intelligence Layer
The central nervous system for document understanding, chunking, embedding,
retrieval, and contextual AI analysis with source attribution.
"""
from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from datetime import datetime
from .protocol import FoundryStandardMixin


class DocumentSource(FoundryStandardMixin, models.Model):
    """
    Represents an ingested document (PDF, PPTX, etc).
    Gateway to the entire intelligence pipeline.
    """
    source_name = "document_sources"
    
    SOURCE_TYPES = [
        ('pitch_deck', 'Pitch Deck'),
        ('financial_model', 'Financial Model'),
        ('business_plan', 'Business Plan'),
        ('whitepaper', 'Whitepaper'),
        ('research', 'Research Report'),
        ('portfolio', 'Investor Portfolio'),
        ('business_valuation', 'Business Valuation Request'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('ingested', 'Ingested'),
        ('chunking', 'Chunking'),
        ('chunked', 'Chunked'),
        ('embedding', 'Embedding'),
        ('embedded', 'Embedded'),
        ('analyzing', 'Analyzing'),
        ('analyzed', 'Analyzed'),
        ('error', 'Error'),
    ]
    

    
    # Metadata
    filename = models.CharField(max_length=255)
    document_type = models.CharField(max_length=20, choices=SOURCE_TYPES, default='pitch_deck')
    source_entity = models.CharField(max_length=255, help_text="Founder name, investor name, or source")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='zelda_documents')
    
    # Content summary
    raw_text_preview = models.TextField(blank=True, help_text="First 1000 chars for reference")
    raw_text_full = models.TextField(blank=True, default='')
    total_pages = models.IntegerField(default=0)
    total_word_count = models.IntegerField(default=0)
    
    # Pipeline status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ingested')
    
    # Intelligence scores
    confidence_score = models.FloatField(default=0.0, help_text="0.0-1.0 overall analysis confidence")
    intelligence_rank = models.IntegerField(default=0, help_text="Ranking by quality/relevance")
    
    # Error tracking
    error_message = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        app_label = 'zelda_api'
        ordering = ['-created_at']
        verbose_name = "Document Source"
        verbose_name_plural = "Document Sources"
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['source_entity']),
        ]
    
    def get_serialized_data(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "document_type": self.document_type,
            "source_entity": self.source_entity,
            "status": self.status,
            "confidence_score": self.confidence_score,
            "total_chunks": self.chunks.count(),
            "created_at": self.created_at.isoformat(),
        }
    
    def __str__(self):
        return f"{self.filename} ({self.source_entity})"


class DocumentChunk(FoundryStandardMixin, models.Model):
    """
    A semantic chunk extracted from a document.
    Chunks are typically 300-500 tokens, with overlaps for context.
    """
    source_name = "document_chunks"
    
    document = models.ForeignKey(DocumentSource, on_delete=models.CASCADE, related_name='chunks')
    
    # Position in document
    chunk_index = models.IntegerField(help_text="Order in the document (0-indexed)")
    page_number = models.IntegerField(default=0, help_text="Page this chunk came from")
    section_title = models.CharField(max_length=255, blank=True, help_text="e.g., 'Problem Statement', 'Market Size'")
    
    # Content
    raw_text = models.TextField(help_text="The actual text chunk")
    token_count = models.IntegerField(help_text="Approximate token count for this chunk")
    
    # Vector embedding (PostgreSQL pgvector or similar)
    # If using pgvector: use VectorField from django-pgvector
    # For now, we'll store as JSON array for compatibility
    embedding_vector = models.JSONField(null=True, blank=True, help_text="Vector embedding (list of floats)")
    embedding_model = models.CharField(max_length=100, default="claude-3-5-sonnet", blank=True)
    
    # Metadata
    is_key_insight = models.BooleanField(default=False, help_text="Marked as particularly important")
    relevance_score = models.FloatField(default=0.5, help_text="0.0-1.0 relevance for the document topic")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    embedded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        app_label = 'zelda_api'
        ordering = ['document', 'chunk_index']
        unique_together = [['document', 'chunk_index']]
        verbose_name = "Document Chunk"
        verbose_name_plural = "Document Chunks"
        indexes = [
            models.Index(fields=['document', 'chunk_index']),
            models.Index(fields=['is_key_insight']),
        ]
    
    def get_serialized_data(self):
        return {
            "id": self.id,
            "document_id": self.document.id,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "section": self.section_title,
            "token_count": self.token_count,
            "is_key_insight": self.is_key_insight,
            "relevance": self.relevance_score,
        }
    
    def __str__(self):
        return f"{self.document.filename} - Chunk {self.chunk_index}"


class IntelligenceInsight(FoundryStandardMixin, models.Model):
    """
    A single AI-derived insight with full source attribution.
    Links back to the specific chunks that informed it.
    """
    source_name = "intelligence_insights"
    
    INSIGHT_TYPES = [
        ('metric', 'Metric Extraction'),
        ('trend', 'Trend Analysis'),
        ('risk', 'Risk Assessment'),
        ('opportunity', 'Opportunity'),
        ('statement', 'Key Statement'),
        ('assumption', 'Assumption'),
        ('recommendation', 'Recommendation'),
        ('other', 'Other'),
    ]
    
    document = models.ForeignKey(DocumentSource, on_delete=models.CASCADE, related_name='insights')
    insight_type = models.CharField(max_length=20, choices=INSIGHT_TYPES, default='statement')
    
    # The insight itself
    category = models.CharField(max_length=100, help_text="e.g., 'TAM', 'Team Size', 'Risk'")
    insight_text = models.TextField(help_text="The actual insight extracted")
    
    # Source chunks (many-to-many with attribution)
    source_chunks = models.ManyToManyField(DocumentChunk, related_name='insights', help_text="Chunks this insight was derived from")
    
    # Confidence & validation
    confidence_score = models.FloatField(default=0.7, help_text="0.0-1.0 confidence in this insight")
    source_attribution = models.CharField(max_length=255, blank=True, help_text="e.g., 'Slide 5', 'Page 3, paragraph 2'")
    
    # Quantified metrics (if applicable)
    metric_value = models.CharField(max_length=100, blank=True, help_text="e.g., '$5M', '50 employees'")
    metric_unit = models.CharField(max_length=50, blank=True, help_text="e.g., 'USD', 'headcount'")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        app_label = 'zelda_api'
        ordering = ['-confidence_score', '-created_at']
        verbose_name = "Intelligence Insight"
        verbose_name_plural = "Intelligence Insights"
        indexes = [
            models.Index(fields=['document', 'insight_type']),
            models.Index(fields=['category']),
            models.Index(fields=['-confidence_score']),
        ]
    
    def get_serialized_data(self):
        return {
            "id": self.id,
            "document_id": self.document.id,
            "type": self.insight_type,
            "category": self.category,
            "insight": self.insight_text,
            "confidence": self.confidence_score,
            "metric": f"{self.metric_value} {self.metric_unit}".strip() if self.metric_value else None,
            "source_attribution": self.source_attribution,
        }
    
    def __str__(self):
        return f"{self.document.filename} - {self.category}: {self.insight_text[:50]}"


class IntelligenceMemo(FoundryStandardMixin, models.Model):
    """
    A compiled executive intelligence memo built from retrieved insights.
    This is what founders/investors see: highly contextual, source-cited, structured.
    """
    source_name = "intelligence_memos"
    
    document = models.OneToOneField(DocumentSource, on_delete=models.CASCADE, related_name='memo')
    
    # Memo content (markdown formatted)
    executive_summary = models.TextField(help_text="High-level overview with key metrics")
    problem_solution = models.TextField(blank=True, help_text="Problem statement and proposed solution")
    market_analysis = models.TextField(blank=True, help_text="TAM, SAM, SOM with sources")
    team_assessment = models.TextField(blank=True, help_text="Team experience, background, gaps")
    financial_analysis = models.TextField(blank=True, help_text="Revenue, burn, runway, unit economics")
    risk_assessment = models.TextField(blank=True, help_text="Key risks and mitigation strategies")
    investment_thesis = models.TextField(help_text="Why this is investable")
    investment_readiness = models.TextField(blank=True, help_text="0-100 readiness score with strengths/weaknesses")
    questions_for_management = models.TextField(blank=True, help_text="Open questions the deck does not answer")
    
    # Source tracking
    insights_used = models.ManyToManyField(IntelligenceInsight, related_name='memos')
    retrieved_context = models.TextField(help_text="Raw context assembled from retrieval")
    
    # Quality metrics
    completeness_score = models.FloatField(default=0.0, help_text="0.0-1.0 memo completeness")
    citations_count = models.IntegerField(default=0, help_text="Number of source citations")
    
    # Recommendations
    recommendation = models.CharField(
        max_length=20,
        choices=[
            ('strong_pass', 'Strong Pass'),
            ('pass', 'Pass'),
            ('consider', 'Consider'),
            ('interview', 'Schedule Interview'),
            ('strong_interest', 'Strong Interest'),
        ],
        default='consider'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'zelda_api'
        ordering = ['-created_at']
        verbose_name = "Intelligence Memo"
        verbose_name_plural = "Intelligence Memos"
    
    def get_serialized_data(self):
        return {
            "id": self.id,
            "document_id": self.document.id,
            "executive_summary": self.executive_summary[:500],
            "recommendation": self.recommendation,
            "completeness": self.completeness_score,
            "citations": self.citations_count,
            "created_at": self.created_at.isoformat(),
        }
    
    def __str__(self):
        return f"Memo: {self.document.filename}"


class BusinessValuationReport(FoundryStandardMixin, models.Model):
    """
    Business memo + risk report + valuation summary for a
    document_type='business_valuation' DocumentSource. A parallel output
    to IntelligenceMemo (which is fundraising-shaped and OneToOne to
    DocumentSource, so it can't also hold a valuation report) — generated
    by ZeldaIntelligencePipelineV2.process_valuation_document() instead of
    the standard memo path.
    """
    source_name = "business_valuation_reports"

    document = models.OneToOneField(DocumentSource, on_delete=models.CASCADE, related_name='valuation_report')

    business_overview = models.TextField(blank=True)
    financial_summary = models.TextField(blank=True)
    risk_report = models.TextField(blank=True)
    valuation_summary = models.TextField(blank=True)
    valuation_low = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    valuation_high = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    confidence_score = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'zelda_api'
        verbose_name = "Business Valuation Report"
        verbose_name_plural = "Business Valuation Reports"

    def get_serialized_data(self):
        return {
            "id": self.id,
            "document_id": self.document.id,
            "valuation_summary": self.valuation_summary[:500],
            "valuation_low": str(self.valuation_low) if self.valuation_low is not None else None,
            "valuation_high": str(self.valuation_high) if self.valuation_high is not None else None,
            "confidence_score": self.confidence_score,
            "created_at": self.created_at.isoformat(),
        }

    def __str__(self):
        return f"Valuation: {self.document.filename}"