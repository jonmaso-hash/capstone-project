from django.contrib import admin, messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django import forms
from django.shortcuts import render
from django.http import HttpResponseRedirect

from .models import Application, Investor, DealFlowLog

# =================================================
# FORMS
# =================================================

class ApplicationAdminForm(forms.ModelForm):
    """Form for Application Detail view with Investor checkboxes."""
    investors = forms.ModelMultipleChoiceField(
        queryset=Investor.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Application
        fields = "__all__"


class SendToSingleInvestorForm(forms.Form):
    """Form for the intermediate action page."""
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    investor = forms.ModelChoiceField(
        queryset=Investor.objects.all(),
        label="Select the recipient investor",
        required=True
    )


# =================================================
# UTILS
# =================================================

def send_deal_flow_email(app, investor):
    """Helper to standardize email sending across different actions."""
    html_content = render_to_string(
        "accounts/emails/founder_profile.html",
        {
            "founder": app.user,
            "application": app,
        },
    )
    return send_mail(
        subject=f"KCV Capital Deal Flow: {app.company_name}",
        message=f"New founder profile: {app.company_name}",
        from_email="admin@kcvcapital.com",
        recipient_list=[investor.email],
        html_message=html_content,
        fail_silently=False,
    )


# =================================================
# ACTIONS
# =================================================

@admin.action(description="Assign selected Applications to ALL Investors")
def assign_investors(modeladmin, request, queryset):
    investors = Investor.objects.all()
    if not investors.exists():
        messages.error(request, "No investors found.")
        return

    count = 0
    for app in queryset:
        for investor in investors:
            DealFlowLog.objects.get_or_create(investor=investor, application=app)
            count += 1
    messages.success(request, f"Created {count} deal flow assignments.")


@admin.action(description="Send emails to ALREADY ASSIGNED investors")
def send_profile_to_assigned_investors(modeladmin, request, queryset):
    sent_count = 0
    for app in queryset:
        logs = DealFlowLog.objects.filter(application=app)
        if not logs.exists():
            messages.warning(request, f"No investors assigned to {app.company_name}")
            continue

        for log in logs:
            send_deal_flow_email(app, log.investor)
            sent_count += 1
    messages.success(request, f"Sent {sent_count} emails successfully.")


@admin.action(description="Send selected to ONE specific investor")
def send_to_single_investor_action(modeladmin, request, queryset):
    """Intermediate page action to pick one investor for selected applications."""
    if 'apply' in request.POST:
        form = SendToSingleInvestorForm(request.POST)
        if form.is_valid():
            investor = form.cleaned_data['investor']
            for app in queryset:
                # Log the deal flow and send the email
                DealFlowLog.objects.get_or_create(investor=investor, application=app)
                send_deal_flow_email(app, investor)
            
            messages.success(request, f"Successfully sent {queryset.count()} application(s) to {investor.name}.")
            return HttpResponseRedirect(request.get_full_path())
    else:
        # Correctly pull the selected checkboxes from the POST data
        selected_ids = request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME)
        form = SendToSingleInvestorForm(initial={
            '_selected_action': selected_ids
        })

    return render(request, "admin/send_to_investor_intermediate.html", {
        "items": queryset,
        "form": form,
        "action": "send_to_single_investor_action"
    })


# =================================================
# ADMIN CLASSES
# =================================================

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    form = ApplicationAdminForm
    list_display = ("company_name", "founder_name", "email", "created_at")
    search_fields = ("company_name", "founder_name", "email")
    list_filter = ("sector", "stage", "created_at")
    
    actions = [
        assign_investors,
        send_profile_to_assigned_investors,
        send_to_single_investor_action,
    ]

    def save_model(self, request, obj, form, change):
        """Handle the investor checkbox logic when saving an individual Application."""
        super().save_model(request, obj, form, change)
        investors = form.cleaned_data.get("investors")
        if investors:
            for investor in investors:
                DealFlowLog.objects.get_or_create(investor=investor, application=obj)


@admin.register(Investor)
class InvestorAdmin(admin.ModelAdmin):
    list_display = ("name", "email")
    search_fields = ("name", "email")


@admin.register(DealFlowLog)
class DealFlowLogAdmin(admin.ModelAdmin):
    list_display = ("investor", "application", "sent_at")
    list_filter = ("sent_at",)