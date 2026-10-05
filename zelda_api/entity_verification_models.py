# zelda_api/entity_verification_models.py
"""
Entity Integrity -- a distinct trust question from Truth Delta's "are the
claims internally consistent?": "does this business exist as claimed, checked
against public sources?" (a fabricated deck can be internally consistent while
the company itself is fictional). Kept as its own model and report section so
the two questions never get conflated.

A report belongs to one business: a startup (Application) or a business for
sale (SellerApplication) -- never to a founder's user account, so the same
report serves either side of the marketplace. Reports made before this carried
only a document; those rows keep working through `document`.

Each finding is a row in `findings`:
    {check, claim, interlink_source, evidence_source, evidence, source_url,
     result, checked_at}
with `result` one of the RESULT_LABELS keys. Nothing here is a verdict or a
score. Who may see a report is decided per report (EntityReportAccessGrant),
not per company, so purchased and shared reports can slot in later.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q

from .vector_models import DocumentSource


class EntityVerificationReport(models.Model):
    MATCHES = 'matches'
    DOESNT_MATCH = 'doesnt_match'
    NOT_FOUND = 'not_found'
    NOT_APPLICABLE = 'not_applicable'
    COULDNT_CHECK = 'couldnt_check'
    PUBLIC_RECORD = 'public_record'
    RESULT_LABELS = {
        MATCHES: 'Matches',
        DOESNT_MATCH: "Doesn't match",
        NOT_FOUND: 'Not found',
        NOT_APPLICABLE: 'Not applicable',
        COULDNT_CHECK: "Couldn't check",
        PUBLIC_RECORD: 'Public record',
    }

    PENDING = 'pending'
    COMPLETE = 'complete'
    STATUS_CHOICES = [(PENDING, 'Checking'), (COMPLETE, 'Complete')]

    # The business being checked -- exactly one for new reports (see Meta).
    founder_profile = models.ForeignKey(
        'matchmaking.Application', on_delete=models.CASCADE, null=True, blank=True,
        related_name='entity_verification_reports',
    )
    seller_profile = models.ForeignKey(
        'matchmaking.SellerApplication', on_delete=models.CASCADE, null=True, blank=True,
        related_name='entity_verification_reports',
    )
    document = models.ForeignKey(
        DocumentSource, on_delete=models.CASCADE, null=True, blank=True,
        related_name='entity_verification_reports',
        help_text="The deck this check was run from, when there was one. The only link on reports made before business-level checks.",
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=COMPLETE)
    checked_at = models.DateTimeField(null=True, blank=True, help_text="When public sources were consulted.")
    inputs_hash = models.CharField(
        max_length=64, blank=True,
        help_text="Fingerprint of the profile fields checked, so an edited profile gets a fresh check.",
    )
    findings = models.JSONField(default=list, blank=True)

    # Earlier Entity Integrity fields, still read for reports made before findings existed.
    domain = models.CharField(max_length=255, blank=True)
    domain_registered_date = models.DateField(null=True, blank=True)
    domain_lookup_error = models.CharField(
        max_length=255, blank=True,
        help_text="Short, user-facing reason the domain lookup didn't produce a date — never a raw exception.",
    )
    claimed_founding_year = models.PositiveIntegerField(null=True, blank=True)
    timeline_flags = models.JSONField(
        default=list, blank=True,
        help_text="Plain-language mismatches between the claimed founding year and external signals.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=Q(founder_profile__isnull=True) | Q(seller_profile__isnull=True),
                name='entity_report_one_business_at_most',
            ),
            models.CheckConstraint(
                condition=Q(founder_profile__isnull=False) | Q(seller_profile__isnull=False) | Q(document__isnull=False),
                name='entity_report_has_a_business_or_document',
            ),
        ]

    def __str__(self):
        return f"Entity Integrity for {self.subject or f'document {self.document_id}'}"

    @property
    def subject(self):
        """The business this report is about, whichever side of the marketplace it is on."""
        if self.founder_profile_id:
            return self.founder_profile
        if self.seller_profile_id:
            return self.seller_profile
        return None

    @property
    def owner(self):
        subject = self.subject
        if subject is not None:
            return subject.user
        return self.document.uploaded_by if self.document_id else None


class EntityReportAccessGrant(models.Model):
    """
    Permission to see one specific report -- "can this user view report Y?", not
    "can this user see company Z?". Today a grant comes from requesting the
    check or confirming a paid analysis; purchases and shares will add more.
    The business owner and staff never need one.
    """
    report = models.ForeignKey(EntityVerificationReport, on_delete=models.CASCADE, related_name='access_grants')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='entity_report_grants')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['report', 'user'], name='entity_report_grant_once_per_user'),
        ]

    def __str__(self):
        return f"{self.user} may view entity report {self.report_id}"
