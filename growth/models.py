import secrets

from django.conf import settings
from django.db import models


class ReferralInvite(models.Model):
    """
    Dual-sided referral loop — a founder inviting a lead from their
    Fundraising CRM, or an investor inviting a portfolio company from Deal
    Pulse, to join Interlink Foundry. Mirrors ops.Invite's token shape
    (email + secrets-generated code + status + timestamps) since that's
    already the established invite pattern in this codebase, just scoped
    to organic user-to-user referrals instead of staff-driven beta invites.
    """

    SOURCE_CHOICES = [
        ('fundraising_lead', 'Fundraising CRM Lead'),
        ('deal_pulse_portfolio', 'Deal Pulse Portfolio Company'),
    ]
    ROLE_HINT_CHOICES = [
        ('INVESTOR', 'Investor'),
        ('FOUNDER', 'Founder'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
    ]

    inviter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='referral_invites_sent')
    invitee_email = models.EmailField()
    role_hint = models.CharField(max_length=20, choices=ROLE_HINT_CHOICES)
    code = models.CharField(max_length=32, unique=True, editable=False)
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    # Separate from status — status flips to ACCEPTED the moment the invitee
    # completes signup, but the premium reward is granted once, at that same
    # moment; this flag is the guard against a retry/double-save granting it twice.
    reward_granted = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = secrets.token_urlsafe(16)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.inviter.username} -> {self.invitee_email} ({self.status})"


class PlatformInsightReport(models.Model):
    """
    Quarterly aggregated, anonymized deal-flow data drop (e.g. "The
    Interlink Foundry Q3 2026 Seed Valuation Report") — content marketing
    fuel generated from platform-wide stats only, never per-user data.
    Drafts are unpublished until staff review (same gate as
    ops.Announcement's is_active toggle).
    """

    title = models.CharField(max_length=255)
    period_label = models.CharField(max_length=50, help_text='e.g. "Q3 2026"')
    period_slug = models.SlugField(max_length=60, unique=True)
    body_sections = models.JSONField(default=list, help_text='List of {"heading": str, "text": str} sections.')
    generated_at = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"{self.title} ({'published' if self.is_published else 'draft'})"
