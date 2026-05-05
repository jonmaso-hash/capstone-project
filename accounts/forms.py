from django import forms
from .models import Application, InvestorApplication


# -----------------------------
# Founder Application Form
# -----------------------------
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
            "reason_for_capital",
            "extra_info",
        ]


# -----------------------------
# Investor Application Form
# -----------------------------
class InvestorForm(forms.ModelForm):

    INVESTMENT_STAGE_CHOICES = [
        ("idea", "Pre-Seed"),
        ("early", "Seed"),
        ("growth", "Series-A"),
        ("late", "Series-B"),
        ("ipo", "Series-C+"),
        ("other", "Other"),
    ]

    investment_stage = forms.ChoiceField(
        choices=INVESTMENT_STAGE_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = InvestorApplication
        fields = [
            "full_name",
            "email",
            "phone",
            "company_name",
            "investment_focus",
            "investment_stage",
            "investment_amount",
        ]