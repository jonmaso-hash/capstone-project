from django.contrib import admin, messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from .models import Application, InvestorApplication, AIMatch, Connection, MatchFeedback

# =================================================
# UTILS
# =================================================

def send_connection_email(app, investor_app):
    """Helper to send founder profiles to investors."""
    html_content = render_to_string(
        "matchmaking/emails/founder_profile.html", 
        {
            "application": app,
            "investor": investor_app,
        },
    )
    return send_mail(
        subject=f"Interlink Foundry Deal Flow: {app.company_name}",
        message=f"New founder profile: {app.company_name}",
        from_email="admin@interlinkfoundry.com",
        recipient_list=[investor_app.email],
        html_message=html_content,
        fail_silently=False,
    )

# =================================================
# ACTIONS
# =================================================

@admin.action(description="Approve and Send intro to Investor")
def approve_and_send_intro(modeladmin, request, queryset):
    """Action for the Connection model to bulk-approve intros."""
    sent_count = 0
    for connection in queryset:
        if connection.status != 'APPROVED':
            connection.status = 'APPROVED'
            connection.save()
            send_connection_email(connection.founder, connection.investor)
            sent_count += 1
    messages.success(request, f"Successfully approved and sent {sent_count} introductions.")

# =================================================
# ADMIN CLASSES
# =================================================

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("company_name", "founder_name", "email", "sector", "stage", "created_at")
    search_fields = ("company_name", "founder_name", "email")
    list_filter = ("sector", "stage")

@admin.register(InvestorApplication)
class InvestorApplicationAdmin(admin.ModelAdmin):
    list_display = ("company_name", "full_name", "email", "investment_stage")
    search_fields = ("company_name", "full_name", "email")

@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    list_display = ("investor", "founder", "status", "created_at")
    list_filter = ("status", "created_at")
    actions = [approve_and_send_intro]

@admin.register(AIMatch)
class AIMatchAdmin(admin.ModelAdmin):
    list_display = ("investor", "founder", "score", "created_at")
    readonly_fields = ("score", "reasons")

@admin.register(MatchFeedback)
class MatchFeedbackAdmin(admin.ModelAdmin):
    list_display = ("user", "application", "vote", "created_at")