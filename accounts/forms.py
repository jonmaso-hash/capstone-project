from django import forms
from django.forms import ModelForm
from .models import Application


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = [
            "company_name",
            "company_website",
            "founder_name",
            "email",
            "phone_number",
            "description",
            "business_description",
            "current_revenue",
            "sector",
            "stage",
            "raising_amount",
            "prior_amount_raised",
            "years_in_business",
            "company_size",
            "amount_raised",
            "reason_for_capital",
            "extra_info",
        ]