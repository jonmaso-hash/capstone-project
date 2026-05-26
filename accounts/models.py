# accounts/models.py
from django.db import models
from django.conf import settings

class InvestorApplication(models.Model):
    # Fixed: Removed duplicate 'user' field. Keeping OneToOneField as the primary link.
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='accounts_investor_profile')
    
    # Firm Details
    company_name = models.CharField(max_length=255)
    full_name = models.CharField(max_length=255)
    website = models.URLField(max_length=500, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    # The Mandate
    sector = models.CharField(max_length=100)
    investment_focus = models.CharField(max_length=255) 
    investment_stage = models.CharField(max_length=50) 
    funding_stage = models.CharField(max_length=50)
    
    # Financials
    investment_amount = models.DecimalField(max_digits=15, decimal_places=2, help_text="Average check size")
    min_check = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    max_check = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Metadata & Social
    location_preference = models.CharField(max_length=255, default="Global")
    is_verified = models.BooleanField(default=False)
    linkedin_url = models.URLField(blank=True, null=True)
    focus_vector = models.JSONField(null=True, blank=True)
    years_in_business = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    stated_thesis = models.TextField(blank=True, null=True, help_text="What they typed in the form")
    portfolio_raw_text = models.TextField(blank=True, null=True, help_text="Scraped from their uploaded PDF/Deck")
    historical_vector_embedding = models.JSONField(blank=True, null=True, help_text="Mathematical representation of past deals")

    def __str__(self):
        return f"{self.company_name} - {self.user.username}"

class FounderApplication(models.Model):
    # Core Relationship
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='founder_applications')
    
    # Added fields to resolve (admin.E108) errors
    company_name = models.CharField(max_length=255)
    sector = models.CharField(max_length=100)
    funding_stage = models.CharField(max_length=50)

    # Diligence fields
    current_revenue = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True, 
        help_text="Current Annual Recurring Revenue (ARR)"
    )
    company_size = models.PositiveIntegerField(
        null=True, blank=True, help_text="Number of full-time employees"
    )
    years_in_business = models.PositiveIntegerField(
        default=0, help_text="Years since incorporation"
    )

    def __str__(self):
        return f"{self.company_name} ({self.user.username})"