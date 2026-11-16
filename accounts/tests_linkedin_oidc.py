"""
LinkedIn sign-in runs on OpenID Connect (allauth's openid_connect provider,
provider_id "linkedin"), not the legacy linkedin_oauth2 provider, whose
r_liteprofile/r_emailaddress scopes LinkedIn retired for new apps.

LinkedIn is never contacted: a fake requests session stands in for its
discovery document, token endpoint and userinfo endpoint, and records what
was sent. The client id and secret below are test values only.
"""
import copy
import json
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from accounts.tests_social_auth_surface import _directives

User = get_user_model()

HOST = 'interlinkfoundry.com'
LOGIN = '/accounts/oidc/linkedin/login/'
CALLBACK = f'https://{HOST}/accounts/oidc/linkedin/login/callback/'
LINKEDIN = 'https://www.linkedin.com'
DISCOVERY = 'https://www.linkedin.com/oauth/.well-known/openid-configuration'
OPENID_CONFIG = {
    'issuer': 'https://www.linkedin.com/oauth',
    'authorization_endpoint': 'https://www.linkedin.com/oauth/v2/authorization',
    'token_endpoint': 'https://www.linkedin.com/oauth/v2/accessToken',
    'userinfo_endpoint': 'https://api.linkedin.com/v2/userinfo',
    'jwks_uri': 'https://www.linkedin.com/oauth/openid/jwks',
    'token_endpoint_auth_methods_supported': ['client_secret_post'],
}
TEST_CLIENT_ID = 'test-linkedin-client-id'
TEST_SECRET = 'test-linkedin-secret'


def _providers_with_test_credentials():
    providers = copy.deepcopy(settings.SOCIALACCOUNT_PROVIDERS)
    app = providers['openid_connect']['APPS'][0]
    app['client_id'], app['secret'] = TEST_CLIENT_ID, TEST_SECRET
    return providers


class _Response:
    def __init__(self, payload, status=200):
        self.status_code, self._payload = status, payload
        self.text = json.dumps(payload)
        self.content = self.text.encode()
        self.headers = {'content-type': 'application/json'}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeLinkedIn:
    """A requests session that answers as LinkedIn would and records each call."""

    def __init__(self, userinfo):
        self.userinfo, self.calls = userinfo, []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, headers=None, **kwargs):
        self.calls.append(('GET', url, None, headers))
        if url == DISCOVERY:
            return _Response(OPENID_CONFIG)
        if url == OPENID_CONFIG['userinfo_endpoint']:
            return _Response(self.userinfo)
        raise AssertionError(f'unexpected GET {url}')

    def request(self, method, url, params=None, data=None, headers=None, auth=None, **kwargs):
        self.calls.append((method, url, data, {'auth': auth}))
        if url == OPENID_CONFIG['token_endpoint']:
            return _Response({'access_token': 'test-access-token', 'expires_in': 3600})
        raise AssertionError(f'unexpected {method} {url}')


@override_settings(SOCIALACCOUNT_PROVIDERS=_providers_with_test_credentials(),
                   ALLOWED_HOSTS=[HOST, 'testserver'])
class LinkedInOpenIDConnectTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def linkedin(self, userinfo):
        fake = FakeLinkedIn(userinfo)
        patcher = mock.patch.object(DefaultSocialAccountAdapter, 'get_requests_session', return_value=fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake

    def start(self):
        page = self.client.get(LOGIN, HTTP_HOST=HOST, secure=True)
        self.assertEqual(page.status_code, 200)
        # Over HTTPS Django's CSRF check also wants the Referer a browser sends.
        response = self.client.post(LOGIN, {'csrfmiddlewaretoken': str(page.context['csrf_token'])},
                                    HTTP_HOST=HOST, HTTP_REFERER=f'https://{HOST}{LOGIN}', secure=True)
        self.assertEqual(response.status_code, 302)
        return urlsplit(response['Location'])

    def sign_in(self, userinfo):
        fake = self.linkedin(userinfo)
        state = parse_qs(self.start().query)['state'][0]
        response = self.client.get(f'{CALLBACK}?code=test-code&state={state}', HTTP_HOST=HOST, secure=True)
        return response, fake

    # -- configuration --------------------------------------------------------

    def test_legacy_provider_is_gone_and_the_oidc_app_is_linkedin(self):
        self.assertNotIn('allauth.socialaccount.providers.linkedin_oauth2', settings.INSTALLED_APPS)
        with self.assertRaises(NoReverseMatch):
            reverse('linkedin_oauth2_login')
        app = settings.SOCIALACCOUNT_PROVIDERS['openid_connect']['APPS'][0]
        self.assertEqual((app['provider_id'], app['settings']['server_url'], app['settings']['token_auth_method']),
                         ('linkedin', 'https://www.linkedin.com/oauth', 'client_secret_post'))
        self.assertEqual(reverse('openid_connect_callback', kwargs={'provider_id': 'linkedin'}),
                         '/accounts/oidc/linkedin/login/callback/')

    def test_login_and_signup_pages_link_to_the_oidc_login(self):
        for name in ('accounts:login', 'accounts:signup'):
            body = self.client.get(reverse(name)).content.decode()
            with self.subTest(page=name):
                self.assertIn(f'href="{LOGIN}', body)
                self.assertNotIn('linkedin_oauth2', body)

    # -- the sign-in redirect --------------------------------------------------

    def test_get_shows_a_confirmation_form_and_post_without_csrf_is_refused(self):
        fake = self.linkedin({})
        page = self.client.get(LOGIN, HTTP_HOST=HOST, secure=True)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'method="post"')
        self.assertEqual(self.client.post(LOGIN, HTTP_HOST=HOST, secure=True).status_code, 403)
        self.assertEqual(fake.calls, [])  # nothing reached LinkedIn

    def test_post_redirects_to_linkedin_with_the_production_callback(self):
        fake = self.linkedin({})
        target = self.start()
        query = parse_qs(target.query)
        self.assertEqual(f'{target.scheme}://{target.netloc}{target.path}', OPENID_CONFIG['authorization_endpoint'])
        self.assertEqual(query['client_id'], [TEST_CLIENT_ID])
        self.assertEqual(query['redirect_uri'], [CALLBACK])
        self.assertEqual(query['response_type'], ['code'])
        self.assertEqual(sorted(query['scope'][0].split()), ['email', 'openid', 'profile'])
        self.assertTrue(query['state'][0])
        self.assertEqual([c[:2] for c in fake.calls], [('GET', DISCOVERY)])

    def test_only_the_linkedin_form_may_submit_to_linkedin(self):
        headers = ('Content-Security-Policy', 'Content-Security-Policy-Report-Only')
        linkedin = self.client.get(LOGIN)
        regular = self.client.get(reverse('accounts:login'))
        google = self.client.get('/accounts/google/login/')
        for header in headers:
            with self.subTest(header=header):
                linkedin_policy, regular_policy = _directives(linkedin[header]), _directives(regular[header])
                self.assertEqual(linkedin_policy.pop('form-action'), ["'self'", LINKEDIN])
                self.assertEqual(regular_policy.pop('form-action'), ["'self'"])
                self.assertEqual(linkedin_policy, regular_policy)
                self.assertNotIn(LINKEDIN, _directives(google[header])['form-action'])

    # -- the callback and account linking -------------------------------------

    def test_first_sign_in_creates_an_account_keyed_by_the_oidc_subject(self):
        response, fake = self.sign_in({'sub': 'li-sub-new', 'email': 'new@example.com', 'email_verified': True,
                                       'given_name': 'Ada', 'family_name': 'Lovelace', 'name': 'Ada Lovelace'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('accounts:post_login_router'))
        account = SocialAccount.objects.get(provider='linkedin')
        self.assertEqual((account.uid, account.user.email), ('li-sub-new', 'new@example.com'))
        self.assertEqual(int(self.client.session['_auth_user_id']), account.user_id)
        # The secret travels in the POST body (client_secret_post), never as Basic auth.
        method, url, data, extra = next(c for c in fake.calls if c[0] == 'POST')
        self.assertEqual(url, OPENID_CONFIG['token_endpoint'])
        self.assertEqual((data['client_id'], data['client_secret'], data['redirect_uri']),
                         (TEST_CLIENT_ID, TEST_SECRET, CALLBACK))
        self.assertIsNone(extra['auth'])

    def test_returning_member_signs_in_to_the_same_account(self):
        user = User.objects.create_user('li_returning', email='back@example.com')
        SocialAccount.objects.create(user=user, provider='linkedin', uid='li-sub-back')
        users_before = User.objects.count()
        response, _ = self.sign_in({'sub': 'li-sub-back', 'email': 'back@example.com', 'email_verified': True})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.assertEqual(User.objects.count(), users_before)
        self.assertEqual(SocialAccount.objects.filter(provider='linkedin').count(), 1)

    def test_an_account_saved_under_the_legacy_provider_is_not_linked_or_taken_over(self):
        """
        A legacy row (provider 'linkedin_oauth2') does not match provider
        'linkedin', and email is not used to connect accounts. The member is
        not signed in to the existing account, no second account is created
        for that email, and the legacy row is left as it was.
        """
        user = User.objects.create_user('li_legacy', email='legacy@example.com')
        SocialAccount.objects.create(user=user, provider='linkedin_oauth2', uid='li-sub-legacy')
        users_before = User.objects.count()
        response, _ = self.sign_in({'sub': 'li-sub-legacy', 'email': 'legacy@example.com', 'email_verified': True})
        self.assertNotEqual(self.client.session.get('_auth_user_id'), str(user.pk))
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(User.objects.count(), users_before)
        self.assertFalse(SocialAccount.objects.filter(provider='linkedin').exists())
        self.assertTrue(SocialAccount.objects.filter(provider='linkedin_oauth2', user=user).exists())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('socialaccount_signup'))
