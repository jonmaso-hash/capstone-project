from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


@deconstructible
class MaxFileSizeValidator:
    """
    Django doesn't enforce a file upload size limit by default — only PDF/PPTX
    extensions were being validated, with no cap on how large the file itself
    could be. @deconstructible makes this safe to reference from migrations,
    matching the same pattern Django's own FileExtensionValidator uses.
    """
    def __init__(self, max_mb):
        self.max_mb = max_mb
        self.max_bytes = max_mb * 1024 * 1024

    def __call__(self, value):
        if value.size > self.max_bytes:
            raise ValidationError(f"File too large. Maximum size is {self.max_mb}MB.")

    def __eq__(self, other):
        return isinstance(other, MaxFileSizeValidator) and self.max_mb == other.max_mb
