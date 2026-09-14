from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

from shared_utils.upload_limits import PROFILE_PICTURE_MAX_MB, SizeLimitedImageField


class ProfilePictureForm(forms.Form):
    """
    A JPG, PNG or WebP picture of at most 5 MB that really is one.

    The size is checked first. The field then opens the file with Pillow, which
    refuses a script or an SVG under an image name, and the decoded format must
    be allowed too, which refuses a GIF or BMP renamed to .png.
    """
    ALLOWED_FORMATS = {'JPEG', 'PNG', 'WEBP'}

    profile_picture = SizeLimitedImageField(
        max_mb=PROFILE_PICTURE_MAX_MB,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])],
    )

    def clean_profile_picture(self):
        picture = self.cleaned_data['profile_picture']
        if picture.image.format not in self.ALLOWED_FORMATS:
            raise ValidationError("Profile pictures must be JPG, PNG or WebP images.")
        return picture
