"""
The shared counter behind accounts/tests_rate_limits.py.

Kept in the database, so every web worker shares one count and a deploy does
not reset it; never in the per-process cache. Fails closed: if the counter
cannot be written or read, the attempt is refused rather than let through.
Stores usernames, emails and addresses only as keyed hashes, and prunes old
rows on the beat schedule. The client address ignores X-Forwarded-For until
RATE_LIMIT_TRUSTED_PROXY_COUNT says how many proxies to trust.
"""
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import DatabaseError
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts import rate_limits
from accounts.models import RateLimitEvent
from accounts.tasks import prune_rate_limit_events

User = get_user_model()

PASSWORD = 'CorrectHorse!2026'
FAST_HASHER = ['django.contrib.auth.hashers.MD5PasswordHasher']
IP = '203.0.113.60'


class LockedLimitsTests(TestCase):

    def test_the_numbers_agreed_for_launch(self):
        self.assertEqual(rate_limits.LIMITS, {
            'login_username': (5, timedelta(minutes=15)),
            'login_ip': (30, timedelta(minutes=15)),
            'signup_ip': (5, timedelta(hours=1)),
            'password_reset_ip': (3, timedelta(hours=1)),
            'password_reset_email': (3, timedelta(hours=1)),
            'contact_ip': (5, timedelta(hours=1)),
            'waitlist_ip': (10, timedelta(hours=1)),
            # Entity Integrity checks: each new one sends ~45 requests to SEC
            # under one declared user agent, so a per-user limit protects the
            # platform and a global one protects SEC's fair-access policy.
            'identity_check_user': (10, timedelta(days=1)),
            'identity_check_global': (200, timedelta(hours=1)),
        })

    def test_each_scope_allows_exactly_its_limit(self):
        for scope, (limit, _window) in rate_limits.LIMITS.items():
            with self.subTest(scope=scope):
                for _ in range(limit):
                    self.assertIsNotNone(rate_limits.reserve(scope, 'same-identifier'))
                self.assertIsNone(rate_limits.reserve(scope, 'same-identifier'))


class DatabaseCounterTests(TestCase):

    def test_every_counted_attempt_is_a_database_row(self):
        for _ in range(3):
            rate_limits.reserve('signup_ip', IP)
        self.assertEqual(RateLimitEvent.objects.filter(scope='signup_ip').count(), 3)

    def test_the_cache_is_never_consulted(self):
        refuse = AssertionError('the rate limiter used the cache')
        with mock.patch.object(cache, 'get', side_effect=refuse), \
                mock.patch.object(cache, 'set', side_effect=refuse), \
                mock.patch.object(cache, 'add', side_effect=refuse), \
                mock.patch.object(cache, 'incr', side_effect=refuse):
            for _ in range(5):
                self.assertIsNotNone(rate_limits.reserve('signup_ip', IP))
            self.assertIsNone(rate_limits.reserve('signup_ip', IP))

    def test_a_refused_attempt_is_not_counted(self):
        for _ in range(8):
            rate_limits.reserve('signup_ip', IP)
        self.assertEqual(RateLimitEvent.objects.filter(scope='signup_ip').count(), 5)

    def test_a_released_attempt_frees_its_slot(self):
        tokens = [rate_limits.reserve('signup_ip', IP) for _ in range(5)]
        rate_limits.release(tokens[0])
        self.assertIsNotNone(rate_limits.reserve('signup_ip', IP))

    def test_clearing_forgets_only_that_identifier(self):
        for _ in range(5):
            rate_limits.reserve('login_username', 'member')
            rate_limits.reserve('login_username', 'someone-else')
        rate_limits.clear('login_username', 'member')
        self.assertIsNotNone(rate_limits.reserve('login_username', 'member'))
        self.assertIsNone(rate_limits.reserve('login_username', 'someone-else'))

    def test_attempts_older_than_the_window_stop_counting(self):
        for _ in range(5):
            rate_limits.reserve('login_username', 'member')
        RateLimitEvent.objects.update(created_at=timezone.now() - timedelta(minutes=16))
        self.assertIsNotNone(rate_limits.reserve('login_username', 'member'))

    def test_the_wait_counts_down_from_the_oldest_attempt_in_the_window(self):
        for _ in range(5):
            rate_limits.reserve('login_username', 'member')
        oldest = RateLimitEvent.objects.order_by('id').first()
        RateLimitEvent.objects.filter(id=oldest.id).update(created_at=timezone.now() - timedelta(minutes=10))
        self.assertEqual(rate_limits.minutes_until_allowed('login_username', 'member'), 5)

    def test_usernames_and_emails_count_without_regard_to_case_or_spacing(self):
        for variant in ('Member', 'MEMBER', 'member', ' member ', 'mEmBeR'):
            self.assertIsNotNone(rate_limits.reserve('login_username', variant))
        self.assertIsNone(rate_limits.reserve('login_username', 'member'))

    def test_identifiers_are_stored_only_as_keyed_hashes(self):
        rate_limits.reserve('login_username', 'Alice.Private')
        rate_limits.reserve('password_reset_email', 'alice@example.test')
        rate_limits.reserve('login_ip', IP)
        for key in RateLimitEvent.objects.values_list('key', flat=True):
            self.assertEqual(len(key), 64)
            self.assertNotIn('alice', key.lower())
            self.assertNotIn('203.0.113', key)


class FailClosedTests(TestCase):

    def test_a_counter_write_failure_refuses_the_attempt(self):
        with mock.patch.object(RateLimitEvent.objects, 'create', side_effect=DatabaseError('write failed')):
            self.assertIsNone(rate_limits.reserve('signup_ip', IP))

    def test_a_counter_read_failure_refuses_the_attempt(self):
        with mock.patch('django.db.models.query.QuerySet.count', side_effect=DatabaseError('read failed')):
            self.assertIsNone(rate_limits.reserve('signup_ip', IP))

    def test_a_release_failure_leaves_the_attempt_counted(self):
        token = rate_limits.reserve('signup_ip', IP)
        with mock.patch('django.db.models.query.QuerySet.delete', side_effect=DatabaseError('delete failed')):
            rate_limits.release(token)
        self.assertEqual(RateLimitEvent.objects.count(), 1)

    @override_settings(PASSWORD_HASHERS=FAST_HASHER)
    def test_sign_in_is_refused_when_the_counter_is_down(self):
        User.objects.create_user('fc_member', password=PASSWORD)
        client = Client()
        with mock.patch.object(RateLimitEvent.objects, 'create', side_effect=DatabaseError('write failed')):
            response = client.post(reverse('accounts:login'), {'username': 'fc_member', 'password': PASSWORD})
        self.assertEqual(response.status_code, 429)
        self.assertNotIn('_auth_user_id', client.session)

    @override_settings(PASSWORD_HASHERS=FAST_HASHER)
    def test_signup_is_refused_when_the_counter_is_down(self):
        with mock.patch.object(RateLimitEvent.objects, 'create', side_effect=DatabaseError('write failed')):
            response = Client().post(reverse('accounts:signup'), {
                'username': 'fc_signup', 'password1': PASSWORD, 'password2': PASSWORD, 'role': 'buyer',
            })
        self.assertEqual(response.status_code, 429)
        self.assertFalse(User.objects.filter(username='fc_signup').exists())

    @override_settings(DEFAULT_FROM_EMAIL='hello@interlinkfoundry.com', CONTACT_FORM_RECIPIENT='inbox@example.test')
    def test_the_contact_form_is_refused_when_the_counter_is_down(self):
        with mock.patch.object(RateLimitEvent.objects, 'create', side_effect=DatabaseError('write failed')):
            response = Client().post(reverse('pages:contact'), {
                'name': 'Ada', 'email': 'ada@visitor.test', 'company': 'Co', 'phone': '', 'message': 'Hello.',
            })
        self.assertEqual(response.status_code, 429)
        self.assertEqual(len(mail.outbox), 0)


class ClientAddressTests(TestCase):

    def _request(self, xff=None, remote='10.0.0.5'):
        extra = {'REMOTE_ADDR': remote}
        if xff is not None:
            extra['HTTP_X_FORWARDED_FOR'] = xff
        return RequestFactory().post('/', **extra)

    def test_the_default_trusts_no_forwarding_proxy(self):
        self.assertEqual(settings.RATE_LIMIT_TRUSTED_PROXY_COUNT, 0)

    @override_settings(RATE_LIMIT_TRUSTED_PROXY_COUNT=0)
    def test_the_forwarded_header_is_ignored_until_the_proxy_is_confirmed(self):
        self.assertEqual(rate_limits.client_ip(self._request(xff='198.51.100.7')), '10.0.0.5')

    @override_settings(RATE_LIMIT_TRUSTED_PROXY_COUNT=0)
    def test_a_forged_header_cannot_dodge_the_limit(self):
        for i in range(5):
            ip = rate_limits.client_ip(self._request(xff=f'198.51.100.{i}'))
            self.assertIsNotNone(rate_limits.reserve('signup_ip', ip))
        ip = rate_limits.client_ip(self._request(xff='198.51.100.250'))
        self.assertIsNone(rate_limits.reserve('signup_ip', ip))

    @override_settings(RATE_LIMIT_TRUSTED_PROXY_COUNT=1)
    def test_one_trusted_proxy_uses_the_address_it_appended(self):
        self.assertEqual(rate_limits.client_ip(self._request(xff='6.6.6.6, 198.51.100.7')), '198.51.100.7')

    @override_settings(RATE_LIMIT_TRUSTED_PROXY_COUNT=2)
    def test_two_trusted_proxies_use_the_second_address_from_the_right(self):
        self.assertEqual(rate_limits.client_ip(self._request(xff='6.6.6.6, 198.51.100.7, 192.0.2.1')), '198.51.100.7')

    @override_settings(RATE_LIMIT_TRUSTED_PROXY_COUNT=2)
    def test_a_short_or_malformed_header_falls_back_to_the_connection_address(self):
        for xff in (None, '', '198.51.100.7', 'not-an-ip, 192.0.2.1'):
            with self.subTest(xff=xff):
                self.assertEqual(rate_limits.client_ip(self._request(xff=xff)), '10.0.0.5')


class PruningTests(TestCase):

    def test_rows_past_the_retention_period_are_pruned_and_recent_ones_kept(self):
        # Aged relative to RETENTION rather than a fixed number of hours: the
        # longest window grew to a day (identity_check_user), so retention grew
        # with it, and a hard-coded 25 hours would now be inside it.
        rate_limits.reserve('signup_ip', 'old-address')
        rate_limits.reserve('signup_ip', 'recent-address')
        RateLimitEvent.objects.filter(key=rate_limits.hash_key('signup_ip', 'old-address')).update(
            created_at=timezone.now() - rate_limits.RETENTION - timedelta(hours=1))
        self.assertEqual(prune_rate_limit_events(), 1)
        self.assertEqual(list(RateLimitEvent.objects.values_list('key', flat=True)),
                         [rate_limits.hash_key('signup_ip', 'recent-address')])

    def test_pruning_is_on_the_beat_schedule(self):
        tasks = [entry['task'] for entry in settings.CELERY_BEAT_SCHEDULE.values()]
        self.assertIn('accounts.tasks.prune_rate_limit_events', tasks)
