from django import forms
from matchmaking.models import Application, InvestorApplication
from django.contrib.auth import get_user_model

User = get_user_model()

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
            "current_revenue",
            "monthly_burn_rate",  # Added for Zelda Engine
            "team_size",          # Renamed from company_size
            "years_in_business",
            "sector",
            "stage",
            "raising_amount",
            "prior_amount_raised",
            "reason_for_capital",
            "extra_info",
            "pitch_deck",
            "is_private",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "reason_for_capital": forms.Textarea(attrs={"rows": 3}),
            "extra_info": forms.Textarea(attrs={"rows": 2}),
            "is_private": forms.CheckboxInput(attrs={"role": "switch"}),
            "pitch_deck": forms.FileInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Bootstrap classes to all fields automatically
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"

# -----------------------------
# Investor Application Form
# -----------------------------
class InvestorForm(forms.ModelForm):
    class Meta:
        model = InvestorApplication
        fields = [
            "full_name",
            "email",
            "phone",
            "company_name",
            "website",
            "investment_focus",
            "investment_stage",
            "investment_amount",
        ]
        widgets = {
            "investment_focus": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        optional_fields = ["phone", "website"]
        
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"
            
            if field_name not in optional_fields:
                field.widget.attrs["required"] = "required"
                field.required = True

# -----------------------------
# System User Creation Form
# -----------------------------
class CustomUserCreationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"