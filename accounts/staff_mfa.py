"""Staff-only MFA, independent of password/social login entry points."""
import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.views.decorators.http import require_http_methods

from . import rate_limits
from .models import StaffMFA
from .redirects import safe_destination

SESSION_KEY = 'staff_mfa_verified'
MAX_AGE = 8 * 60 * 60
ALLOWED = {'accounts:staff_mfa_setup', 'accounts:staff_mfa_verify',
           'accounts:login', 'accounts:logout', 'logout', 'account_logout'}


def cipher(key):
    material = hashlib.sha256(('interlink-staff-mfa:' + key).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(material))


def encrypt_secret(secret):
    return cipher(settings.SECRET_KEY).encrypt(secret.encode()).decode()


def decrypt_secret(value):
    for key in [settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS]:
        try:
            return cipher(key).decrypt(value.encode()).decode()
        except InvalidToken:
            continue
    raise InvalidToken('Staff MFA encryption key unavailable')


def fingerprint(credential):
    return hashlib.sha256(credential.encrypted_secret.encode()).hexdigest()


def mark_verified(request, credential):
    request.session.cycle_key()
    request.session[SESSION_KEY] = {
        'user_id': str(request.user.pk), 'credential_id': credential.pk,
        'fingerprint': fingerprint(credential), 'at': time.time(),
    }


def is_verified(request, credential):
    stamp = request.session.get(SESSION_KEY)
    if not isinstance(stamp, dict) or not credential or not credential.enabled_at:
        return False
    try:
        age = time.time() - float(stamp['at'])
        return (0 <= age < MAX_AGE and stamp['user_id'] == str(request.user.pk)
                and stamp['credential_id'] == credential.pk
                and secrets.compare_digest(stamp['fingerprint'], fingerprint(credential)))
    except (KeyError, TypeError, ValueError):
        return False


class StaffMFAMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # DRF authenticates tokens after Django middleware. A staff-owned
        # bearer token must not grant staff powers without a session factor.
        parts = request.META.get('HTTP_AUTHORIZATION', '').split()
        if len(parts) == 2:
            staff_token = False
            if parts[0].lower() == 'token':
                from rest_framework.authtoken.models import Token
                staff_token = Token.objects.filter(key=parts[1], user__is_staff=True).exists()
            elif parts[0].lower() == 'api-key':
                from matchmaking.models import APIKey
                staff_token = APIKey.objects.filter(key_hash=APIKey.digest(parts[1]), owner__is_staff=True).exists()
            if staff_token:
                return JsonResponse({'error': 'Staff must use an MFA-verified session; staff bearer tokens are not accepted.'}, status=403)
        if request.user.is_authenticated and request.user.is_staff:
            try:
                name = resolve(request.path_info).view_name
            except Resolver404:
                name = None
            if name not in ALLOWED:
                credential = StaffMFA.objects.filter(user=request.user).first()
                if not is_verified(request, credential):
                    target = reverse('accounts:staff_mfa_verify' if credential and credential.enabled_at
                                     else 'accounts:staff_mfa_setup')
                    if request.method not in {'GET', 'HEAD', 'OPTIONS'} or request.headers.get('Accept', '').startswith('application/json'):
                        return JsonResponse({'error': 'Staff MFA verification required.', 'verify_url': target}, status=403)
                    return redirect(target + '?' + urlencode({'next': request.get_full_path()}))
        return self.get_response(request)


def destination(request):
    target = safe_destination(request.POST.get('next') or request.GET.get('next'), request)
    if target and target.split('?', 1)[0] not in {reverse('accounts:staff_mfa_setup'), reverse('accounts:staff_mfa_verify'), reverse('accounts:login')}:
        return target
    return '/' + settings.ADMIN_URL_PATH


def response_page(request, **context):
    response = render(request, 'accounts/staff_mfa.html', context)
    add_never_cache_headers(response)
    response['Referrer-Policy'] = 'no-referrer'
    response['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    return response


def accepted_counter(credential, code):
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return None
    totp = pyotp.TOTP(decrypt_secret(credential.encrypted_secret))
    counter = int(time.time()) // totp.interval
    for candidate in (counter, counter - 1, counter + 1):
        if candidate > credential.last_counter and secrets.compare_digest(totp.at(candidate * totp.interval), code):
            return candidate
    return None


def reserve(request):
    return rate_limits.reserve_all([
        ('staff_mfa_user', request.user.pk),
        ('staff_mfa_ip', rate_limits.client_ip(request)),
    ])


def release(request, tokens):
    for token in tokens:
        rate_limits.release(token)
    rate_limits.clear('staff_mfa_user', request.user.pk)


@login_required
@require_http_methods(['GET', 'POST'])
def setup(request):
    if not request.user.is_staff:
        return HttpResponseForbidden('Staff only.')
    target = destination(request)
    error = None
    codes = None
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        credential, _ = StaffMFA.objects.get_or_create(user=request.user, defaults={
            'encrypted_secret': encrypt_secret(pyotp.random_base32()),
        })
        if credential.enabled_at:
            return redirect(target if is_verified(request, credential) else reverse('accounts:staff_mfa_verify') + '?' + urlencode({'next': target}))
        if request.method == 'POST':
            tokens, refused = reserve(request)
            password_valid = not request.user.has_usable_password() or request.user.check_password(request.POST.get('password', ''))
            counter = None if refused or not password_valid else accepted_counter(credential, request.POST.get('code', '').strip())
            if counter is None:
                error = 'Too many attempts. Try again in 15 minutes.' if refused else 'Invalid password or authenticator code. Try again.'
            else:
                codes = [secrets.token_hex(16) for _ in range(10)]
                credential.recovery_hashes = [hashlib.sha256(code.encode()).hexdigest() for code in codes]
                credential.enabled_at = timezone.now()
                credential.last_counter = counter
                credential.save(update_fields=['recovery_hashes', 'enabled_at', 'last_counter'])
                release(request, tokens)
                mark_verified(request, credential)
        secret = None if codes else decrypt_secret(credential.encrypted_secret)
    return response_page(request, enrolling=True, secret=secret, recovery_codes=codes, next_destination=target, error=error)


@login_required
@require_http_methods(['GET', 'POST'])
def verify(request):
    if not request.user.is_staff:
        return HttpResponseForbidden('Staff only.')
    target = destination(request)
    error = None
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        credential = StaffMFA.objects.filter(user=request.user).first()
        if not credential or not credential.enabled_at:
            return redirect(reverse('accounts:staff_mfa_setup') + '?' + urlencode({'next': target}))
        if is_verified(request, credential):
            return redirect(target)
        if request.method == 'POST':
            tokens, refused = reserve(request)
            code = request.POST.get('code', '').strip()
            digest = hashlib.sha256(code.encode()).hexdigest()
            recovery = None if refused else next((item for item in credential.recovery_hashes
                                                  if secrets.compare_digest(item, digest)), None)
            counter = None if refused or recovery else accepted_counter(credential, code)
            if counter is not None or recovery:
                if recovery:
                    credential.recovery_hashes.remove(recovery)
                else:
                    credential.last_counter = counter
                credential.save(update_fields=['last_counter', 'recovery_hashes'])
                release(request, tokens)
                mark_verified(request, credential)
                return redirect(target)
            error = 'Too many attempts. Try again in 15 minutes.' if refused else 'Invalid or already-used code. Try a fresh code or a recovery code.'
    return response_page(request, enrolling=False, next_destination=target, error=error)
