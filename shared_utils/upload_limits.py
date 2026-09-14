"""
Upload size limits, enforced before anything reads the request body.

Django's CSRF check and DRF's session authentication both read request.POST
before a view runs, and IdempotencyMiddleware reads it for every POST. Reading
it parses the whole multipart body into a temporary file, so a size check inside
a view only happens after the upload has been accepted. UploadSizeLimitMiddleware
sits ahead of all of that and refuses the request from its Content-Length header.

The header also counts the other form fields and the multipart boundaries, so it
is compared against the file limit plus MULTIPART_ALLOWANCE_BYTES. Each view then
checks the file's exact size before doing anything else with it.
"""
from django import forms
from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import Resolver404, resolve
from django.utils.http import url_has_allowed_host_and_scheme

from matchmaking.validators import MaxFileSizeValidator

MB = 1024 * 1024
MULTIPART_ALLOWANCE_BYTES = 256 * 1024

PROFILE_PICTURE_MAX_MB = 5
BLOG_IMAGE_MAX_MB = 5
RESUME_MAX_MB = 10
PITCH_ANALYSIS_MAX_MB = 25  # the same limit as pitch decks on profiles and in the deal room

# URL name -> the largest file that endpoint accepts.
UPLOAD_LIMITS_MB = {
    'usersettings:update_profile_picture': PROFILE_PICTURE_MAX_MB,
    'blog:blog_view': BLOG_IMAGE_MAX_MB,
    'blog:edit_article': BLOG_IMAGE_MAX_MB,
    'jobs:apply': RESUME_MAX_MB,
    'zelda_api:pitch_analysis': PITCH_ANALYSIS_MAX_MB,
}


class SizeLimitedImageField(forms.ImageField):
    """An ImageField that checks the file's size before Pillow opens it."""

    def __init__(self, *, max_mb, **kwargs):
        self.max_size = MaxFileSizeValidator(max_mb=max_mb)
        super().__init__(**kwargs)

    def to_python(self, data):
        if data not in self.empty_values and hasattr(data, 'size'):
            self.max_size(data)
        return super().to_python(data)


class UploadSizeLimitMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST':
            limit_mb = _limit_for(request.path_info)
            if limit_mb is not None and _content_length(request) > limit_mb * MB + MULTIPART_ALLOWANCE_BYTES:
                return _refuse(request, limit_mb)
        return self.get_response(request)


def _limit_for(path):
    try:
        return UPLOAD_LIMITS_MB.get(resolve(path).view_name)
    except Resolver404:
        return None


def _content_length(request):
    try:
        return int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError:
        return 0


def _refuse(request, limit_mb):
    message = f"That file is too large. The limit is {limit_mb} MB."
    if request.path_info.startswith('/api/'):
        return JsonResponse({'error': message}, status=413)

    # A form post: back to the page it came from, with the reason shown there.
    messages.error(request, message)
    page = request.META.get('HTTP_REFERER', '')
    if not url_has_allowed_host_and_scheme(page, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        page = '/'
    return HttpResponseRedirect(page)
