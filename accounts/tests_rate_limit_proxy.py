"""
Behind a reverse proxy, per-IP rate limits must not collapse into one limit.

Found on the EC2 deployment at 7ba055c: Caddy proxies every request, so
REMOTE_ADDR is Caddy's container address, and RATE_LIMIT_TRUSTED_PROXY_COUNT
was unset (0). Every per-IP limit was therefore shared by every visitor --
five signups an hour for the whole site, three password resets, and thirty
failed logins in fifteen minutes would lock everyone out. Production's only
signup_ip event in 30 days was keyed to Caddy's address.

The fix for production is RATE_LIMIT_TRUSTED_PROXY_COUNT=1. This makes the
misconfiguration loud: a one-time warning when proxied requests arrive while
the count is 0, and a deploy check (accounts.W001).
"""
from django.core.checks import run_checks
from django.test import RequestFactory, TestCase, override_settings

from accounts import rate_limits

PROXY = '172.18.0.5'   # a reverse proxy on the Docker network
VISITORS = ['203.0.113.%d' % n for n in range(1, 7)]


def proxied(visitor):
    return RequestFactory().get('/', REMOTE_ADDR=PROXY, HTTP_X_FORWARDED_FOR=visitor)


class ProxiedClientIpTests(TestCase):
    def setUp(self):
        rate_limits._proxy_warning_logged = False

    @override_settings(RATE_LIMIT_TRUSTED_PROXY_COUNT=0)
    def test_without_the_setting_six_visitors_share_one_signup_limit(self):
        # The production failure, pinned: the sixth unrelated visitor is refused.
        self.assertEqual({rate_limits.client_ip(proxied(v)) for v in VISITORS}, {PROXY})
        refused = [rate_limits.reserve('signup_ip', rate_limits.client_ip(proxied(v))) is None for v in VISITORS]
        self.assertEqual(refused, [False] * 5 + [True])

    @override_settings(RATE_LIMIT_TRUSTED_PROXY_COUNT=1)
    def test_with_one_trusted_proxy_each_visitor_has_their_own_limit(self):
        self.assertEqual([rate_limits.client_ip(proxied(v)) for v in VISITORS], VISITORS)
        refused = [rate_limits.reserve('signup_ip', rate_limits.client_ip(proxied(v))) is None for v in VISITORS]
        self.assertEqual(refused, [False] * 6)

    @override_settings(RATE_LIMIT_TRUSTED_PROXY_COUNT=1)
    def test_a_client_cannot_choose_its_address_through_the_header(self):
        forged = RequestFactory().get('/', REMOTE_ADDR=PROXY, HTTP_X_FORWARDED_FOR='1.2.3.4, 203.0.113.9')
        self.assertEqual(rate_limits.client_ip(forged), '203.0.113.9')


class ProxyWarningTests(TestCase):
    def setUp(self):
        rate_limits._proxy_warning_logged = False

    @override_settings(RATE_LIMIT_TRUSTED_PROXY_COUNT=0)
    def test_proxied_requests_with_no_trusted_proxy_warn_once(self):
        with self.assertLogs('accounts.rate_limits', level='WARNING') as logs:
            for visitor in VISITORS:
                rate_limits.client_ip(proxied(visitor))
        self.assertEqual(len(logs.records), 1)
        self.assertIn('RATE_LIMIT_TRUSTED_PROXY_COUNT is 0', logs.output[0])

    @override_settings(RATE_LIMIT_TRUSTED_PROXY_COUNT=0)
    def test_no_warning_for_direct_clients_or_a_configured_proxy(self):
        with self.assertNoLogs('accounts.rate_limits', level='WARNING'):
            rate_limits.client_ip(RequestFactory().get('/', REMOTE_ADDR='93.184.216.34'))
            rate_limits.client_ip(RequestFactory().get('/', REMOTE_ADDR='93.184.216.34', HTTP_X_FORWARDED_FOR='198.51.100.1'))
            with self.settings(RATE_LIMIT_TRUSTED_PROXY_COUNT=1):
                rate_limits.client_ip(proxied(VISITORS[0]))


class DeployCheckTests(TestCase):
    def ids(self):
        return [m.id for m in run_checks(include_deployment_checks=True) if m.id == 'accounts.W001']

    @override_settings(DEBUG=False, RATE_LIMIT_TRUSTED_PROXY_COUNT=0, RATE_LIMIT_NO_PROXY=False)
    def test_the_deploy_check_flags_an_unset_proxy_count(self):
        self.assertEqual(self.ids(), ['accounts.W001'])

    def test_the_deploy_check_is_quiet_when_configured(self):
        for overrides in ({'DEBUG': False, 'RATE_LIMIT_TRUSTED_PROXY_COUNT': 1},
                          {'DEBUG': False, 'RATE_LIMIT_TRUSTED_PROXY_COUNT': 0, 'RATE_LIMIT_NO_PROXY': True},
                          {'DEBUG': True, 'RATE_LIMIT_TRUSTED_PROXY_COUNT': 0}):
            with self.subTest(**overrides), self.settings(**overrides):
                self.assertEqual(self.ids(), [])
