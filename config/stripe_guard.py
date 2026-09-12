"""
A development environment must never be a live Stripe client.

Found during the payment audit: the local `.env` held an `sk_live_` secret key
while `DEBUG=True`, and billing/views.py assigns that key to `stripe.api_key` at
import. The only thing keeping local dev from creating real Stripe objects was
that every STRIPE_*_PRICE_ID happened to be unset, so checkout returned early
before calling Stripe. That was containment by accident. Setting up test prices
without also swapping the key would have removed it.

This makes the unsafe combination impossible instead of unlikely: settings
refuse to load. It lives outside any Django app because it runs while settings
are still being built, before apps can be imported.

Deliberately narrow:
- Live keys are refused only when DEBUG is on. Production runs with DEBUG off
  and must keep working with its live key.
- Restricted live keys (`rk_live_`) are refused as well as secret ones; they can
  still move money.
- Test keys and an unset key are always allowed.
"""
from django.core.exceptions import ImproperlyConfigured

LIVE_KEY_PREFIXES = ('sk_live_', 'rk_live_')


def refuse_live_stripe_key_in_debug(debug, secret_key):
    """Raise ImproperlyConfigured if a live Stripe key is configured with DEBUG on."""
    if debug and (secret_key or '').startswith(LIVE_KEY_PREFIXES):
        raise ImproperlyConfigured(
            'Refusing to start: STRIPE_SECRET_KEY is a live-mode Stripe key and '
            'DEBUG is True. A development environment must not be able to create '
            'real Stripe charges, customers or subscriptions. Put a test-mode key '
            '(sk_test_...) in your local .env, and keep the live key in production '
            'configuration only, where DEBUG is False.'
        )
