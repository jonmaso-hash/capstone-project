from django.contrib import admin
from .models import PropertyListing, BuyerMandate, UnderwritingReport

@admin.register(PropertyListing)
class PropertyListingAdmin(admin.ModelAdmin):
    # Columns that appear in the admin list dashboard view
    list_display = ('property_name', 'asset_class', 'units', 'implied_cap_rate', 'created_at')
    
    # Sidebar filters to drill down into data quickly
    list_filter = ('asset_class', 'created_at')
    
    # Search bar config for scanning properties by name or address strings
    search_fields = ('property_name', 'address', 'description')
    
    # Organizes records by the newest entries first
    ordering = ('-created_at',)


@admin.register(BuyerMandate)
class BuyerMandateAdmin(admin.ModelAdmin):
    list_display = ('user', 'asset_class', 'target_cap_rate_min', 'created_at')
    list_filter = ('asset_class', 'target_cap_rate_min')
    search_fields = ('user__username', 'buy_box_description')


@admin.register(UnderwritingReport)
class UnderwritingReportAdmin(admin.ModelAdmin):
    list_display = ('property_listing', 'gross_potential_rent', 'net_operating_income', 'created_at')
    ordering = ('-created_at',)