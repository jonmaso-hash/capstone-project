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


class RealNetworkInTests(BaseException):
    """
    A test tried to reach the network.

    DERIVED FROM BaseException, NOT Exception, and that is the whole point.
    The first version subclassed AssertionError, and
    `entity_verification.lookup_domain_creation_date` wraps its WHOIS call in a
    bare `except Exception` -- so it CAUGHT the ban, returned its polite
    "Domain lookup unavailable right now." string, and the test passed while
    having attempted a real network call. Measured, not theorised.

    A ban a provider can catch is not a ban. unittest's test executor uses a
    bare `except:`, so a BaseException subclass is still reported as a test
    error rather than aborting the run -- which is what makes this safe as well
    as correct.
    """


@contextlib.contextmanager
def allow_real_http():
    """Permit real HTTP inside this block. For transport tests only."""
    _ALLOWED.append(True)
    try:
        yield
    finally:
        _ALLOWED.pop()


def install_network_ban():
    """
    Replace HTTPAdapter.send with a refusal. Idempotent.

    Covers TWO paths, because one was missed and the gap was invisible:

      `requests`, via HTTPAdapter.send -- every HTTP provider in this codebase.
      `whois.whois`, which uses RAW SOCKETS and so never touched the first ban
      at all. A survey of the excluded suite caught it live:
      "WHOIS lookup failed for domain example.com: socket timeout at
      10.0.0.1:43". Port 43 is WHOIS.

    Still not a socket ban: the cache is Redis over TLS to a remote host, so
    banning sockets wholesale would break every test that touches the cache.
    Each outbound provider is banned at its own seam instead, and the cost of
    that choice is exactly this -- a new seam has to be added deliberately.

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
        raise RealNetworkInTests(
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

    _install_whois_ban()


def _install_whois_ban():
    """
    Ban the WHOIS lookup, which reaches the network over a raw socket and so
    was never covered by the `requests` ban.
    """
    try:
        import whois
    except ImportError:          # pragma: no cover - the package is installed
        return
    if getattr(whois, '_interlink_whois_banned', False):
        return
    original_whois = whois.whois

    def banned_whois(domain, *args, **kwargs):
        if _ALLOWED:
            return original_whois(domain, *args, **kwargs)
        raise RealNetworkInTests(
            'A test tried to make a real WHOIS lookup for %r.\n'
            'WHOIS uses a raw socket on port 43, so it is banned at its own '
            'seam rather than through requests. Mock '
            "mock.patch('zelda_api.entity_verification."
            "lookup_domain_creation_date'), or the whois call itself."
            % (domain,))

    whois.whois = banned_whois
    whois._interlink_whois_banned = True


def _install_stream_stub():
    """
    Replace Stream Chat with an inert double.

    A STUB, not a ban, and the distinction is deliberate. Stream is third-party
    chat infrastructure, not one of Zelda's evidence sources: its calls say
    nothing about a company and cannot corrupt a finding. So it is substituted
    the way the cache is substituted for locmem, rather than refused the way a
    provider is refused.

    It was found the hard way. Making the ban unswallowable turned 27 tests
    across three modules red, all of them POSTing to chat.stream-io-api.com and
    creating real users in a live Stream account on every gate run. The ban had
    been firing on them all along and something in that path was catching it --
    which is precisely what deriving from Exception allowed.

    Patched in THREE places, because `from stream_chat import StreamChat` at
    module scope binds the name into the importing module: replacing only
    `stream_chat.StreamChat` would leave the already-imported references in the
    view modules pointing at the real client.
    """
    class _InertStreamChat:
        """Records what was asked of it and reaches nothing."""

        calls = []

        def __init__(self, *args, **kwargs):
            type(self).calls.append(('__init__', args, kwargs))

        def __getattr__(self, name):
            def _recorded(*args, **kwargs):
                type(self).calls.append((name, args, kwargs))
                return {}
            return _recorded

    import stream_chat
    stream_chat.StreamChat = _InertStreamChat
    for dotted in ('accounts.views', 'matchmaking.views'):
        try:
            module = __import__(dotted, fromlist=['StreamChat'])
        except Exception:                      # pragma: no cover
            continue
        if hasattr(module, 'StreamChat'):
            module.StreamChat = _InertStreamChat
    return _InertStreamChat


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
        install_network_ban()
        _install_stream_stub()
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
