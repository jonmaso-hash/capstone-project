from django.db import models
from django.conf import settings
from .vector_models import DocumentSource
from .truth_delta_models import ExternalDataSource

class FactAssertion(models.Model):
    """
    Structured fact extracted from documents with full provenance and traceability.
    Acts as the single source of truth for the dilution/truth-delta engine.
    """
    document = models.ForeignKey(DocumentSource, on_delete=models.CASCADE, related_name='fact_assertions')
    
    # FACT STRUCTURE
    entity_name = models.CharField(max_length=255)
    attribute = models.CharField(max_length=100)
    value = models.CharField(max_length=255)
    value_numeric = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    time_period = models.CharField(max_length=50, blank=True)
    
    # PROVENANCE TRACKING
    source_type = models.CharField(max_length=50, default='pitch_deck')
    source_name = models.CharField(max_length=255, blank=True)
    page_number = models.IntegerField(null=True, blank=True)
    section_title = models.CharField(max_length=255, null=True, blank=True)
    text_excerpt = models.TextField()
    chunk_hash = models.CharField(max_length=128)
    
    # CONFIDENCE & METADATA
    confidence_score = models.FloatField(default=0.0)
    extraction_date = models.DateTimeField(auto_now_add=True)
    extracted_by = models.CharField(max_length=100, default='intelligence_pipeline_v3')
    
    # VERIFICATION STATUS
    verification_status = models.CharField(max_length=20, default='unverified')
    manual_review_required = models.BooleanField(default=False)
    manual_review_notes = models.TextField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['entity_name', 'attribute']),
            models.Index(fields=['verification_status']),
        ]

    def __str__(self):
        return f"{self.entity_name} | {self.attribute}: {self.value}"

class ContradictionAlert(models.Model):
    """Structured record of conflicts detected between FactAssertions and external sources."""
    fact_assertion = models.ForeignKey(FactAssertion, on_delete=models.CASCADE, related_name='alerts')
    
    # CONFLICTING EVIDENCE
    conflicting_assertion = models.ForeignKey(FactAssertion, on_delete=models.SET_NULL, null=True, blank=True)
    external_source = models.ForeignKey(ExternalDataSource, on_delete=models.SET_NULL, null=True, blank=True)
    
    # DELTA ANALYSIS
    claimed_value = models.CharField(max_length=255)
    observed_value = models.CharField(max_length=255)
    discrepancy_percent = models.FloatField(null=True, blank=True)
    discrepancy_direction = models.CharField(max_length=50, blank=True)
    
    # SEVERITY & ACTION
    alert_level = models.CharField(max_length=20, default='medium')
    requires_manual_review = models.BooleanField(default=True)
    analyst_assigned = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    # TIMELINE
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Alert: {self.alert_level} discrepancy on {self.fact_assertion.attribute}"