import re

from django import forms
from matchmaking.models import Application, InvestorApplication, SellerApplication, BuyerApplication
from django.contrib.auth import get_user_model

User = get_user_model()


class CommaFormattedNumberInput(forms.TextInput):
    """
    Renders a Decimal value with thousands-separator commas (e.g.
    "500,000") instead of a raw number. Client-side JS (see
    edit_founder_profile.html) keeps the commas live as the user types;
    format_value handles the initial page-load render and re-renders after
    a validation error, so the field never flashes unformatted.

    value_from_datadict strips the commas back out before Django's
    DecimalField.to_python ever sees the submitted value — to_python calls
    Decimal(str(value)) directly and raises on a comma-containing string,
    so this has to happen at the widget level, before field-level cleaning,
    not in a clean_<field> method (which only runs after to_python already
    succeeded).
    """

    def format_value(self, value):
        if value in (None, ''):
            return ''
        try:
            return '{:,.0f}'.format(float(value))
        except (TypeError, ValueError):
            return value

    def value_from_datadict(self, data, files, name):
        value = super().value_from_datadict(data, files, name)
        if value in (None, ''):
            return value
        return re.sub(r'[^\d.]', '', value)


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
            "raising_amount": CommaFormattedNumberInput(attrs={"inputmode": "numeric", "class": "currency-input"}),
            "prior_amount_raised": CommaFormattedNumberInput(attrs={"inputmode": "numeric", "class": "currency-input"}),
            "current_revenue": CommaFormattedNumberInput(attrs={"inputmode": "numeric", "class": "currency-input"}),
            "monthly_burn_rate": CommaFormattedNumberInput(attrs={"inputmode": "numeric", "class": "currency-input"}),
        }

    def __init__(self, *args, lock_vector_fields=False, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Bootstrap classes to all fields automatically
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"

        # "Years in Business" was ambiguous about which start point it measured
        # from — relabeled to make clear it's time since legal founding, not
        # since the idea started. Still the same plain-integer field; the
        # tooltip in the template explains the "since founding" framing, and
        # profile.html derives an approximate founding year for display.
        self.fields["years_in_business"].label = "Years Since Founding"

        # prior_amount_raised/years_in_business live in the "optional" collapsed
        # section of the template — they must not be browser-required (the user
        # can't fix a validation error on a field they can't see), so we relax
        # them here and default to 0 in clean_* if left blank, matching the
        # model's own default=0.
        self.fields["prior_amount_raised"].required = False
        self.fields["years_in_business"].required = False

        # A brand-new application shouldn't show a pre-filled value on fields the
        # matching engine actually weighs — "Other"/"Seed"/0 look like real answers,
        # so a rushed signup would silently submit them without the founder noticing.
        if self.instance.pk is None:
            self.initial["sector"] = ""
            self.fields["sector"].widget.attrs["placeholder"] = "e.g. FinTech, SaaS, Healthcare"
            self.initial["stage"] = ""
            self.fields["stage"].widget.attrs["placeholder"] = "e.g. Seed, Series A"
            self.initial["raising_amount"] = None
            self.fields["raising_amount"].widget.attrs["placeholder"] = "e.g. 500,000"
            self.initial["prior_amount_raised"] = None
            self.fields["prior_amount_raised"].widget.attrs["placeholder"] = "e.g. 0"

        if lock_vector_fields:
            for field_name in Application.VECTOR_FIELDS:
                if field_name in self.fields:
                    self.fields[field_name].disabled = True

    def clean_prior_amount_raised(self):
        return self.cleaned_data.get("prior_amount_raised") or 0

    def clean_years_in_business(self):
        return self.cleaned_data.get("years_in_business") or 0

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
            "ticket_size_min",
            "ticket_size_max",
            "investment_thesis_summary",
            "weight_problem_solution",
            "weight_capital_plan",
            "weight_market_context",
        ]
        widgets = {
            "investment_focus": forms.Textarea(attrs={"rows": 4}),
            "investment_thesis_summary": forms.Textarea(attrs={"rows": 4}),
            "weight_problem_solution": forms.NumberInput(attrs={"step": "0.05", "min": "0", "max": "1"}),
            "weight_capital_plan": forms.NumberInput(attrs={"step": "0.05", "min": "0", "max": "1"}),
            "weight_market_context": forms.NumberInput(attrs={"step": "0.05", "min": "0", "max": "1"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        optional_fields = [
            "phone", "website", "linkedin_url", "location",
            "ticket_size_min", "ticket_size_max", "investment_thesis_summary",
            "weight_problem_solution", "weight_capital_plan", "weight_market_context",
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
            "pitch_video",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "reason_for_sale": forms.Textarea(attrs={"rows": 3}),
            "extra_info": forms.Textarea(attrs={"rows": 2}),
            "cim_document": forms.FileInput(),
            "pitch_video": forms.FileInput(),
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

        # years_in_business lives in the "optional" collapsed section of the
        # template — must not be browser-required (see ApplicationForm for why).
        self.fields["years_in_business"].required = False

        # Same fix as ApplicationForm: don't let a new listing silently inherit
        # "Other" industry or a $0 asking price just because the seller didn't touch the field.
        if self.instance.pk is None:
            self.initial["industry"] = ""
            self.fields["industry"].widget.attrs["placeholder"] = "e.g. Manufacturing, Retail, SaaS"
            self.initial["asking_price"] = None
            self.fields["asking_price"].widget.attrs["placeholder"] = "e.g. 500000"

        if lock_vector_fields:
            for field_name in SellerApplication.VECTOR_FIELDS:
                if field_name in self.fields:
                    self.fields[field_name].disabled = True

    def clean_years_in_business(self):
        return self.cleaned_data.get("years_in_business") or 0

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

        self.fields["acquisition_thesis"].widget.attrs["placeholder"] = (
            "e.g. Profitable manufacturing businesses, $1–5M revenue, Southeast US"
        )

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