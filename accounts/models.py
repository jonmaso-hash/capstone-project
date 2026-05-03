from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Application(models.Model):
    """
    One application per user (OneToOne relationship).
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="application"
    )

    # Personal Details
    founder_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=30, blank=True, null=True)

    # Company Details
    company_name = models.CharField(max_length=255)
    company_website = models.URLField(blank=True, null=True)

    description = models.TextField()
    business_description = models.TextField(blank=True, null=True)

    # Business Info
    sector = models.CharField(max_length=255, blank=True, null=True)
    stage = models.CharField(max_length=50, blank=True, null=True)

    years_in_business = models.PositiveIntegerField(blank=True, null=True)
    company_size = models.CharField(max_length=50, blank=True, null=True)

    # Funding Info
    raising_amount = models.CharField(max_length=50, blank=True, null=True)
    amount_raised = models.CharField(max_length=50, blank=True, null=True)

    reason_for_capital = models.TextField(blank=True, null=True)

    # Extra
    extra_info = models.TextField(blank=True, null=True)

    # Meta
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Application"
        verbose_name_plural = "Applications"

    def __str__(self):
        return self.company_name or f"Application ({self.user.username})"