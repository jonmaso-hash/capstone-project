from django import forms
from .models import DataRoomDocument, ExternalDealRoom


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


class ExternalDealRoomForm(forms.ModelForm):
    """
    Link only. There is no file field to add here later without also adding one
    to the model, which is the point -- see ExternalDealRoom's docstring.

    URLField already rejects anything that is not a URL; the extra check is the
    scheme, because an http:// data room sends whatever credential is in the
    link across the wire in clear text.
    """

    class Meta:
        model = ExternalDealRoom
        fields = ['title', 'provider', 'external_url', 'description', 'access_instructions']

    def clean_external_url(self):
        url = (self.cleaned_data.get('external_url') or '').strip()
        if not url.lower().startswith('https://'):
            raise forms.ValidationError(
                'Use the full https:// address. A plain http:// link exposes the room '
                'address in transit.'
            )
        return url
