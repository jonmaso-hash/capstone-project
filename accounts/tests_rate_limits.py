"""
Rate limits on sign-in, signup, password reset, the contact form and the waitlist.

None of these had a limit: a script could guess passwords, open accounts, send
reset mail and fill the contact inbox without end. The limits, locked with the
owner on 2026-09-14:

  login     5 failed / 15 min per username, 30 failed / 15 min per IP
  signup    5 accounts / hour per IP
  reset     3 requests / hour per IP, 3 / hour per email
  contact   5 messages / hour per IP
  waitlist  10 joins / hour per IP

A limit is a temporary slowdown, never a lockout: it lifts when the window
passes. These tests drive the views over HTTP; accounts/tests_rate_limit_mechanism.py
covers the shared counter itself.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ops.models import WaitlistEntry

User = get_user_model()

PASSWORD = 'CorrectHorse!2026'
FAST_HASHER = ['django.contrib.auth.hashers.MD5PasswordHasher']


def _client(ip='203.0.113.10'):
    return Client(REMOTE_ADDR=ip)


def _messages(response):
    return ' '.join(str(m) for m in response.context['messages'])


@override_settings(PASSWORD_HASHERS=FAST_HASHER)
class LoginRateLimitTests(TestCase):

    LIMIT_MESSAGE = 'Too many sign-in attempts'

    def setUp(self):
        self.user = User.objects.create_user('rl_member', password=PASSWORD)
        self.url = reverse('accounts:login')

    def _attempt(self, username='rl_member', password='wrong-guess', ip='203.0.113.10'):
        client = _client(ip)
        return client.post(self.url, {'username': username, 'password': password}), client

    def _fail(self, times, **kwargs):
        for _ in range(times):
            response, _client_used = self._attempt(**kwargs)
            self.assertEqual(response.status_code, 200)  # the ordinary wrong-password form

    def test_five_failures_then_the_next_attempt_is_slowed(self):
        self._fail(5)
        response, _ = self._attempt()
        self.assertContains(response, self.LIMIT_MESSAGE, status_code=429)

    def test_the_right_password_is_refused_during_the_slowdown(self):
        self._fail(5)
        response, client = self._attempt(password=PASSWORD)
        self.assertEqual(response.status_code, 429)
        self.assertNotIn('_auth_user_id', client.session)

    def test_the_username_limit_does_not_depend_on_the_address(self):
        for i in range(5):
            self._fail(1, ip=f'198.51.100.{i + 1}')
        response, _ = self._attempt(ip='198.51.100.99')
        self.assertEqual(response.status_code, 429)

    def test_an_unknown_username_gets_the_same_message(self):
        self._fail(5, username='nobody_here')
        response, _ = self._attempt(username='nobody_here')
        self.assertContains(response, self.LIMIT_MESSAGE, status_code=429)

    def test_thirty_failures_from_one_address_slow_every_username_there(self):
        for i in range(30):
            self._fail(1, username=f'guess{i}')
        response, client = self._attempt(password=PASSWORD)
        self.assertEqual(response.status_code, 429)
        self.assertNotIn('_auth_user_id', client.session)

    def test_another_address_is_not_slowed_by_that_limit(self):
        for i in range(30):
            self._fail(1, username=f'guess{i}')
        response, client = self._attempt(password=PASSWORD, ip='203.0.113.99')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.session['_auth_user_id'], str(self.user.pk))

    def test_a_successful_sign_in_resets_the_username_count(self):
        self._fail(4)
        response, _ = self._attempt(password=PASSWORD)
        self.assertEqual(response.status_code, 302)
        self._fail(5)
        response, _ = self._attempt()
        self.assertEqual(response.status_code, 429)

    def test_the_slowdown_lifts_when_the_window_passes(self):
        self._fail(5)
        self.assertEqual(self._attempt()[0].status_code, 429)
        later = timezone.now() + timedelta(minutes=16)
        with mock.patch('django.utils.timezone.now', return_value=later):
            response, client = self._attempt(password=PASSWORD)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.session['_auth_user_id'], str(self.user.pk))

    def test_the_count_survives_clearing_the_cache(self):
        self._fail(5)
        cache.clear()
        self.assertEqual(self._attempt()[0].status_code, 429)


@override_settings(PASSWORD_HASHERS=FAST_HASHER)
class SignupRateLimitTests(TestCase):

    def _signup(self, n, ip='203.0.113.20', valid=True):
        return _client(ip).post(reverse('accounts:signup'), {
            'username': f'rl_signup_{n}',
            'email': f'rl_signup_{n}@example.com',
            'password1': PASSWORD,
            'password2': PASSWORD if valid else 'Mismatch!2026xyz',
            'role': 'founder',
        })

    def test_five_new_accounts_per_address_then_refused(self):
        for n in range(5):
            self.assertEqual(self._signup(n).status_code, 302)
        response = self._signup(5)
        self.assertEqual(response.status_code, 429)
        self.assertIn('Too many new accounts', _messages(response))
        self.assertFalse(User.objects.filter(username='rl_signup_5').exists())

    def test_signups_that_fail_validation_do_not_use_up_the_limit(self):
        for n in range(6):
            self.assertEqual(self._signup(n, valid=False).status_code, 200)
        self.assertEqual(self._signup(99).status_code, 302)

    def test_another_address_can_still_sign_up(self):
        for n in range(5):
            self._signup(n)
        self.assertEqual(self._signup(50, ip='203.0.113.21').status_code, 302)


@override_settings(PASSWORD_HASHERS=FAST_HASHER)
class PasswordResetRateLimitTests(TestCase):

    def setUp(self):
        for i in range(4):
            User.objects.create_user(f'rl_reset_{i}', email=f'reset{i}@example.test', password=PASSWORD)
        self.url = reverse('password_reset')
        self.done = reverse('password_reset_done')

    def _request(self, email, ip='203.0.113.30'):
        return _client(ip).post(self.url, {'email': email})

    def test_three_requests_per_email_then_no_more_mail(self):
        for i in range(4):
            response = self._request('reset0@example.test', ip=f'198.51.100.{i + 1}')
            self.assertRedirects(response, self.done, fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 3)

    def test_three_requests_per_address_then_no_more_mail(self):
        for i in range(4):
            response = self._request(f'reset{i}@example.test')
            self.assertRedirects(response, self.done, fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 3)

    def test_a_refused_request_looks_exactly_like_an_accepted_one(self):
        accepted = self._request('reset0@example.test')
        for _ in range(2):
            self._request('reset0@example.test')
        refused = self._request('reset0@example.test')
        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual((refused.status_code, refused['Location']), (accepted.status_code, accepted['Location']))


@override_settings(DEFAULT_FROM_EMAIL='hello@interlinkfoundry.com', CONTACT_FORM_RECIPIENT='inbox@example.test')
class ContactFormRateLimitTests(TestCase):

    VALID = {
        'name': 'Ada Visitor', 'email': 'ada@visitor.test', 'company': 'Visitor Co',
        'phone': '', 'message': 'I would like to learn more.',
    }

    def _send(self, ip='203.0.113.40'):
        return _client(ip).post(reverse('pages:contact'), self.VALID)

    def test_five_messages_per_address_then_refused(self):
        for _ in range(5):
            self.assertEqual(self._send().status_code, 302)
        response = self._send()
        self.assertEqual(response.status_code, 429)
        self.assertIn('Too many messages', _messages(response))
        self.assertEqual(len(mail.outbox), 5)

    def test_another_address_can_still_send(self):
        for _ in range(5):
            self._send()
        self.assertEqual(self._send(ip='203.0.113.41').status_code, 302)
        self.assertEqual(len(mail.outbox), 6)


class WaitlistRateLimitTests(TestCase):

    def _join(self, n, ip='203.0.113.50'):
        return _client(ip).post(reverse('pages:waitlist'), {'email': f'wait{n}@example.test', 'name': 'W'}, follow=True)

    def test_ten_joins_per_address_then_quietly_not_saved(self):
        for n in range(10):
            self._join(n)
        self.assertEqual(WaitlistEntry.objects.count(), 10)
        response = self._join(10)
        self.assertIn("You're on the list", _messages(response))
        self.assertFalse(WaitlistEntry.objects.filter(email='wait10@example.test').exists())
        self.assertEqual(WaitlistEntry.objects.count(), 10)

    def test_another_address_can_still_join(self):
        for n in range(10):
            self._join(n)
        self._join(10, ip='203.0.113.51')
        self.assertTrue(WaitlistEntry.objects.filter(email='wait10@example.test').exists())
