# real_estate_api/models.py
from django.db import models
from django.contrib.auth import get_user_model

# Fetch the active User model configured in your KCV project
User = get_user_model()

class PropertyListing(models.Model):
    """
    Stores core real estate asset profiles, including physical characteristics 
    and baseline financial indicators parsed by the underlying semantic layers.
    """
    ASSET_CLASSES = [
        ('multifamily', 'Multifamily'),
        ('industrial', 'Industrial'),
        ('retail', 'Retail'),
        ('office', 'Office'),
    ]
    
    property_name = models.CharField(max_length=255)
    address = models.CharField(max_length=500)
    asset_class = models.CharField(max_length=50, choices=ASSET_CLASSES, default='multifamily')
    units = models.IntegerField(default=1)
    implied_cap_rate = models.FloatField(default=0.0)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Property Listing"
        verbose_name_plural = "Property Listings"

    def __str__(self):
        return f"{self.property_name} ({self.get_asset_class_display()})"


class BuyerMandate(models.Model):
    """
    Tracks institutional investor buy-boxes (unstructured text requirements) 
    to drive Zelda's property-matching radar calculations.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='buyer_mandates')
    asset_class = models.CharField(max_length=50, choices=PropertyListing.ASSET_CLASSES, default='multifamily')
    target_cap_rate_min = models.FloatField(default=5.0)
    buy_box_description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Buyer Mandate"
        verbose_name_plural = "Buyer Mandates"

    def __str__(self):
        return f"Mandate: {self.user.username} - {self.asset_class}"


class UnderwritingReport(models.Model):
    """
    Stores deeply extracted financial metrics and structural risks parsed directly 
    from multi-page Offering Memorandums (OMs) by the multimodal engine.
    """
    property_listing = models.OneToOneField(PropertyListing, on_delete=models.CASCADE, related_name='underwriting_report')
    gross_potential_rent = models.DecimalField(decimal_places=2, max_digits=15)
    net_operating_income = models.DecimalField(decimal_places=2, max_digits=15)
    risk_factors_detected = models.JSONField(default=list)  # Tracks an array of found risk flags
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Underwriting Report"
        verbose_name_plural = "Underwriting Reports"

    def __str__(self):
        return f"Underwriting Analysis: {self.property_listing.property_name}"