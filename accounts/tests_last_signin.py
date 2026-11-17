"""
The login page's "Last used" badge (accounts/last_signin.py).

The cookie holds only the sign-in method, is Secure, HttpOnly and
SameSite=Lax, and is written only once sign-in has fully succeeded -- after
the MFA step for staff. Failed and cancelled attempts leave it alone, logout
keeps it, and every option stays on the page whatever it says.

LinkedIn is the social provider exercised end to end, through the same fake
LinkedIn session as accounts/tests_linkedin_oidc.py; nothing is contacted.
"""
import copy
import re
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

import pyotp
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts import last_signin
from accounts.models import StaffMFA
from accounts.staff_mfa import decrypt_secret
from accounts.tests_linkedin_oidc import (
    CALLBACK, HOST, LOGIN as LINKEDIN_LOGIN, FakeLinkedIn, _providers_with_test_credentials,
)

User = get_user_model()
COOKIE = last_signin.COOKIE
PASSWORD = 'LastUsed!2026xyz'
NOW = 1800000000


def _all_providers_configured():
    providers = _providers_with_test_credentials()
    for name in ('google', 'facebook'):
        providers[name]['APP'] = {**providers[name]['APP'], 'client_id': f'test-{name}-id', 'secret': 'test'}
    return providers


def _without(providers, name):
    providers = copy.deepcopy(providers)
    providers[name]['APP'] = {**providers[name]['APP'], 'client_id': ''}
    return providers


class PasswordOnlyClient(Client):
    auto_staff_mfa = False


def badges(page):
    return re.findall(r'data-last-used="([a-z]+)">Last used<', page.content.decode())


@override_settings(SOCIALACCOUNT_PROVIDERS=_all_providers_configured(),
                   ALLOWED_HOSTS=[HOST, 'testserver'])
class LastUsedBadgeTests(TestCase):
    client_class = PasswordOnlyClient

    def setUp(self):
        self.member = User.objects.create_user('last_used_member', password=PASSWORD)
        self.login = reverse('accounts:login')

    def password_login(self, password=PASSWORD, username='last_used_member'):
        return self.client.post(self.login, {'username': username, 'password': password})

    def assert_cookie(self, response, method):
        cookie = response.cookies.get(COOKIE)
        self.assertIsNotNone(cookie, f'{COOKIE} was not set')
        self.assertEqual(cookie.value, method)
        self.assertTrue(cookie['secure'])
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(int(cookie['max-age']), last_signin.MAX_AGE)

    def assert_every_option(self, page):
        html = page.content.decode()
        self.assertIn('name="username"', html)
        self.assertIn('name="password"', html)
        self.assertIn('>Log in', html)
        for path in ('/accounts/google/login/', '/accounts/facebook/login/', '/accounts/oidc/linkedin/login/'):
            self.assertIn(f'href="{path}', html)

    # -- no cookie -----------------------------------------------------------

    def test_a_browser_with_no_cookie_sees_no_badge_and_every_option(self):
        page = self.client.get(self.login)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(badges(page), [])
        self.assertNotIn('Last used', page.content.decode())
        self.assert_every_option(page)
        self.assertNotIn(COOKIE, page.cookies)

    def test_an_unknown_cookie_value_is_ignored(self):
        self.client.cookies[COOKIE] = '<script>'
        page = self.client.get(self.login)
        self.assertEqual(badges(page), [])
        self.assertNotIn('<script>"', page.content.decode())

    # -- email/password ------------------------------------------------------

    def test_password_sign_in_sets_only_the_method_then_survives_logout(self):
        response = self.password_login()
        self.assertEqual(response.status_code, 302)
        self.assert_cookie(response, 'password')
        self.assertNotIn(last_signin.PENDING, self.client.session)

        logout = self.client.post(reverse('accounts:logout'))
        self.assertEqual(logout.status_code, 302)
        self.assertNotIn(COOKIE, logout.cookies)  # not deleted or overwritten
        self.assertEqual(self.client.cookies[COOKIE].value, 'password')

        page = self.client.get(self.login)
        self.assertEqual(badges(page), ['password'])
        self.assert_every_option(page)

    def test_a_failed_password_attempt_leaves_the_cookie_alone(self):
        self.client.cookies[COOKIE] = 'linkedin'
        response = self.password_login(password='wrong-password')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(COOKIE, response.cookies)
        self.assertNotIn(last_signin.PENDING, self.client.session)
        self.assertEqual(badges(self.client.get(self.login)), ['linkedin'])

    # -- social ----------------------------------------------------------------

    def linkedin(self, query):
        """Start a LinkedIn sign-in and return LinkedIn's (fake) callback response."""
        fake = FakeLinkedIn({'sub': 'li-last-used', 'email': 'li-last-used@example.com',
                             'email_verified': True, 'given_name': 'Lee', 'family_name': 'Used'})
        patcher = mock.patch.object(DefaultSocialAccountAdapter, 'get_requests_session', return_value=fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        start = self.client.post(LINKEDIN_LOGIN, HTTP_HOST=HOST, secure=True)
        self.assertEqual(start.status_code, 302)
        state = parse_qs(urlsplit(start['Location']).query)['state'][0]
        return self.client.get(f'{CALLBACK}?state={state}&{query}', HTTP_HOST=HOST, secure=True)

    def test_social_sign_in_sets_the_provider_then_survives_logout(self):
        self.client.cookies[COOKIE] = 'password'
        response = self.linkedin('code=test-code')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.client.session.get('_auth_user_id'))
        self.assert_cookie(response, 'linkedin')

        self.client.post(reverse('accounts:logout'), HTTP_HOST=HOST, secure=True)
        page = self.client.get(self.login, HTTP_HOST=HOST, secure=True)
        self.assertEqual(badges(page), ['linkedin'])
        self.assert_every_option(page)

    def test_a_cancelled_social_attempt_leaves_the_cookie_alone(self):
        self.client.cookies[COOKIE] = 'password'
        response = self.linkedin('error=access_denied&error_description=cancelled')
        self.assertRedirects(response, reverse('socialaccount_login_cancelled'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertNotIn(COOKIE, response.cookies)
        self.assertNotIn(last_signin.PENDING, self.client.session)
        self.assertEqual(badges(self.client.get(self.login, HTTP_HOST=HOST, secure=True)), ['password'])

    def test_a_failed_social_callback_leaves_the_cookie_alone(self):
        self.client.cookies[COOKIE] = 'password'
        response = self.client.get(f'{CALLBACK}?code=test-code&state=forged', HTTP_HOST=HOST, secure=True)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertNotIn(COOKIE, response.cookies)
        self.assertEqual(self.client.cookies[COOKIE].value, 'password')

    # -- availability ----------------------------------------------------------

    def test_each_available_method_is_badged_beside_its_own_option(self):
        for method in last_signin.METHODS:
            with self.subTest(method=method):
                self.client.cookies[COOKIE] = method
                page = self.client.get(self.login)
                self.assertEqual(badges(page), [method])
                self.assert_every_option(page)

    def test_an_unavailable_provider_gets_no_badge_but_keeps_its_button(self):
        with override_settings(SOCIALACCOUNT_PROVIDERS=_without(_all_providers_configured(), 'facebook')):
            self.client.cookies[COOKIE] = 'facebook'
            page = self.client.get(self.login)
        self.assertEqual(badges(page), [])
        self.assert_every_option(page)

    # -- MFA -------------------------------------------------------------------

    def test_staff_cookie_waits_for_mfa_and_an_abandoned_mfa_step_never_sets_it(self):
        staff = User.objects.create_user('last_used_staff', password=PASSWORD, is_staff=True)
        clock = mock.patch('accounts.staff_mfa.time.time', return_value=NOW)
        clock.start()
        self.addCleanup(clock.stop)

        response = self.password_login(username=staff.username)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(COOKIE, response.cookies)
        setup = reverse('accounts:staff_mfa_setup')
        self.assertNotIn(COOKIE, self.client.get(setup).cookies)
        credential = StaffMFA.objects.get(user=staff)
        wrong = self.client.post(setup, {'code': '000000', 'password': PASSWORD})
        self.assertNotIn(COOKIE, wrong.cookies)

        # Walking away from the MFA step drops the pending method with the session.
        self.client.post(reverse('accounts:logout'))
        self.assertNotIn(COOKIE, self.client.cookies)
        self.assertNotIn(last_signin.PENDING, self.client.session)
        self.assertNotIn(COOKIE, self.client.get(self.login).cookies)

        # Signing in again and completing MFA writes it.
        self.password_login(username=staff.username)
        code = pyotp.TOTP(decrypt_secret(credential.encrypted_secret)).at(NOW)
        enrolled = self.client.post(setup, {'code': code, 'password': PASSWORD})
        self.assertEqual(enrolled.status_code, 200)
        self.assert_cookie(enrolled, 'password')
        self.assertNotIn(last_signin.PENDING, self.client.session)

    def test_an_enrolled_staff_member_gets_the_cookie_only_after_verifying(self):
        staff = User.objects.create_user('last_used_verify', password=PASSWORD, is_staff=True)
        from accounts.staff_mfa import encrypt_secret
        from django.utils import timezone
        secret = pyotp.random_base32()
        StaffMFA.objects.create(user=staff, encrypted_secret=encrypt_secret(secret), enabled_at=timezone.now())
        clock = mock.patch('accounts.staff_mfa.time.time', return_value=NOW)
        clock.start()
        self.addCleanup(clock.stop)

        self.assertNotIn(COOKIE, self.password_login(username=staff.username).cookies)
        verify = reverse('accounts:staff_mfa_verify')
        self.assertNotIn(COOKIE, self.client.post(verify, {'code': '000000'}).cookies)
        response = self.client.post(verify, {'code': pyotp.TOTP(secret).at(NOW)})
        self.assertEqual(response.status_code, 302)
        self.assert_cookie(response, 'password')
