"""
Lightweight in-house circuit breaker for the Claude API calls in
intelligence_pipeline.py. No new dependency — uses the same Django cache
(Redis-backed once CACHE_URL is set, LocMemCache otherwise) already wired
up for embedding/TF-IDF caching, just under different keys.

Three states, tracked per named circuit ("claude_api" is the only one used
today, but the name param allows more circuits later without another module):
- closed: normal operation, calls go through.
- open: once FAILURE_THRESHOLD consecutive failures land, every call for
  the next COOLDOWN_SECONDS is short-circuited immediately (no network
  attempt at all) — this is what stops worker threads piling up against a
  degraded upstream.
- half-open: after the cooldown elapses, exactly one trial call is let
  through. Success closes the circuit; failure re-opens it for another
  cooldown window.
"""
import time
from django.core.cache import cache

FAILURE_THRESHOLD = 5
COOLDOWN_SECONDS = 60


class CircuitOpenError(Exception):
    """Raised instead of attempting the call when the circuit is open."""
    pass


def _failure_count_key(name):
    return f"circuit_breaker:{name}:failures"


def _opened_until_key(name):
    return f"circuit_breaker:{name}:opened_until"


def is_open(name):
    opened_until = cache.get(_opened_until_key(name))
    if opened_until is None:
        return False
    if time.time() >= opened_until:
        # Cooldown elapsed — clear the open marker so the next call is a
        # half-open trial. record_failure() will re-open it if that fails.
        cache.delete(_opened_until_key(name))
        return False
    return True


def record_success(name):
    cache.delete(_failure_count_key(name))
    cache.delete(_opened_until_key(name))


def record_failure(name):
    failures = (cache.get(_failure_count_key(name)) or 0) + 1
    cache.set(_failure_count_key(name), failures, COOLDOWN_SECONDS * 10)
    if failures >= FAILURE_THRESHOLD:
        cache.set(_opened_until_key(name), time.time() + COOLDOWN_SECONDS, COOLDOWN_SECONDS + 5)


def call_with_breaker(name, func, *args, **kwargs):
    """Runs func(*args, **kwargs); raises CircuitOpenError instead of ever
    calling func if the circuit is currently open."""
    if is_open(name):
        raise CircuitOpenError(f"Circuit '{name}' is open — upstream is degraded, short-circuiting.")
    try:
        result = func(*args, **kwargs)
    except Exception:
        record_failure(name)
        raise
    record_success(name)
    return result
