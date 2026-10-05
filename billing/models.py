from django.conf import settings
from django.db import models


class Subscription(models.Model):
    """
    Source of truth for a user's Stripe subscription lifecycle. Stripe
    webhooks write here; the fast, cheap `is_premium` boolean already checked
    throughout matchmaking/views.py (request_intro, export_search_csv, etc.)
    stays in sync with this via the webhook handler in billing/views.py.
    """

    class Plan(models.TextChoices):
        FOUNDER_PREMIUM = 'FOUNDER_PREMIUM', 'Founder Premium'
        INVESTOR_PREMIUM = 'INVESTOR_PREMIUM', 'Investor Premium'
        SELLER_PREMIUM = 'SELLER_PREMIUM', 'Seller Premium'
        BUYER_PREMIUM = 'BUYER_PREMIUM', 'Buyer Premium'
        INVESTOR_FIRM = 'INVESTOR_FIRM', 'Investor Firm'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        PAST_DUE = 'past_due', 'Past Due'
        CANCELED = 'canceled', 'Canceled'
        INCOMPLETE = 'incomplete', 'Incomplete'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscriptions',
    )
    plan = models.CharField(max_length=20, choices=Plan.choices)
    stripe_customer_id = models.CharField(max_length=255)
    stripe_subscription_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INCOMPLETE)
    current_period_end = models.DateTimeField(null=True, blank=True)
    # Cancelling here asks Stripe to stop at the end of the period the customer
    # already paid for, so access is never taken away mid-period. Stripe remains
    # the source of truth; this mirrors it so the billing page can say what ends
    # and when without a round trip.
    cancel_at_period_end = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.get_plan_display()} ({self.status})"

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE


class SubscriptionConsent(models.Model):
    """
    What the customer was told about the recurring charge, and when they agreed.

    Federal law is ROSCA since the FTC's click-to-cancel rule was vacated in
    July 2025, and the strictest state rules (California's amended ARL) ask for
    affirmative consent to the renewal terms, kept on the record. Storing the
    exact text shown — rather than a version number pointing at wording that may
    since have changed — is the point: this row is the evidence of what was
    actually on screen when the box was ticked.

    Written before checkout starts. `billing_state` is filled in afterwards from
    Stripe's billing address, which is the authoritative jurisdiction and is only
    known once the customer has entered it.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription_consents',
    )
    plan = models.CharField(max_length=20)
    price_usd = models.PositiveIntegerField()
    interval = models.CharField(max_length=20, default='month')
    terms_text = models.TextField(help_text="The exact disclosure shown when consent was given")
    agreed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    stripe_checkout_session_id = models.CharField(max_length=255, blank=True)
    billing_country = models.CharField(max_length=2, blank=True)
    billing_state = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ['-agreed_at']
        indexes = [models.Index(fields=['user', '-agreed_at'])]

    def __str__(self):
        return f"{self.user.username} agreed to {self.plan} at {self.agreed_at:%Y-%m-%d}"
