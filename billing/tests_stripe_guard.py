"""
DEBUG=True plus a live Stripe key must stop the application from starting.

The local development environment held an `sk_live_` key with DEBUG on. The
only thing preventing a real Stripe call was that no price IDs were configured.
config/stripe_guard.py turns that accident into an invariant.

The unit tests pin the rule. The subprocess tests go through real settings
loading, because a correct guard function that settings.py never calls protects
nothing. That is the same untested-seam problem as the login router.
"""
import os
import subprocess
import sys

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.stripe_guard import refuse_live_stripe_key_in_debug

# Fake keys: correct prefixes only. Nothing here is a real credential.
FAKE_LIVE_SECRET = 'sk_live_' + 'x' * 24
FAKE_LIVE_RESTRICTED = 'rk_live_' + 'x' * 24
FAKE_TEST_SECRET = 'sk_test_' + 'x' * 24


class GuardRuleTests(SimpleTestCase):

    def test_live_secret_key_with_debug_is_refused(self):
        with self.assertRaises(ImproperlyConfigured):
            refuse_live_stripe_key_in_debug(True, FAKE_LIVE_SECRET)

    def test_live_restricted_key_with_debug_is_refused(self):
        with self.assertRaises(ImproperlyConfigured):
            refuse_live_stripe_key_in_debug(True, FAKE_LIVE_RESTRICTED)

    def test_test_key_with_debug_is_allowed(self):
        refuse_live_stripe_key_in_debug(True, FAKE_TEST_SECRET)

    def test_unset_key_with_debug_is_allowed(self):
        refuse_live_stripe_key_in_debug(True, '')
        refuse_live_stripe_key_in_debug(True, None)

    def test_live_key_in_production_is_allowed(self):
        """Production runs DEBUG=False with its live key. It must keep starting."""
        refuse_live_stripe_key_in_debug(False, FAKE_LIVE_SECRET)

    def test_the_error_says_how_to_fix_it(self):
        with self.assertRaises(ImproperlyConfigured) as caught:
            refuse_live_stripe_key_in_debug(True, FAKE_LIVE_SECRET)
        self.assertIn('sk_test_', str(caught.exception))


class SettingsActuallyEnforceTheGuardTests(SimpleTestCase):
    """
    Loads real settings in a fresh interpreter. The child inherits this process's
    environment, so whatever else settings needs is already present, and only
    DEBUG and STRIPE_SECRET_KEY are overridden. django-environ's read_env does
    not overwrite variables that are already set, so these values win over .env.
    """

    def _start_django(self, debug, secret_key):
        env = dict(os.environ)
        env['DEBUG'] = 'True' if debug else 'False'
        env['STRIPE_SECRET_KEY'] = secret_key
        env['DJANGO_SETTINGS_MODULE'] = 'config.settings'
        return subprocess.run(
            [sys.executable, '-c', 'import django; django.setup(); print("STARTED")'],
            cwd=str(settings.BASE_DIR), env=env,
            capture_output=True, text=True, timeout=180,
        )

    def test_settings_refuse_to_load_with_debug_and_a_live_key(self):
        result = self._start_django(True, FAKE_LIVE_SECRET)
        self.assertNotEqual(result.returncode, 0,
                            'Django started with DEBUG=True and a live Stripe key')
        self.assertIn('Refusing to start', result.stderr)
        self.assertNotIn('STARTED', result.stdout)

    def test_settings_load_with_debug_and_a_test_key(self):
        """Positive control: the refusal above comes from the guard, not a broken environment."""
        result = self._start_django(True, FAKE_TEST_SECRET)
        self.assertEqual(result.returncode, 0, result.stderr[-800:])
        self.assertIn('STARTED', result.stdout)

    def test_settings_load_in_production_mode_with_a_live_key(self):
        result = self._start_django(False, FAKE_LIVE_SECRET)
        self.assertEqual(result.returncode, 0, result.stderr[-800:])
        self.assertIn('STARTED', result.stdout)
