# zelda_api/truth_delta_models.py
"""
Truth Delta Verification Engine Models
Compares claimed data vs observed data to detect discrepancies.
This is the highest-value diligence feature.
"""
from django.db import models
from django.conf import settings
from .vector_models import DocumentSource


class ExternalDataSource(models.Model):
    """
    Represents an external data source (Crunchbase, LinkedIn, SEC, etc)
    Used for cross-referencing claims against verified external data.
    """
    
    SOURCE_TYPES = [
        ('crunchbase', 'Crunchbase'),
        ('linkedin', 'LinkedIn'),
        ('sec', 'SEC EDGAR'),
        ('web', 'Web Scraping'),
        ('news', 'News Articles'),
        ('domain', 'Domain WHOIS'),
        ('jobs', 'Job Boards'),
        ('news_api', 'News API'),
        ('corporate', 'Corporate Filings'),
        ('other', 'Other Source'),
    ]
    
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    source_name = models.CharField(max_length=255)
    url = models.URLField(blank=True)
    api_key = models.CharField(max_length=255, blank=True, help_text="API key if needed")
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    
    class Meta:
        app_label = 'zelda_api'
        verbose_name = "External Data Source"
        verbose_name_plural = "External Data Sources"
    
    def __str__(self):
        return f"{self.source_name} ({self.source_type})"


class ClaimedDatapoint(models.Model):
    """
    A single claim extracted from a founder's pitch deck.
    E.g., "500 customers", "$1M ARR", "200% YoY growth"
    """
    
    CATEGORY_CHOICES = [
        ('revenue', 'Revenue'),
        ('arr', 'Annual Recurring Revenue (ARR)'),
        ('customers', 'Customer Count'),
        ('growth_rate', 'Growth Rate (%)'),
        ('employees', 'Employee Count'),
        ('funding_raised', 'Funding Raised'),
        ('market_share', 'Market Share'),
        ('user_count', 'User Count'),
        ('engagement', 'Engagement Metric'),
        ('churn', 'Churn Rate'),
        ('team_size', 'Team Size'),
        ('office_locations', 'Office Locations'),
        ('countries', 'Countries Served'),
        ('other', 'Other Metric'),
    ]
    
    document = models.ForeignKey(DocumentSource, on_delete=models.CASCADE, related_name='claimed_datapoints')

    # The claim itself
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    claimed_value = models.CharField(max_length=255, help_text="E.g., '500', '$1M', '200%'")
    claimed_value_numeric = models.FloatField(null=True, blank=True, help_text="Numeric value for comparison")
    unit = models.CharField(max_length=50, blank=True, help_text="E.g., 'customers', '$', '%'")
    time_period = models.CharField(max_length=100, blank=True, help_text="E.g., 'YoY', 'Q3 2024'")
    source_chunk = models.CharField(max_length=255, blank=True, help_text="Which slide/section in deck")

    # Provenance — full traceability back to the source chunk this claim came from
    page_number = models.IntegerField(null=True, blank=True, help_text="Page this claim's source chunk came from")
    text_excerpt = models.TextField(blank=True, help_text="Full source chunk text this claim was extracted from")
    chunk_hash = models.CharField(max_length=128, blank=True, help_text="Hash of the source chunk, for change detection/dedup")

    # Extraction metadata
    confidence_in_extraction = models.FloatField(default=0.7, help_text="How confident are we we extracted this correctly")
    extraction_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'zelda_api'
        ordering = ['category', '-created_at']
    
    def __str__(self):
        return f"{self.category}: {self.claimed_value}"


class ObservedDatapoint(models.Model):
    """
    Verified data from external sources.
    This is the "ground truth" we compare against claims.
    """
    
    document = models.ForeignKey(DocumentSource, on_delete=models.CASCADE, related_name='observed_datapoints')
    
    # The observed value
    category = models.CharField(max_length=50, choices=ClaimedDatapoint.CATEGORY_CHOICES)
    observed_value = models.CharField(max_length=255)
    observed_value_numeric = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    time_period = models.CharField(max_length=100, blank=True)
    
    # Source information
    source = models.ForeignKey(ExternalDataSource, on_delete=models.SET_NULL, null=True)
    source_url = models.URLField(blank=True)
    source_date = models.DateField(null=True, blank=True, help_text="When this data was published")
    
    # Credibility
    source_credibility = models.FloatField(default=0.8, help_text="0.0-1.0 how much we trust this source")
    extraction_method = models.CharField(
        max_length=50,
        choices=[
            ('api', 'API Call'),
            ('web_scrape', 'Web Scraping'),
            ('manual', 'Manual Entry'),
            ('filing', 'Corporate Filing'),
        ],
        default='api'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        app_label = 'zelda_api'
        ordering = ['-source_date', '-created_at']
    
    def __str__(self):
        return f"{self.category}: {self.observed_value}"


class TruthDeltaReport(models.Model):
    document = models.ForeignKey('DocumentSource', on_delete=models.CASCADE)
    overall_truth_score = models.FloatField(default=0.0)
    credibility_risk = models.CharField(max_length=20, default='unknown')
    summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'zelda_api'