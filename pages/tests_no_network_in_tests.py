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

from config.test_runner import RealNetworkInTests, allow_real_http, install_network_ban


class RealHTTPIsRefusedTests(SimpleTestCase):
    """
    The ban is installed by the runner. `install_network_ban()` is called here too
    so these tests mean something under a runner that has not been configured
    yet -- otherwise this file would pass vacuously on exactly the setup it
    exists to detect.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        install_network_ban()

    def test_a_plain_get_is_refused(self):
        with self.assertRaises(RealNetworkInTests):
            requests.get('https://example.invalid/whatever', timeout=1)

    def test_a_post_is_refused(self):
        with self.assertRaises(RealNetworkInTests):
            requests.post('https://example.invalid/whatever', json={}, timeout=1)

    def test_a_session_is_refused_too(self):
        """Providers hold Session objects; they share the same adapter."""
        with self.assertRaises(RealNetworkInTests):
            requests.Session().get('https://example.invalid/', timeout=1)

    def test_the_refusal_names_the_url_so_the_provider_is_obvious(self):
        with self.assertRaises(RealNetworkInTests) as caught:
            requests.get('https://api.companyenrich.com/companies/enrich', timeout=1)
        self.assertIn('api.companyenrich.com', str(caught.exception))

    def test_the_refusal_says_what_to_do_instead(self):
        with self.assertRaises(RealNetworkInTests) as caught:
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
        install_network_ban()

    def test_companyenrich_cannot_reach_its_api(self):
        from zelda_api import companyenrich
        with mock.patch.object(companyenrich.settings, 'COMPANYENRICH_API_KEY',
                               'configured-on-purpose', create=True):
            with self.assertRaises(RealNetworkInTests):
                companyenrich._fetch('example.com')

    def test_the_sec_lookup_cannot_reach_edgar(self):
        """
        Also proves the ban SURVIVES a provider's own error handling.

        `sec_identity._get` catches `requests.exceptions.RequestException` and
        degrades politely. A ban raised as a request exception would be
        swallowed there and the violation would vanish into a graceful
        fallback -- the test would pass while the call went out.
        RealNetworkInTests derives from BaseException for exactly this reason,
        and this test is what holds it to that.
        """
        from zelda_api import sec_identity
        with self.assertRaises(RealNetworkInTests):
            sec_identity._get('https://data.sec.gov/submissions/CIK0000320193.json')

    def test_a_narrow_except_cannot_hide_it(self):
        """
        Renamed, because the old name -- "a provider catching everything still
        cannot hide it" -- described something this body never did. It catches
        `requests.exceptions.RequestException` only, which is narrow. The real
        claim is tested below, against a provider that genuinely catches
        Exception.
        """
        with self.assertRaises(RealNetworkInTests):
            try:
                requests.get('https://example.invalid/', timeout=1)
            except requests.exceptions.RequestException:
                self.fail('the ban was raised as a request exception and got swallowed')

    def test_a_bare_except_exception_cannot_hide_it(self):
        """
        The claim the old test name made and did not keep.

        `except Exception` is what the first version of the ban actually died
        on: it subclassed AssertionError, so a provider wrapping its call in
        `except Exception` caught the ban, degraded politely, and the test
        passed having tried to reach the network. Deriving from BaseException
        is what fixes it, and this is the test that holds it there.
        """
        with self.assertRaises(RealNetworkInTests):
            try:
                requests.get('https://example.invalid/', timeout=1)
            except Exception:                      # noqa: BLE001 - the point
                self.fail('a bare `except Exception` swallowed the network ban')

    def test_the_ban_is_not_an_exception_subclass(self):
        """
        Stated structurally too, so the property survives someone "tidying"
        the base class back to AssertionError for consistency with other
        test helpers.
        """
        self.assertTrue(issubclass(RealNetworkInTests, BaseException))
        self.assertFalse(issubclass(RealNetworkInTests, Exception))


class WhoisIsBannedAtItsOwnSeamTests(SimpleTestCase):
    """
    WHOIS reaches the network over a raw socket on port 43, so the `requests`
    ban never saw it. A survey of the excluded zelda_api suite caught it live:
    "WHOIS lookup failed for domain example.com: socket timeout at 10.0.0.1:43".

    This is the cost of banning each provider at its own seam rather than
    banning sockets -- a choice forced by the cache being Redis over TLS to a
    remote host. The cost is that a new seam must be added deliberately, and
    this test is what makes a missing one visible.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        install_network_ban()

    def test_a_direct_whois_call_is_refused(self):
        import whois
        with self.assertRaises(RealNetworkInTests):
            whois.whois('example.com')

    def test_the_providers_whois_path_is_refused_rather_than_degraded(self):
        """
        The end-to-end case. Before this, the provider's `except Exception`
        turned the ban into "Domain lookup unavailable right now." and the test
        reported success.
        """
        from zelda_api.entity_verification import lookup_domain_creation_date
        with self.assertRaises(RealNetworkInTests):
            lookup_domain_creation_date('example.com')

    def test_the_refusal_names_the_domain_and_the_seam(self):
        import whois
        with self.assertRaises(RealNetworkInTests) as caught:
            whois.whois('northwind-grid.example')
        message = str(caught.exception)
        self.assertIn('northwind-grid.example', message)
        self.assertIn('WHOIS', message)

    def test_the_whois_ban_consults_the_same_escape_hatch_as_http(self):
        """
        Checked structurally, because the honest behavioural test would have to
        let a real WHOIS lookup out to observe delegation -- and the first
        version of this test dodged that by asserting `mock.patch` had worked,
        which proves nothing about the hatch.

        Both bans gate on the same `_ALLOWED` stack, so the hatch's behaviour
        is already covered by the HTTP delegation test; what matters here is
        that WHOIS reads the same gate rather than ignoring it.
        """
        import inspect
        from config import test_runner

        source = inspect.getsource(test_runner._install_whois_ban)
        self.assertGreater(len(source), 200, 'positive control: source was read')
        self.assertIn('_ALLOWED', source)

    def test_the_hatch_is_empty_outside_and_filled_inside(self):
        """The shared gate both bans read, asserted directly."""
        from config import test_runner
        self.assertEqual(test_runner._ALLOWED, [])
        with allow_real_http():
            self.assertNotEqual(test_runner._ALLOWED, [])
        self.assertEqual(test_runner._ALLOWED, [])


class TheEscapeHatchIsNarrowTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        install_network_ban()

    def test_inside_the_hatch_the_ban_delegates(self):
        """
        Delegation proved WITHOUT touching the internet: a closed port on
        localhost. Getting a ConnectionError rather than RealNetworkInTests is the
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
        with self.assertRaises(RealNetworkInTests):
            requests.get('https://example.invalid/', timeout=1)

    def test_a_raising_block_still_restores_the_ban(self):
        """A leaked permit would silently unban the rest of the run."""
        with self.assertRaises(ValueError):
            with allow_real_http():
                raise ValueError('boom')
        with self.assertRaises(RealNetworkInTests):
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


class HuggingFaceIsOfflineDuringTestsTests(SimpleTestCase):
    """
    The one provider the ban cannot cover. `huggingface_hub` catches broadly to
    fall back on its local cache, so a refused request never becomes a test
    failure -- it becomes a slow, non-deterministic model resolution instead.
    The previous PR recorded huggingface.co as still being contacted for
    exactly that reason.

    It matters beyond tidiness: the zelda_api rehab is measuring peak memory,
    and model-resolution behaviour would land inside `peak - start` and
    contaminate the comparison between isolated and cumulative runs.
    """

    def test_the_offline_switches_are_set(self):
        import os
        for name in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_DATASETS_OFFLINE'):
            with self.subTest(variable=name):
                self.assertEqual(os.environ.get(name), '1')

    def test_ci_puts_the_model_on_disk_since_the_runner_forbids_fetching_it(self):
        """
        The guard for the failure that actually happened, which a local gate
        cannot otherwise catch.

        Forcing offline mode broke CI and not this machine, because the weights
        are cached here and were not there. `EmbeddingSemanticOrderingTests`
        deliberately uses a real model -- a mocked embedding would make a
        semantic-ordering assertion meaningless -- so offline mode without a
        cached model gives it 0.0 similarity scores and five failures.

        Two halves that must stay together: the runner forbids fetching, so CI
        must fetch beforehand. Removing either one alone is the bug, and this
        fails locally if anyone does.
        """
        import io
        from pathlib import Path

        import yaml
        from django.conf import settings

        workflow = yaml.safe_load(
            io.open(Path(settings.BASE_DIR) / '.github' / 'workflows' / 'ci.yml',
                    encoding='utf-8').read())
        for job in ('check', 'zelda-api-tests'):
            spec = workflow['jobs'][job]
            steps = spec['steps']
            self.assertGreater(len(steps), 2, 'positive control: %s has steps' % job)

            # The producer and the consumer must agree on ONE location. An
            # earlier version of this test looked for the literal string
            # 'huggingface' in the cache path, which broke the moment the path
            # became an HF_HOME reference -- it was checking a spelling, not the
            # property. The property is: the job declares HF_HOME, and the thing
            # it caches is that same location.
            hf_home = (spec.get('env') or {}).get('HF_HOME')
            fetches = [s for s in steps
                       if 'sentence_transformers' in str(s.get('run', ''))]
            caches = [s for s in steps if 'cache' in str(s.get('uses', ''))]
            cached_paths = [str(s.get('with', {}).get('path', '')) for s in caches]

            with self.subTest(job=job):
                self.assertTrue(
                    hf_home,
                    '%s does not declare HF_HOME, so the preload step and the '
                    'test step rely on the default cache location happening to '
                    'coincide. It does today; it is not a contract.' % job)
                self.assertTrue(
                    fetches,
                    'The test runner forces HF offline, so %s must put the '
                    'embedding model on disk before running tests. Without it, '
                    'EmbeddingSemanticOrderingTests gets 0.0 similarity scores '
                    'and fails -- which is how PR #124 broke.' % job)
                self.assertTrue(
                    any('HF_HOME' in p or 'huggingface' in p for p in cached_paths),
                    '%s fetches the model but caches nothing at HF_HOME, so '
                    'every run downloads it again and depends on '
                    'huggingface.co being up. Cached paths: %r'
                    % (job, cached_paths))
                self.assertTrue(
                    any('revision=' in str(s.get('run', '')) for s in fetches),
                    '%s fetches the model without pinning a revision, so '
                    'upstream reweighting can move the semantic assertions '
                    'underneath the suite.' % job)
                self.assertTrue(
                    any('EMBEDDING_REVISION' in str(s.get('run', ''))
                        for s in fetches),
                    '%s names a revision of its own rather than deriving it '
                    'from ai_utils.EMBEDDING_REVISION. That disagreement IS '
                    'the bug that broke the build: CI fetched a SHA while the '
                    'loader asked for `main`, and a SHA fetch writes no '
                    'refs/main for an offline lookup to resolve.' % job)

    def test_the_model_identity_lives_in_one_place(self):
        """
        The loader must pin the same revision CI preloads. A pin the consumer
        ignores protects nothing -- and worse, it breaks the offline path,
        because fetching by SHA writes snapshots/<sha> and no refs/main.
        """
        import io
        from pathlib import Path

        from django.conf import settings
        from matchmaking.services.ai_utils import EMBEDDING_MODEL, EMBEDDING_REVISION

        self.assertTrue(EMBEDDING_MODEL and EMBEDDING_REVISION)
        self.assertEqual(len(EMBEDDING_REVISION), 40,
                         'a revision should be a full commit SHA')

        # And the workflow must not carry its own copy of it.
        workflow_text = io.open(
            Path(settings.BASE_DIR) / '.github' / 'workflows' / 'ci.yml',
            encoding='utf-8').read()
        self.assertGreater(len(workflow_text), 500, 'positive control')
        self.assertEqual(
            workflow_text.count(EMBEDDING_REVISION), 0,
            'ci.yml hardcodes the revision instead of importing it from '
            'ai_utils, which is how the two sides drifted apart.')

    def test_the_runner_is_what_sets_them(self):
        """
        Not a shell or a developer's environment. A property that depends on
        how the suite was launched is not a property of the suite.
        """
        import inspect
        from config import test_runner
        source = inspect.getsource(test_runner._force_huggingface_offline)
        self.assertGreater(len(source), 200, 'positive control: source was read')
        self.assertIn('HF_HUB_OFFLINE', source)


class TheBanIsDescribedAccuratelyTests(SimpleTestCase):
    """
    A consistency guard, reusing the pattern that caught the stale
    `registry_source` docstring: check the prose against the value it
    describes, rather than banning a phrase.

    This file described the ban as the wrong base class, in the present tense,
    after the class had been changed to BaseException. The claim was not merely
    stale: it asserted the opposite of the fix, and would have led the next
    reader to "correct" the base class back.

    The claim is deliberately NOT quoted here. This file is one of the files
    the guard scans, so writing the banned phrase out -- even inside a
    docstring explaining it -- makes the guard fail on itself. It did, twice:
    once as a test literal and once as a quotation in this docstring.
    """

    def test_no_file_claims_the_ban_is_an_assertionerror(self):
        import io
        from pathlib import Path
        from django.conf import settings

        # The needles are ASSEMBLED, never written out, because this file is one
        # of the files being scanned -- a literal would match the guard's own
        # source and fail on itself. The first version did exactly that.
        wrong = 'AssertionError'
        claims = ('is an ' + wrong, 'RealNetworkInTests(' + wrong + ')')

        for relative in ('config/test_runner.py', 'pages/tests_no_network_in_tests.py'):
            text = io.open(Path(settings.BASE_DIR) / relative, encoding='utf-8').read()
            self.assertGreater(len(text), 500, 'positive control: %s was read' % relative)
            # "subclassed AssertionError" and "back to AssertionError" are
            # historical narration and stay; a present-tense claim does not.
            for claim in claims:
                with self.subTest(file=relative, claim=claim):
                    self.assertEqual(
                        text.count(claim), 0,
                        '%s says the ban %r, but it derives from BaseException. '
                        'That claim is not merely stale -- it asserts the '
                        'opposite of the fix, and would lead the next reader to '
                        '"correct" the base class back.' % (relative, claim))

    def test_the_base_class_is_what_the_prose_says(self):
        self.assertTrue(issubclass(RealNetworkInTests, BaseException))
        self.assertFalse(issubclass(RealNetworkInTests, Exception))


class StreamChatIsInertDuringTestsTests(SimpleTestCase):
    """
    Found by making the ban unswallowable: 27 tests across three modules were
    POSTing to chat.stream-io-api.com and creating real users in a live Stream
    account on every gate run. The ban had been firing on them the whole time
    and something in that path was catching it -- which is exactly what
    subclassing Exception permitted.

    A STUB rather than a ban, because Stream is third-party chat
    infrastructure and not one of Zelda's evidence sources: its calls say
    nothing about a company and cannot corrupt a finding. Substituted the way
    the cache is substituted for locmem.
    """

    def test_the_view_modules_hold_the_inert_double_not_the_real_client(self):
        """
        Checked in the VIEW modules, not in `stream_chat`. Both do
        `from stream_chat import StreamChat` at module scope, which binds the
        name at import time -- so replacing only the package attribute would
        leave these pointing at the real client.
        """
        from accounts import views as accounts_views
        from matchmaking import views as matchmaking_views
        for module in (accounts_views, matchmaking_views):
            with self.subTest(module=module.__name__):
                self.assertEqual(module.StreamChat.__name__, '_InertStreamChat')

    def test_using_it_records_the_call_and_reaches_nothing(self):
        from matchmaking import views as matchmaking_views
        client = matchmaking_views.StreamChat(api_key='k', api_secret='s')
        before = len(type(client).calls)
        client.upsert_user({'id': 'someone'})
        self.assertGreater(len(type(client).calls), before)

    def test_the_real_client_still_exists(self):
        """
        Positive control. If `stream_chat` stopped importing, the stub would
        still be in place and every test above would pass while the production
        import was broken.
        """
        import importlib
        self.assertIsNotNone(importlib.import_module('stream_chat'))


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
