from django.contrib import admin
from .models import LeadICPScore, CompetitorAudit

@admin.register(LeadICPScore)
class LeadICPScoreAdmin(admin.ModelAdmin):
    # Columns displayed in the admin dashboard list view
    list_display = ('company_url', 'icp_alignment_score', 'created_at')
    
    # Allows you to filter results by score or date in the sidebar
    list_filter = ('icp_alignment_score', 'created_at')
    
    # Adds a search bar targeting the company URL
    search_fields = ('company_url', 'qualification_signals')
    
    # Automatically organizes fields chronologically
    ordering = ('-created_at',)


@admin.register(CompetitorAudit)
class CompetitorAuditAdmin(admin.ModelAdmin):
    list_display = ('id', 'competitor_count', 'created_at')
    list_filter = ('created_at',)
    ordering = ('-created_at',)

    def competitor_count(self, obj):
        """Custom column to show how many URLs were analyzed in this batch"""
        if obj.competitor_urls:
            # Assumes list data is stored as a string or list format
            return len(obj.competitor_urls)
        return 0
    competitor_count.short_description = "Competitors Audited"