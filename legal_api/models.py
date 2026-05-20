# marketing_api/models.py
from django.db import models

class LeadICPScore(models.Model):
    """
    Stores sales lead URLs, the target ICP definition they were measured against, 
    and the resulting AI alignment metrics and outreach suggestions.
    """
    company_url = models.URLField(max_length=500)
    icp_definition_text = models.TextField(help_text="The core definition of the target client profile.")
    icp_alignment_score = models.FloatField(help_text="Calculated vector similarity score between 0.0 and 1.0.")
    qualification_signals = models.JSONField(default=dict, help_text="Structured dict containing firmographics, pain points, etc.")
    recommended_outreach_angle = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lead ICP Score"
        verbose_name_plural = "Lead ICP Scores"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.company_url} - Score: {self.icp_alignment_score}"


class CompetitorAudit(models.Model):
    """
    Tracks bulk crawl runs analyzing multiple competitor domains to identify 
    gaps in market messaging themes.
    """
    competitor_urls = models.JSONField(default=list, help_text="Array of target competitor domain strings.")
    market_positioning_landscape = models.JSONField(default=dict, help_text="Synthesized themes, identified gaps, and keywords.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Competitor Audit"
        verbose_name_plural = "Competitor Audits"
        ordering = ['-created_at']

    def __str__(self):
        return f"Audit Batch #{self.id} ({self.created_at.strftime('%Y-%m-%d')})"
    
# legal_api/models.py
from django.db import models

class LegalContract(models.Model):
    """Stores metadata extracted from multi-page document file binaries."""
    contract_type = models.CharField(max_length=255, default="Commercial Lease Agreement")
    governing_jurisdiction = models.CharField(max_length=255)
    termination_penalty_months = models.IntegerField(default=0)
    late_fee_percentage = models.FloatField(default=0.0)
    annual_escalation_rate = models.FloatField(default=0.0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'legal_api'
        verbose_name = "Legal Contract"
        verbose_name_plural = "Legal Contracts"

    def __str__(self):
        return f"{self.contract_type} - {self.governing_jurisdiction}"


class RiskFlag(models.Model):
    """Tracks isolated high/medium risk liabilities linked to a parent contract."""
    SEVERITY_CHOICES = [('HIGH', 'High'), ('MEDIUM', 'Medium'), ('LOW', 'Low')]
    
    contract = models.ForeignKey(LegalContract, on_delete=models.CASCADE, related_name='risk_flags')
    clause_type = models.CharField(max_length=100)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='MEDIUM')
    issue = models.TextField()
    original_text_snippet = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'legal_api'
        verbose_name = "Risk Flag"
        verbose_name_plural = "Risk Flags"


class ConflictEvaluation(models.Model):
    """Logs semantic checks evaluated across the internal matter database."""
    STATUS_CHOICES = [('CLEAR', 'Clear'), ('FLAGGED', 'Flagged')]
    
    adversary_party_name = models.CharField(max_length=255)
    matter_description = models.TextField()
    conflict_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='CLEAR')
    confidence_score = models.FloatField()
    system_rationale = models.TextField()
    evaluated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'legal_api'
        verbose_name = "Conflict Evaluation"
        verbose_name_plural = "Conflict Evaluations"

    def __str__(self):
        return f"Check: {self.adversary_party_name} ({self.conflict_status})"