"""Resource isolation and nonce-safe HTML caching on every response path."""
from django.utils.cache import patch_cache_control

from config.browser_policy import PERMISSIONS_POLICY


class BrowserPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault('Permissions-Policy', PERMISSIONS_POLICY)
        # A view may explicitly permit a public embeddable image, such as the
        # readiness badge. Downloads and private API responses remain isolated.
        response.setdefault('Cross-Origin-Resource-Policy', 'same-origin')
        if response.get('Content-Type', '').split(';', 1)[0].strip().lower() == 'text/html':
            # A cached HTML body and a newly generated CSP nonce disagree.
            # Neither shared caches nor browser caches should reuse these pages.
            patch_cache_control(response, private=True, no_store=True)
        return response
