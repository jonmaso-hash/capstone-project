# zelda_api/entity_verification_models.py
"""
Entity Integrity — a distinct trust question from Truth Delta's "are the
claims internally consistent?": "does this company/founder exist as
claimed, checked against external reality?" (a fabricated deck can be
internally consistent while the company itself is fictional). Kept as
its own model and its own report section rather than folded into
TruthDeltaReport, so the two questions never get conflated in the data
model or the UI.

Sprint 1 covers the two pillars buildable with zero external API keys:
domain age (WHOIS) and timeline consistency (pure logic over data already
gathered). Founder digital-footprint search and corporate-registry
matching are later sprints — this model only carries the fields Sprint 1
actually populates.
"""
from django.db import models

from .vector_models import DocumentSource


class EntityVerificationReport(models.Model):
    document = models.ForeignKey(
        DocumentSource, on_delete=models.CASCADE, related_name='entity_verification_reports'
    )

    # Domain Age pillar
    domain = models.CharField(max_length=255, blank=True)
    domain_registered_date = models.DateField(null=True, blank=True)
    domain_lookup_error = models.CharField(
        max_length=255, blank=True,
        help_text="Short, user-facing reason the domain lookup didn't produce a date — never a raw exception.",
    )

    # Timeline Consistency pillar
    claimed_founding_year = models.PositiveIntegerField(null=True, blank=True)
    timeline_flags = models.JSONField(
        default=list, blank=True,
        help_text="Plain-language mismatches between the claimed founding year and external signals.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Entity Integrity for document {self.document_id}"
