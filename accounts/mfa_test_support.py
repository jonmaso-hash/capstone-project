"""Fixtures for unrelated tests that deliberately bypass authentication."""
from types import SimpleNamespace

import pyotp
from django.utils import timezone
from django.conf import settings

from .models import StaffMFA
from .staff_mfa import encrypt_secret, mark_verified


def grant_staff_mfa(client, user):
    credential, _ = StaffMFA.objects.get_or_create(user=user, defaults={
        'encrypted_secret': encrypt_secret(pyotp.random_base32()),
        'enabled_at': timezone.now(),
    })
    if not credential.enabled_at:
        credential.enabled_at = timezone.now()
        credential.save(update_fields=['enabled_at'])
    session = client.session
    mark_verified(SimpleNamespace(user=user, session=session), credential)
    session.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
