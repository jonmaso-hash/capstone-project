from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    company_name = models.CharField(max_length=255, blank=True, null=True)
    sector = models.CharField(max_length=255, blank=True, null=True)
    funding_stage = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.user.username


class CompanyProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company_name = models.CharField(max_length=255)

    def __str__(self):
        return self.company_name


# ✅ NEW: Founder Application Model
class FounderApplication(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # Personal
    founder_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    # Company
    company_name = models.CharField(max_length=255)
    company_website = models.URLField(blank=True, null=True)

    # Descriptions
    pitch_summary = models.TextField()
    business_description = models.TextField(blank=True, null=True)

    # Funding & stage
    sector = models.CharField(max_length=255, blank=True, null=True)
    stage = models.CharField(max_length=50, blank=True, null=True)
    raising_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    years_in_business = models.IntegerField(blank=True, null=True)
    company_size = models.CharField(max_length=50, blank=True, null=True)
    amount_raised = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    # Intent
    reason_for_capital = models.TextField(blank=True, null=True)

    # Extra
    extra_info = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.company_name} ({self.founder_name})"