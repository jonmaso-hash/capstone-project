from django import forms
from django.core.validators import RegexValidator

class contactForm(forms.Form):
    name = forms.CharField(max_length=50, label='Your Name')
    email = forms.EmailField()
    message = forms.CharField(widget= forms.Textarea)
    company = forms.CharField(
        max_length=150,
        required=True
    )
    phone = forms.CharField(
        required=False,
        validators=[
            RegexValidator(
                regex=r'^\+?[\d\s\-()]{7,20}$',
                message="Enter a valid phone number."
            )
        ],
        widget=forms.TextInput(attrs={"type": "tel"})
    )
    
    
