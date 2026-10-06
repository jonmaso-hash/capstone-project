from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.models import Application


User = get_user_model()


class FounderNavigationParityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('nav_founder', password='x')
        Application.objects.create(
            user=self.user,
            founder_name='Nav Founder',
            email='nav@example.com',
            company_name='Nav Co',
            sector='SaaS',
            stage='Seed',
            description='Navigation parity test',
            is_private=False,
        )
        self.client.force_login(self.user)

    def test_founder_navigation_points_to_recovered_workflows(self):
        response = self.client.get(reverse('accounts:profile', args=[self.user.username]))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()

        expected_hrefs = (
            reverse('matchmaking:founder_dashboard'),
            reverse('matchmaking:fundraising_crm'),
            reverse('matchmaking:data_room', args=[self.user.username]),
            reverse('matchmaking:diligence_chat'),
            reverse('accounts:profile_self'),
        )
        for href in expected_hrefs:
            with self.subTest(href=href):
                self.assertIn(f'href="{href}"', body)

    def test_profile_self_redirects_to_named_founder_profile(self):
        response = self.client.get(reverse('accounts:profile_self'))
        self.assertRedirects(
            response,
            reverse('accounts:profile', args=[self.user.username]),
            fetch_redirect_response=False,
        )
