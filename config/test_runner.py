"""
The project test runner. No test reaches the network.

This was a promise in a docstring before it was a mechanism, and the promise
was false for months without anyone being able to tell -- a live call looks
exactly like a mocked one until it is slow or flaky.

`pages/tests_entity_identity_check.py::_external()` says "nothing reaches the
network" and patches `fetch_public_page`, the WHOIS lookup and `sec_findings`.
It does not patch `companyenrich`, which was added underneath it later, inside
`collect_findings`. Every one of those 44 tests has been calling an external
API ever since. The visible symptoms were 16 tests taking 318 seconds and a
full gate turning red on a Redis timeout; the cause took a traceback to find.

CLEARING ENVIRONMENT VARIABLES DOES NOT WORK, which is worth recording because
it looks like it should. `full_gate.ps1` sets each provider key to '' before
running, and in PowerShell assigning '' DELETES the variable rather than
emptying it. `config/settings.py` then calls
`environ.Env.read_env(BASE_DIR / '.env')`, whose setdefault semantics repopulate
anything absent -- so the key comes straight back from the file, at full length.
A containment measure that reads correctly and does nothing is worse than none.

WHY `requests` AND NOT SOCKETS. Banning non-local sockets (the pytest-socket
approach) is more thorough and wrong here: the cache is Redis over TLS to a
REMOTE host, so that ban breaks every test that touches the cache, including the
ones this protects. Every outbound provider in this codebase goes through
`requests`; redis-py and psycopg do not. `HTTPAdapter.send` is therefore the
chokepoint that covers exactly what must never be live and nothing that must
keep working.

The escape hatch is deliberately narrow and currently unused. It exists so that
a future contract test against a real endpoint has a sanctioned way through,
rather than a reason to weaken the guard.
"""
import contextlib

from django.test.runner import DiscoverRunner

# A stack rather than a flag, so nesting cannot leave the ban switched off.
_ALLOWED = []


class RealHTTPInTests(AssertionError):
    """A test tried to make a real HTTP request."""


@contextlib.contextmanager
def allow_real_http():
    """Permit real HTTP inside this block. For transport tests only."""
    _ALLOWED.append(True)
    try:
        yield
    finally:
        _ALLOWED.pop()


def install_http_ban():
    """
    Replace HTTPAdapter.send with a refusal. Idempotent.

    Idempotence matters: the runner installs it once, but a test that imports
    this module must not be able to wrap the refusal in another refusal and
    change the error anyone sees.
    """
    from requests.adapters import HTTPAdapter

    if getattr(HTTPAdapter, '_interlink_http_banned', False):
        return
    original_send = HTTPAdapter.send

    def send(self, request, *args, **kwargs):
        if _ALLOWED:
            return original_send(self, request, *args, **kwargs)
        raise RealHTTPInTests(
            'A test tried to make a real HTTP request:\n'
            '    %s %s\n'
            'Tests must not reach the network: it makes them slow, flaky, '
            'dependent on someone else\'s uptime, and -- for a metered '
            'provider -- expensive. Mock the provider at its own seam (for '
            'example mock.patch(\'zelda_api.companyenrich._fetch\')), or wrap '
            'the call in config.test_runner.allow_real_http() if the test is '
            'specifically about transport.'
            % (request.method, request.url))

    HTTPAdapter.send = send
    HTTPAdapter._interlink_http_banned = True


class InterlinkTestRunner(DiscoverRunner):
    """
    DiscoverRunner, plus two kinds of isolation.

    THE HTTP BAN, above.

    A LOCAL CACHE, because the configured cache is Redis on a REMOTE host and
    sharing it between runs made the suite depend on history rather than on
    code. `companyenrich._lookup` caches settled outcomes for seven days, so
    when this guard was first switched on, 57 of 60 tests passed purely because
    earlier runs had already cached their domains, and the 3 that failed were
    the 3 whose entries were missing. Those are the same 3 that turned a full
    gate red on a Redis timeout, and the same 3 that passed when the module was
    re-run alone minutes later -- because the failed run had by then cached
    them. A suite whose result depends on what is in a shared cache is not
    measuring the code.

    Swapping to locmem makes each run start empty and identical, removes a
    remote round-trip from every cache call, and keeps the cache API working so
    the tests that legitimately use it are unaffected.
    """

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        install_http_ban()
        from django.test.utils import override_settings
        self._local_cache = override_settings(CACHES={
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'LOCATION': 'interlink-test-cache',
            },
        })
        self._local_cache.enable()
        # A fast password hasher. The production hasher is deliberately slow --
        # that is its job -- and this suite creates a user per test, so the cost
        # lands on all ~2,000 of them. Measured on the same 78 tests:
        #
        #     production hasher   375.8s
        #     MD5                  11.9s
        #
        # a 31x difference, same tests, all passing. This is the reason a full
        # gate took 58 minutes, which in turn is why it could not run inside a
        # background task's time limit. Production hashing is unaffected:
        # PASSWORD_HASHERS is overridden for the duration of the test run only.
        self._fast_hashers = override_settings(
            PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
        self._fast_hashers.enable()

    def teardown_test_environment(self, **kwargs):
        for name in ('_fast_hashers', '_local_cache'):
            override = getattr(self, name, None)
            if override is not None:
                override.disable()
        super().teardown_test_environment(**kwargs)
