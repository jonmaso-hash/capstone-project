from django.contrib import admin, messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from .models import Application

@admin.action(description="Send selected Founder profiles to an Investor")
def send_profile_to_investor(modeladmin, request, queryset):
    # This email should be updated to the specific recipient or a dynamic selection
    investor_email = "investor@example.com" 

    for app in queryset:
        # Render the template located in accounts/templates/accounts/emails/
        html_content = render_to_string('accounts/emails/founder_profile.html', {
            'founder': app.user,
            'application': app
        })

        send_mail(
            subject=f"KCV Capital Deal Flow: {app.company_name}",
            message=f"Profile details for {app.company_name}", 
            from_email="admin@kcvcapital.com", 
            recipient_list=[investor_email],
            html_message=html_content,
            fail_silently=False,
        )

    messages.success(request, f"Successfully sent {queryset.count()} profiles to {investor_email}.")

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    # Merged list_display with fields from both requirements[cite: 2]
    list_display = ("company_name", "founder_name", "email", "created_at")
    search_fields = ("company_name", "founder_name", "email")
    list_filter = ("sector", "stage", "created_at")
    
    # Add the custom action to the admin interface
    actions = [send_profile_to_investor]