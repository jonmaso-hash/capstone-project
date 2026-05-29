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
            "sector",
            "stage",
            "raising_amount",
            "prior_amount_raised",
            "years_in_business",
            "company_size",
            "reason_for_capital",
            "extra_info",
            "pitch_deck",  # FIXED: Added field back so asset uploads save to your DB pipeline
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
        # Explicitly declare fields that are allowed to bypass validation
        optional_fields = ["extra_info", "is_private", "phone_number", "company_website", "prior_amount_raised", "years_in_business", "company_size"]
        
        for field_name, field in self.fields.items():
            # Apply uniform Bootstrap design patterns
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"
            
            # Enforce hard validation blocks natively in the HTML render
            if field_name not in optional_fields:
                field.widget.attrs["required"] = "required"
                field.required = True


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
        widget=forms.Select()
    )

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
            field.widget.attrs["required"] = "required"