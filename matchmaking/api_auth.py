# matchmaking/api_auth.py
"""
Enterprise API tier authentication — external firms authenticate with an
`Authorization: Api-Key <key>` header instead of a session cookie or the
internal DRF token scheme. Kept separate from the site's own
SessionAuthentication/TokenAuthentication so internal and external API
consumers are clearly distinct.
"""
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.throttling import SimpleRateThrottle
from .models import APIKey


class APIKeyAuthentication(BaseAuthentication):
    keyword = 'Api-Key'

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith(f'{self.keyword} '):
            return None

        key_value = auth_header[len(self.keyword) + 1:].strip()
        try:
            api_key = APIKey.objects.select_related('owner').get(key=key_value, is_active=True)
        except APIKey.DoesNotExist:
            raise AuthenticationFailed('Invalid or inactive API key.')

        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=['last_used_at'])

        return (api_key.owner, api_key)


class APIKeyRateThrottle(SimpleRateThrottle):
    scope = 'enterprise_api'

    def get_cache_key(self, request, view):
        auth = getattr(request, 'auth', None)
        if not isinstance(auth, APIKey):
            return None  # not an API-key request — nothing for this throttle to do
        return self.cache_format % {'scope': self.scope, 'ident': auth.key}
