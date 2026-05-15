from django.db import models
from django.contrib.auth.models import User

class InvestorApplication(models.Model):
    # Core Relationship
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='accounts_investor_profile')
    
    # Firm Details
    company_name = models.CharField(max_length=255)
    website = models.URLField(max_length=500, blank=True, null=True)
    full_name = models.CharField(max_length=255) # For the profile header we built
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    # The Mandate (The "Rules" for the engine)
    investment_focus = models.CharField(max_length=255) # e.g., "SaaS, AI, FinTech"
    investment_stage = models.CharField(max_length=50)  # e.g., "Seed, Series A"
    
    # Financials
    # Rename to 'target_ticket_size' or keep 'investment_amount'
    investment_amount = models.DecimalField(max_digits=15, decimal_places=2, help_text="Average check size")
    min_check = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    max_check = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Geographic Focus (Vital for many investors)
    location_preference = models.CharField(max_length=255, default="Global") # e.g., "North America", "San Diego"

    # Social Proof / Trust
    is_verified = models.BooleanField(default=False) # Manual flag for you to set
    linkedin_url = models.URLField(blank=True, null=True)

    # AI & Metadata
    focus_vector = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.company_name} ({self.user.username})"