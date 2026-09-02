from django import forms
from .models import DataRoomDocument


class DataRoomDocumentForm(forms.ModelForm):
    class Meta:
        model = DataRoomDocument
        fields = ['file', 'category', 'label', 'visibility']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Not required at the form level — the view falls back to the
        # model's default (INVESTOR_APPROVED, today's original behavior)
        # when omitted, so any existing caller that doesn't know about
        # visibility yet keeps working unchanged.
        self.fields['visibility'].required = False
