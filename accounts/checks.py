"""
Deploy checks for settings that fail open or fail shared rather than fail loudly.

Run by `manage.py check --deploy` (the EC2 candidate check runs it before a swap).
"""
from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.security, deploy=True)
def rate_limit_proxy_count(app_configs, **kwargs):
    """
    Production sits behind a reverse proxy (Caddy on EC2). With
    RATE_LIMIT_TRUSTED_PROXY_COUNT at 0 every per-IP limit counts the proxy
    address for every visitor, so the limits are site-wide. Set it to the
    number of proxies, or set RATE_LIMIT_NO_PROXY=True when clients connect directly.
    """
    if settings.DEBUG or settings.RATE_LIMIT_TRUSTED_PROXY_COUNT > 0 or getattr(settings, 'RATE_LIMIT_NO_PROXY', False):
        return []
    return [Warning(
        'RATE_LIMIT_TRUSTED_PROXY_COUNT is 0, so behind a reverse proxy every per-IP rate limit is shared by all visitors.',
        hint='Set RATE_LIMIT_TRUSTED_PROXY_COUNT=1 behind Caddy, or RATE_LIMIT_NO_PROXY=True if clients connect directly.',
        id='accounts.W001',
    )]
