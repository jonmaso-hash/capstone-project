from django import forms

from shared_utils.upload_limits import BLOG_IMAGE_MAX_MB, SizeLimitedImageField
from .models import Article

class ArticleUploadForm(forms.ModelForm):
    image = SizeLimitedImageField(max_mb=BLOG_IMAGE_MAX_MB)

    class Meta:
        model = Article
        fields = ['company_name','title', 'body', 'image']
