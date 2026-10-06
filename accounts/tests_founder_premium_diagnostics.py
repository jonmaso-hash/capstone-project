from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.models import Application


User = get_user_model()


class FounderPremiumDiagnosticsPlacementTests(TestCase):
    def setUp(self):
        self.embedding_patch = patch(
            'matchmaking.signals.generate_profile_embedding',
            return_value=[],
        )
        self.embedding_patch.start()
        self.addCleanup(self.embedding_patch.stop)

    def _founder(self, username, premium):
        user = User.objects.create_user(username=username, password='x')
        application = Application.objects.create(
            user=user,
            company_name=f'{username} Co',
            founder_name='Founder',
            email=f'{username}@example.com',
            description='',
            sector='SaaS',
            stage='Seed',
            is_private=True,
            is_premium=premium,
        )
        return user, application

    def test_founder_profile_no_longer_renders_readiness_or_activity(self):
        user, _ = self._founder('diagnostics_profile', premium=True)
        self.client.force_login(user)

        response = self.client.get(
            reverse('accounts:profile', args=[user.username])
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Investor Readiness')
        self.assertNotContains(response, 'Founder Activity')
        self.assertNotIn('investor_readiness', response.context)
        self.assertNotIn('founder_activity', response.context)

    def test_free_founder_insights_does_not_leak_premium_diagnostics(self):
        user, _ = self._founder('diagnostics_free', premium=False)
        self.client.force_login(user)

        response = self.client.get(
            reverse('accounts:profile_analysis', args=[user.username])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['profile_analysis_locked'])
        self.assertContains(response, 'Unlock Founder Insights')
        self.assertNotContains(response, 'Investor Readiness')
        self.assertNotContains(response, 'Founder Activity')

    def test_premium_founder_insights_contains_readiness_and_activity(self):
        user, _ = self._founder('diagnostics_premium', premium=True)
        self.client.force_login(user)

        response = self.client.get(
            reverse('accounts:profile_analysis', args=[user.username])
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['profile_analysis_locked'])
        self.assertContains(response, 'Investor Readiness')
        self.assertContains(response, 'Founder Activity')
        self.assertIn('investor_readiness', response.context)
        self.assertIn('founder_activity', response.context)
