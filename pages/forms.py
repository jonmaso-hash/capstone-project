from django import forms

class contactForm(forms.Form):
    name = forms.CharField(max_length=50, label='Your Name')
    email = forms.EmailField()
    message = forms.CharField(widget= forms.Textarea)
    
