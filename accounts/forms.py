from django import forms
from matchmaking.models import Application, InvestorApplication

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
            "description", # This replaces the old 'business_description'
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
        # Adding Bootstrap classes for consistent UI
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "reason_for_capital": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "extra_info": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        }

# -----------------------------
# Investor Application Form
# -----------------------------
class InvestorForm(forms.ModelForm):
    INVESTMENT_STAGE_CHOICES = [
        ("Pre-Seed", "Pre-Seed"),
        ("Seed", "Seed"),
        ("Series-A", "Series-A"),
        ("Series-B", "Series-B"),
        ("Series-C+", "Series-C+"),
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
            "website", # Added to match your InvestorApplication model
            "investment_focus",
            "investment_stage",
            "investment_amount",
        ]
        widgets = {
            "investment_focus": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
        }