from django import forms
from .models import PersonProfile


class PersonProfileForm(forms.ModelForm):
    class Meta:
        model = PersonProfile
        fields = ("display_name", "headline", "biography", "location", "website", "linkedin_url")
        widgets = {
            "biography": forms.Textarea(attrs={"rows": 5}),
            "display_name": forms.TextInput(attrs={"autocomplete": "name"}),
            "website": forms.URLInput(attrs={"placeholder": "https://"}),
            "linkedin_url": forms.URLInput(attrs={"placeholder": "https://www.linkedin.com/in/"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


from .models import EducationRecord, OrganizationRelationship, ProfessionalOrganization


class EducationRecordForm(forms.ModelForm):
    class Meta:
        model = EducationRecord
        fields = ("institution", "credential", "field_of_study", "started_on", "ended_on", "is_public")
        widgets = {
            "started_on": forms.DateInput(attrs={"type": "date"}),
            "ended_on": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        data = super().clean()
        if data.get("started_on") and data.get("ended_on") and data["ended_on"] < data["started_on"]:
            self.add_error("ended_on", "End date cannot precede start date.")
        return data


class OrganizationRelationshipForm(forms.ModelForm):
    organization_name = forms.CharField(max_length=255, label="Organization name")
    organization_website = forms.URLField(required=False, label="Organization website")

    class Meta:
        model = OrganizationRelationship
        fields = ("role", "title", "started_on", "ended_on", "is_public")
        widgets = {
            "started_on": forms.DateInput(attrs={"type": "date"}),
            "ended_on": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["organization_name"].initial = self.instance.organization.name
            self.fields["organization_website"].initial = self.instance.organization.website

    def clean(self):
        data = super().clean()
        if data.get("started_on") and data.get("ended_on") and data["ended_on"] < data["started_on"]:
            self.add_error("ended_on", "End date cannot precede start date.")
        return data
