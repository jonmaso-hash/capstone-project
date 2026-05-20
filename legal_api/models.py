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