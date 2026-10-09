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
