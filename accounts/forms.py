from django import forms
from matchmaking.models import Application, InvestorApplication, SellerApplication, BuyerApplication
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
            "linkedin_url",
            "description",
            "current_revenue",
            "monthly_burn_rate",  # Added for Zelda Engine
            "team_size",          # Renamed from company_size
            "years_in_business",
            "sector",
            "stage",
            "geography",
            "raising_amount",
            "prior_amount_raised",
            "reason_for_capital",
            "extra_info",
            "pitch_deck",
            "pitch_video",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "reason_for_capital": forms.Textarea(attrs={"rows": 3}),
            "extra_info": forms.Textarea(attrs={"rows": 2}),
            "pitch_deck": forms.FileInput(),
            "pitch_video": forms.FileInput(),
        }

    def __init__(self, *args, lock_vector_fields=False, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Bootstrap classes to all fields automatically
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"

        if lock_vector_fields:
            for field_name in Application.VECTOR_FIELDS:
                if field_name in self.fields:
                    self.fields[field_name].disabled = True

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
            "linkedin_url",
            "location",
            "investment_focus",
            "investment_stage",
            "investment_amount",
        ]
        widgets = {
            "investment_focus": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        optional_fields = ["phone", "website", "linkedin_url", "location"]
        
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
# Seller (Business-for-Sale) Application Form
# -----------------------------
class SellerForm(forms.ModelForm):
    class Meta:
        model = SellerApplication
        fields = [
            "company_name",
            "company_website",
            "seller_name",
            "email",
            "phone_number",
            "linkedin_url",
            "description",
            "industry",
            "geography",
            "annual_revenue",
            "ebitda",
            "asking_price",
            "deal_structure",
            "team_size",
            "years_in_business",
            "reason_for_sale",
            "extra_info",
            "cim_document",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "reason_for_sale": forms.Textarea(attrs={"rows": 3}),
            "extra_info": forms.Textarea(attrs={"rows": 2}),
            "cim_document": forms.FileInput(),
        }

    def __init__(self, *args, lock_vector_fields=False, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"

        if lock_vector_fields:
            for field_name in SellerApplication.VECTOR_FIELDS:
                if field_name in self.fields:
                    self.fields[field_name].disabled = True

# -----------------------------
# Buyer (Acquirer) Application Form
# -----------------------------
class BuyerForm(forms.ModelForm):
    class Meta:
        model = BuyerApplication
        fields = [
            "full_name",
            "email",
            "phone",
            "company_name",
            "website",
            "linkedin_url",
            "location",
            "acquisition_thesis",
            "target_revenue_min",
            "target_revenue_max",
            "target_ebitda_min",
            "target_ebitda_max",
            "budget_min",
            "budget_max",
            "preferred_deal_structure",
        ]
        widgets = {
            "acquisition_thesis": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        optional_fields = [
            "phone", "website", "linkedin_url", "location",
            "target_revenue_min", "target_revenue_max",
            "target_ebitda_min", "target_ebitda_max",
        ]

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