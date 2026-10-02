"""
The network prohibition is enforced, not promised.

What we had was a docstring: `_external()` in two suites says "nothing reaches
the network", patches three things, and has been missing `companyenrich` since
it was added inside `collect_findings`. Nobody could tell, because a live call
and a mocked one are indistinguishable until one is slow.

What we had second was an environment variable: `full_gate.ps1` sets each
provider key to ''. In PowerShell that DELETES the variable, and
`environ.Env.read_env(BASE_DIR / '.env')` then puts the real value back. A
measured check found both keys intact at full length after the "clearing" ran.

So the guard itself is the thing under test here, and every negative is paired
with a positive control. That pairing is the point: a guard that blocked all
network traffic would pass every "nothing gets through" assertion while taking
the cache, the database and the test client down with it, and the suite would
fail far away from the cause.
"""
from unittest import mock

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from config.test_runner import RealHTTPInTests, allow_real_http, install_http_ban


class RealHTTPIsRefusedTests(SimpleTestCase):
    """
    The ban is installed by the runner. `install_http_ban()` is called here too
    so these tests mean something under a runner that has not been configured
    yet -- otherwise this file would pass vacuously on exactly the setup it
    exists to detect.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        install_http_ban()

    def test_a_plain_get_is_refused(self):
        with self.assertRaises(RealHTTPInTests):
            requests.get('https://example.invalid/whatever', timeout=1)

    def test_a_post_is_refused(self):
        with self.assertRaises(RealHTTPInTests):
            requests.post('https://example.invalid/whatever', json={}, timeout=1)

    def test_a_session_is_refused_too(self):
        """Providers hold Session objects; they share the same adapter."""
        with self.assertRaises(RealHTTPInTests):
            requests.Session().get('https://example.invalid/', timeout=1)

    def test_the_refusal_names_the_url_so_the_provider_is_obvious(self):
        with self.assertRaises(RealHTTPInTests) as caught:
            requests.get('https://api.companyenrich.com/companies/enrich', timeout=1)
        self.assertIn('api.companyenrich.com', str(caught.exception))

    def test_the_refusal_says_what_to_do_instead(self):
        with self.assertRaises(RealHTTPInTests) as caught:
            requests.get('https://example.invalid/', timeout=1)
        self.assertIn('mock', str(caught.exception).lower())


class TheGuardDoesNotBreakWhatTestsNeedTests(TestCase):
    """
    Positive controls. Without these, a guard that refused everything would
    look perfect above.
    """

    def test_the_cache_still_works(self):
        """Redis is a REMOTE TLS connection -- the reason this is not a socket ban."""
        cache.set('network_guard_probe', 'value', 10)
        self.assertEqual(cache.get('network_guard_probe'), 'value')

    def test_the_database_still_works(self):
        get_user_model().objects.create_user('network_guard_probe', password='x')
        self.assertTrue(
            get_user_model().objects.filter(username='network_guard_probe').exists())

    def test_the_test_client_still_works(self):
        self.assertIn(self.client.get('/').status_code, (200, 301, 302))


class TheProvidersCannotDialOutTests(SimpleTestCase):
    """
    Coverage of the modules that actually reach outward. Each of these was a
    live call before this change, on every test that ran `collect_findings`.

    The key is forced ON here. Testing with it absent would prove nothing: the
    provider short-circuits to UNCONFIGURED and never attempts a request, which
    is precisely the false comfort the deleted-env-var measure gave.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        install_http_ban()

    def test_companyenrich_cannot_reach_its_api(self):
        from zelda_api import companyenrich
        with mock.patch.object(companyenrich.settings, 'COMPANYENRICH_API_KEY',
                               'configured-on-purpose', create=True):
            with self.assertRaises(RealHTTPInTests):
                companyenrich._fetch('example.com')

    def test_the_sec_lookup_cannot_reach_edgar(self):
        """
        Also proves the ban SURVIVES a provider's own error handling.

        `sec_identity._get` catches `requests.exceptions.RequestException` and
        degrades politely. A ban raised as a request exception would be
        swallowed there and the violation would vanish into a graceful
        fallback -- the test would pass while the call went out. RealHTTPInTests
        is an AssertionError for exactly this reason, and this test is what
        holds it to that.
        """
        from zelda_api import sec_identity
        with self.assertRaises(RealHTTPInTests):
            sec_identity._get('https://data.sec.gov/submissions/CIK0000320193.json')

    def test_a_provider_catching_everything_still_cannot_hide_it(self):
        """The same property stated directly, independent of any provider."""
        with self.assertRaises(RealHTTPInTests):
            try:
                requests.get('https://example.invalid/', timeout=1)
            except requests.exceptions.RequestException:
                self.fail('the ban was raised as a request exception and got swallowed')


class TheEscapeHatchIsNarrowTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        install_http_ban()

    def test_inside_the_hatch_the_ban_delegates(self):
        """
        Delegation proved WITHOUT touching the internet: a closed port on
        localhost. Getting a ConnectionError rather than RealHTTPInTests is the
        evidence -- the request reached the real adapter and failed at the
        transport layer.

        Mocking HTTPAdapter.send here would be worthless, since that replaces
        the ban itself; any assertion about the mock being called would hold
        whether the hatch worked or not.
        """
        with allow_real_http():
            with self.assertRaises(requests.exceptions.ConnectionError):
                requests.get('http://127.0.0.1:1/', timeout=2)

    def test_the_ban_is_back_once_the_hatch_closes(self):
        with allow_real_http():
            pass
        with self.assertRaises(RealHTTPInTests):
            requests.get('https://example.invalid/', timeout=1)

    def test_a_raising_block_still_restores_the_ban(self):
        """A leaked permit would silently unban the rest of the run."""
        with self.assertRaises(ValueError):
            with allow_real_http():
                raise ValueError('boom')
        with self.assertRaises(RealHTTPInTests):
            requests.get('https://example.invalid/', timeout=1)


class TheCacheIsLocalDuringTestsTests(TestCase):
    """
    The configured cache is Redis on a remote host. Sharing it across runs made
    the suite depend on history: `companyenrich` caches settled outcomes for
    seven days, so when the HTTP ban first went on, 57 of 60 tests passed only
    because previous runs had cached their domains, and the 3 failures were the
    3 whose entries were missing. Those same 3 had turned a full gate red on a
    Redis timeout and then passed on a re-run minutes later.

    A shared cache also means one run can poison the next, which no amount of
    mocking inside a test file can fix.
    """

    def test_the_backend_is_locmem_not_redis(self):
        from django.conf import settings
        backend = settings.CACHES['default']['BACKEND']
        self.assertEqual(backend, 'django.core.cache.backends.locmem.LocMemCache')
        self.assertNotIn('redis', backend.lower())

    def test_a_value_written_here_is_readable_here(self):
        """Positive control: local does not mean broken."""
        cache.set('locmem_probe', {'a': 1}, 30)
        self.assertEqual(cache.get('locmem_probe'), {'a': 1})

    def test_the_cache_does_not_arrive_pre_populated(self):
        """
        The key companyenrich would use for a domain these tests never query.
        A hit here would mean the run inherited another run's answers.
        """
        self.assertIsNone(cache.get('companyenrich_v1:never-queried.example'))


class TheRunnerIsTheConfiguredOneTests(SimpleTestCase):
    """
    The guard only applies if Django is actually told to use this runner. A
    perfect runner nobody runs is the same "present but inert" shape as a field
    written nowhere or a manifest entry for a module nobody ran.
    """

    def test_settings_name_this_runner(self):
        from django.conf import settings
        self.assertEqual(settings.TEST_RUNNER, 'config.test_runner.InterlinkTestRunner')

    def test_a_fast_password_hasher_is_in_force(self):
        """
        Not a network property, but the same kind of guarantee: something the
        runner establishes that must not quietly revert.

        The production hasher is slow by design, and this suite creates a user
        per test. Measured on 78 tests: 375.8s with the production hasher,
        11.9s with this one. That 31x is why a full gate took 58 minutes and
        could not finish inside a background task's limit.
        """
        from django.conf import settings
        self.assertEqual(
            settings.PASSWORD_HASHERS,
            ['django.contrib.auth.hashers.MD5PasswordHasher'],
            'the fast test hasher is gone; a full gate will take ~30x longer')


class PasswordsStillWorkUnderTheFastHasherTests(TestCase):
    """
    Positive control, and it needs the database so it cannot live beside the
    settings assertion above. A hasher swap that broke authentication would
    make every login test fail somewhere far from the cause.
    """

    def test_the_right_password_authenticates_and_the_wrong_one_does_not(self):
        from django.contrib.auth import authenticate
        get_user_model().objects.create_user('hasher_probe', password='correct-horse')
        self.assertIsNotNone(authenticate(username='hasher_probe', password='correct-horse'))
        self.assertIsNone(authenticate(username='hasher_probe', password='wrong'))
