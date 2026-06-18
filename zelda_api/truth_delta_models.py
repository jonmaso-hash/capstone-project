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


class TruthDeltaAnalysis(models.Model):
    """
    Comparison between claimed and observed data.
    Calculates discrepancy and flags suspicious claims.
    """
    
    DISCREPANCY_LEVELS = [
        ('none', 'None (0-5%)'),
        ('low', 'Low (5-20%)'),
        ('medium', 'Medium (20-50%)'),
        ('high', 'High (50-100%)'),
        ('critical', 'Critical (>100%)'),
    ]
    
    FLAG_LEVELS = [
        ('green', 'Verified - Matches Data'),
        ('yellow', 'Caution - Minor Discrepancy'),
        ('orange', 'Warning - Significant Discrepancy'),
        ('red', 'Alert - Major Red Flag'),
    ]
    
    document = models.ForeignKey(DocumentSource, on_delete=models.CASCADE, related_name='truth_delta_analyses')
    
    # The comparison
    claimed = models.ForeignKey(ClaimedDatapoint, on_delete=models.CASCADE, related_name='truth_analyses')
    observed = models.ForeignKey(ObservedDatapoint, on_delete=models.SET_NULL, null=True, related_name='truth_analyses')
    
    # Discrepancy calculation
    discrepancy_percent = models.FloatField(help_text="Absolute % difference between claimed and observed")
    discrepancy_level = models.CharField(max_length=20, choices=DISCREPANCY_LEVELS)
    
    # Direction of discrepancy
    is_inflated = models.BooleanField(help_text="Is claimed value higher than observed?")
    is_deflated = models.BooleanField(help_text="Is claimed value lower than observed?")
    
    # Flagging
    flag_level = models.CharField(max_length=20, choices=FLAG_LEVELS, default='yellow')
    explanation = models.TextField(help_text="Why this is flagged")
    
    # Weighting
    importance_weight = models.FloatField(
        default=1.0,
        help_text="How important is this metric? Revenue=1.0, Team=0.6, etc"
    )
    
    # Manual review
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_analyses'
    )
    verified_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'zelda_api'
        ordering = ['-flag_level', '-discrepancy_percent']
    
    def __str__(self):
        return f"{self.claimed.category}: {self.discrepancy_percent:.1f}% discrepancy"


class TruthDeltaScore(models.Model):
    """
    Overall Truth Delta Score for a document.
    Combines all individual analyses into one credibility metric.
    """
    
    document = models.OneToOneField(DocumentSource, on_delete=models.CASCADE, related_name='truth_delta_score')
    
    # Aggregate metrics
    overall_truth_score = models.FloatField(help_text="0-100: Overall credibility score")
    claims_analyzed = models.IntegerField(default=0, help_text="How many claims were analyzed")
    claims_verified = models.IntegerField(default=0, help_text="How many claims matched external data")
    claims_flagged = models.IntegerField(default=0, help_text="How many claims have discrepancies")
    
    # Breakdown by severity
    green_count = models.IntegerField(default=0)  # No discrepancy
    yellow_count = models.IntegerField(default=0)  # Minor (<20%)
    orange_count = models.IntegerField(default=0)  # Medium (20-50%)
    red_count = models.IntegerField(default=0)    # Critical (>50%)
    
    # Risk calculation
    credibility_risk = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low Risk'),
            ('medium', 'Medium Risk'),
            ('high', 'High Risk'),
            ('critical', 'Critical Risk'),
        ]
    )
    
    # Investment recommendation impact
    recommendation_adjustment = models.CharField(
        max_length=50,
        blank=True,
        help_text="E.g., 'downgrade_from_consider_to_pass'"
    )
    
    # Report
    summary = models.TextField(help_text="Human-readable summary of findings")
    key_findings = models.TextField(help_text="Bullet points of main discrepancies")
    
    # Metadata
    analyzed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'zelda_api'
    
    def __str__(self):
        return f"Truth Delta Score: {self.overall_truth_score:.1f}% - {self.document.filename}"
    
    @property
    def verification_rate(self):
        """Percentage of claims that were verified"""
        if self.claims_analyzed == 0:
            return 0.0
        return (self.claims_verified / self.claims_analyzed) * 100
    
    @property
    def discrepancy_rate(self):
        """Percentage of claims with discrepancies"""
        if self.claims_analyzed == 0:
            return 0.0
        return (self.claims_flagged / self.claims_analyzed) * 100


class VerificationAuditLog(models.Model):
    """
    Audit trail of all verification activities.
    For compliance and transparency.
    """
    
    document = models.ForeignKey(DocumentSource, on_delete=models.CASCADE, related_name='audit_logs')
    
    ACTION_TYPES = [
        ('claimed_created', 'Claim Created'),
        ('observed_created', 'Observed Data Added'),
        ('analysis_created', 'Analysis Performed'),
        ('flag_updated', 'Flag Level Changed'),
        ('verified', 'Manually Verified'),
        ('score_calculated', 'Score Calculated'),
    ]
    
    action = models.CharField(max_length=50, choices=ACTION_TYPES)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    details = models.TextField()
    change_summary = models.CharField(max_length=255, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'zelda_api'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.action} on {self.document.filename} at {self.created_at}"