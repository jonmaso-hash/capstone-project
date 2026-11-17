from allauth.socialaccount import app_settings
from django.test import Client, TestCase
from django.urls import reverse


class SocialAuthSurfaceTests(TestCase):
    PROVIDER_PATHS = (
        '/accounts/google/login/',
        '/accounts/facebook/login/',
        '/accounts/oidc/linkedin/login/',
    )

    def test_login_page_exposes_all_social_sign_in_providers(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        for path in self.PROVIDER_PATHS:
            with self.subTest(path=path):
                self.assertIn(f'href="{path}', body)

    def test_signup_page_exposes_all_social_sign_in_providers(self):
        response = self.client.get(reverse('accounts:signup'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        for path in self.PROVIDER_PATHS:
            with self.subTest(path=path):
                self.assertIn(f'href="{path}', body)


def _directives(header):
    """Parse a CSP header into {directive: [sources]}, nonce sources removed."""
    parsed = {}
    for part in header.split(';'):
        name, *sources = part.split()
        parsed[name] = [s for s in sources if not s.startswith("'nonce-")]
    return parsed


class GoogleSignInFormPolicyTests(TestCase):
    """The Google confirmation form submits to a redirect ending on Google.

    Chrome applies form-action to that redirect, so this one response must
    permit accounts.google.com; every other page keeps form-action 'self'.
    """
    HEADERS = ('Content-Security-Policy', 'Content-Security-Policy-Report-Only')
    GOOGLE = 'https://accounts.google.com'

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def test_login_on_get_stays_disabled(self):
        self.assertFalse(app_settings.LOGIN_ON_GET)
        response = self.client.get('/accounts/google/login/')
        # A confirmation form, not a redirect straight to Google.
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'method="post"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_google_form_permits_google_redirect_in_both_policies(self):
        google = self.client.get('/accounts/google/login/')
        regular = self.client.get(reverse('accounts:login'))
        for header in self.HEADERS:
            with self.subTest(header=header):
                google_policy = _directives(google[header])
                regular_policy = _directives(regular[header])
                self.assertEqual(google_policy['form-action'], ["'self'", self.GOOGLE])
                # Every other directive is exactly the site-wide policy.
                google_policy.pop('form-action')
                regular_policy.pop('form-action')
                self.assertEqual(google_policy, regular_policy)

    def test_regular_login_page_keeps_form_action_self(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        for header in self.HEADERS:
            with self.subTest(header=header):
                self.assertEqual(_directives(response[header])['form-action'], ["'self'"])
                self.assertNotIn('google.com', response[header])

    def test_other_providers_keep_form_action_self(self):
        for path in ('/accounts/facebook/login/',):
            response = self.client.get(path)
            for header in self.HEADERS:
                with self.subTest(path=path, header=header):
                    self.assertEqual(_directives(response[header])['form-action'], ["'self'"])

    def test_post_requires_csrf_and_then_redirects_to_google(self):
        refused = self.client.post('/accounts/google/login/')
        self.assertEqual(refused.status_code, 403)

        page = self.client.get('/accounts/google/login/')
        token = page.context['csrf_token']
        response = self.client.post('/accounts/google/login/', {'csrfmiddlewaretoken': str(token)})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(self.GOOGLE + '/'), response['Location'])
