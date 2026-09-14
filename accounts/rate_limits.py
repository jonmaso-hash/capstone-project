"""
Rate limits for the entry points anyone can reach without an account: sign-in,
signup, password reset, the contact form and the waitlist.

Counts live in the database (accounts.models.RateLimitEvent), never the cache.
Production runs several web workers, each with its own in-process cache, and
a deploy would wipe it. A limit is a temporary slowdown that lifts as attempts
age out of the window, never a lockout.

Every check fails closed. If the counter can't be written or read, the attempt
is refused: a database problem must not quietly switch the limiter off.

Race-safe without locks: an attempt is recorded first and counted second, so
concurrent requests always see each other's rows and together can't pass the
limit. An attempt over the limit, or one that turns out not to count (a
successful sign-in, a signup that fails validation), removes its own row.
"""
import hashlib
import hmac
import ipaddress
import logging
import math
from datetime import timedelta

from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone

from .models import RateLimitEvent

logger = logging.getLogger(__name__)

# Locked with the owner on 2026-09-14: scope -> (attempts allowed, window).
LIMITS = {
    'login_username': (5, timedelta(minutes=15)),
    'login_ip': (30, timedelta(minutes=15)),
    'signup_ip': (5, timedelta(hours=1)),
    'password_reset_ip': (3, timedelta(hours=1)),
    'password_reset_email': (3, timedelta(hours=1)),
    'contact_ip': (5, timedelta(hours=1)),
    'waitlist_ip': (10, timedelta(hours=1)),
}

# How long rows are kept before pruning -- well past every window above.
RETENTION = timedelta(days=1)


def hash_key(scope, identifier):
    """
    A keyed hash of the identifier, so the table never holds a username, email
    or address. Case and surrounding spaces don't matter: 'Member' and
    ' member ' count together.
    """
    normalized = f"{scope}:{str(identifier or '').strip().casefold()}"
    return hmac.new(settings.SECRET_KEY.encode(), normalized.encode(), hashlib.sha256).hexdigest()


def client_ip(request):
    """
    The address an attempt counts against.

    REMOTE_ADDR, unless RATE_LIMIT_TRUSTED_PROXY_COUNT says how many proxies in
    front of the app each append one X-Forwarded-For entry. Then it is the
    entry the outermost trusted proxy appended, counting from the right;
    anything further left is whatever the client sent and is ignored. A header
    too short for that count, or an entry that isn't an address, falls back to
    REMOTE_ADDR.
    """
    remote = request.META.get('REMOTE_ADDR') or 'unknown'
    trusted = settings.RATE_LIMIT_TRUSTED_PROXY_COUNT
    if trusted <= 0:
        return remote
    entries = [entry.strip() for entry in request.META.get('HTTP_X_FORWARDED_FOR', '').split(',') if entry.strip()]
    if len(entries) < trusted:
        return remote
    candidate = entries[-trusted]
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return remote
    return candidate


def reserve(scope, identifier):
    """
    Counts one attempt. Returns a token for release() while the attempt is
    within the limit, and None when it is over the limit -- or when the
    counter can't be written or read. The caller refuses the attempt on None
    either way.
    """
    limit, window = LIMITS[scope]
    key = hash_key(scope, identifier)
    try:
        # Two atomic blocks rather than one: without an outer transaction each
        # commits on its own, so a concurrent request's count includes this row.
        with transaction.atomic():
            event = RateLimitEvent.objects.create(scope=scope, key=key)
        with transaction.atomic():
            counted = RateLimitEvent.objects.filter(
                scope=scope, key=key, created_at__gt=timezone.now() - window,
            ).count()
    except DatabaseError:
        logger.exception("Rate limit counter unavailable for %s; refusing the attempt", scope)
        return None
    if counted > limit:
        release(event.id)
        return None
    return event.id


def reserve_all(checks):
    """
    reserve() for several (scope, identifier) pairs that must all pass. Returns
    (tokens, None), or (None, the refused pair) after releasing anything
    already counted, so a refused attempt counts against nothing.
    """
    tokens = []
    for scope, identifier in checks:
        token = reserve(scope, identifier)
        if token is None:
            for taken in tokens:
                release(taken)
            return None, (scope, identifier)
        tokens.append(token)
    return tokens, None


def release(token):
    """
    Un-counts an attempt that turned out not to count. If that fails, the
    attempt simply stays counted -- the safe direction.
    """
    if token is None:
        return
    try:
        with transaction.atomic():
            RateLimitEvent.objects.filter(id=token).delete()
    except DatabaseError:
        logger.exception("Could not release rate limit attempt %s; it stays counted", token)


def clear(scope, identifier):
    """Forgets every counted attempt for one identifier, e.g. a username after it signs in."""
    try:
        with transaction.atomic():
            RateLimitEvent.objects.filter(scope=scope, key=hash_key(scope, identifier)).delete()
    except DatabaseError:
        logger.exception("Could not clear the %s rate limit; its attempts stay counted", scope)


def minutes_until_allowed(scope, identifier):
    """
    Whole minutes until the oldest attempt in the window ages out and another
    is allowed, for the message shown on refusal. None if that can't be read.
    """
    _limit, window = LIMITS[scope]
    now = timezone.now()
    try:
        oldest = (
            RateLimitEvent.objects
            .filter(scope=scope, key=hash_key(scope, identifier), created_at__gt=now - window)
            .order_by('created_at')
            .values_list('created_at', flat=True)
            .first()
        )
    except DatabaseError:
        return None
    if oldest is None:
        return None
    return max(1, math.ceil((oldest + window - now).total_seconds() / 60))


def retry_phrase(scope, identifier):
    """'in 12 minutes', 'in 1 minute', or 'in a few minutes' when the wait can't be read."""
    minutes = minutes_until_allowed(scope, identifier)
    if minutes is None:
        return "in a few minutes"
    return f"in {minutes} minute{'' if minutes == 1 else 's'}"
