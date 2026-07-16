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
