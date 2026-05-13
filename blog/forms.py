from django import forms
from .models import Article

class ArticleUploadForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['company_name','title', 'body', 'image']