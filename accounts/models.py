from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


# =================================================
# INVESTOR PROFILE
# =================================================
class Investor(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.name


# =================================================
# APPLICATION (FOUNDERS)
# =================================================
class Application(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="application"
    )

    # Founder info
    founder_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=30, blank=True, null=True)

    # Company info
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

    investors = models.ManyToManyField(
        Investor,
        through="DealFlowLog",
        blank=True,
        related_name="applications"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name or self.founder_name


# =================================================
# INVESTOR APPLICATION (optional onboarding form)
# =================================================
class InvestorApplication(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="investor_application"
    )

    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True, null=True)

    company_name = models.CharField(max_length=255)

    investment_focus = models.CharField(max_length=255)
    investment_stage = models.CharField(max_length=255)
    investment_amount = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.full_name


# =================================================
# DEAL FLOW LOG (JOIN TABLE)
# =================================================
class DealFlowLog(models.Model):
    investor = models.ForeignKey(Investor, on_delete=models.CASCADE)
    application = models.ForeignKey(Application, on_delete=models.CASCADE)

    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("investor", "application")
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.investor.name} → {self.application.company_name}"