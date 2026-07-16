from django import forms
from .models import DataRoomDocument


class DataRoomDocumentForm(forms.ModelForm):
    class Meta:
        model = DataRoomDocument
        fields = ['file', 'category', 'label']
