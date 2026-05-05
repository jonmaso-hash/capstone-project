from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Application(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="application"
    )

    # Founder
    founder_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=30, blank=True, null=True)

    # Company
    company_name = models.CharField(max_length=255)
    company_website = models.URLField(blank=True, null=True)

    description = models.TextField()
    business_description = models.TextField(blank=True, null=True)

    current_revenue = models.CharField(max_length=50, blank=True, null=True)

    sector = models.CharField(max_length=255, blank=True, null=True)
    stage = models.CharField(max_length=50, blank=True, null=True)

    years_in_business = models.PositiveIntegerField(blank=True, null=True)
    company_size = models.CharField(max_length=50, blank=True, null=True)

    raising_amount = models.CharField(max_length=50, blank=True, null=True)
    prior_amount_raised = models.CharField(max_length=50, blank=True, null=True)


    reason_for_capital = models.TextField(blank=True, null=True)
    extra_info = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # ✅ FIX for your crash

    def __str__(self):
        return self.company_name or self.user.username