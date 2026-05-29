# accounts/models.py
from django.db import models
from django.conf import settings

class InvestorApplication(models.Model):
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

    # --- INCOGNITO & PRIVACY LAYER ---
    is_private = models.BooleanField(
        default=False, 
        help_text="Incognito Mode: Hides your mandate from dashboards, smart filters, and global AI memo index tools."
    )
    allowed_viewers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        blank=True, 
        related_name='permitted_investor_profiles',
        help_text="Users granted direct access via accepted invitation paths."
    )
    
    @property
    def completion_percentage(self):
        """Calculates setup completeness across institutional mandate parameters."""
        tracked_fields = [
            self.company_name,
            self.investment_focus,
            self.investment_stage,
            self.investment_amount,
            self.full_name,
            self.email,
            self.phone,
        ]
        filled_count = sum(1 for field in tracked_fields if field not in (None, "", 0))
        return int((filled_count / len(tracked_fields)) * 100)

    def __str__(self):
        return f"{self.company_name} - {self.user.username}"

class FounderApplication(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='accounts_founder_profile'
    )
    
    company_name = models.CharField(max_length=255)
    sector = models.CharField(max_length=100)
    funding_stage = models.CharField(max_length=50)

    # Diligence fields
    current_revenue = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True, 
        help_text="Current Annual Recurring Recurring Revenue (ARR)"
    )
    company_size = models.PositiveIntegerField(
        null=True, blank=True, help_text="Number of full-time employees"
    )
    years_in_business = models.PositiveIntegerField(
        default=0, help_text="Years since incorporation"
    )

    # --- INCOGNITO & PRIVACY LAYER ---
    is_private = models.BooleanField(
        default=False, 
        help_text="Incognito Mode: Hides your pitch tracking records from public bulletin boards, global metrics grids, and Zelda AI."
    )
    allowed_viewers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        blank=True, 
        related_name='permitted_founder_profiles',
        help_text="Investors authorized to audit this company via invite workflow matches."
    )
    
    @property
    def completion_percentage(self):
        """Calculates setup completeness across core startup metrics."""
        tracked_fields = [
            self.company_name,
            self.sector,
            self.funding_stage,
            self.description,
            self.founder_name,
            self.email,
            self.raising_amount,
            self.current_revenue,
            self.company_website,
            self.pitch_deck,
        ]
        # Evaluates fields that are not None, empty strings, or 0
        filled_count = sum(1 for field in tracked_fields if field not in (None, "", 0))
        return int((filled_count / len(tracked_fields)) * 100)

    def __str__(self):
        return f"{self.company_name} ({self.user.username})"