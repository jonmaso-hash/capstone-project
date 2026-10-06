from django.test import TestCase
from django.urls import reverse


class SocialAuthSurfaceTests(TestCase):
    PROVIDER_PATHS = (
        '/accounts/google/login/',
        '/accounts/facebook/login/',
        '/accounts/linkedin_oauth2/login/',
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
