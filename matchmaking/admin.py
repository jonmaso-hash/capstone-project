from django.contrib import admin
from .models import Application, InvestorApplication, AIMatch, Connection, MatchFeedback


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("company_name", "founder_name", "sector", "stage", "raising_amount", "is_private", "created_at")
    list_filter = ("stage", "sector", "is_private")
    search_fields = ("company_name", "founder_name", "email", "description")
    readonly_fields = ("created_at", "updated_at")


@admin.register(InvestorApplication)
class InvestorApplicationAdmin(admin.ModelAdmin):
    list_display = ("company_name", "full_name", "investment_stage", "investment_amount", "is_private", "created_at")
    list_filter = ("investment_stage", "is_private")
    search_fields = ("company_name", "full_name", "email", "investment_focus")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AIMatch)
class AIMatchAdmin(admin.ModelAdmin):
    # FIXED: Swapped 'founder' out for custom display method, and removed the missing 'reasons' property
    list_display = ("investor", "get_founder_company", "score", "created_at")
    list_filter = ("score", "created_at")
    readonly_fields = ("created_at",)

    def get_founder_company(self, obj):
        """Safely fetches target venture name from relation link."""
        return obj.application.company_name
    get_founder_company.short_description = "Founder Company"


@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    list_display = ("investor", "founder", "status", "created_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("investor__company_name", "founder__company_name")


@admin.register(MatchFeedback)
class MatchFeedbackAdmin(admin.ModelAdmin):
    list_display = ("user", "application", "investor", "vote", "created_at")
    list_filter = ("vote", "created_at")