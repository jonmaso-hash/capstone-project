from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.models import Application


User = get_user_model()


class FounderProfileZeldaWorkspaceTests(TestCase):
    def setUp(self):
        self.embedding_patch = patch(
            'matchmaking.signals.generate_profile_embedding',
            return_value=[],
        )
        self.embedding_patch.start()
        self.addCleanup(self.embedding_patch.stop)

        self.user = User.objects.create_user('founder_zelda_workspace', password='x')
        Application.objects.create(
            user=self.user,
            company_name='Workspace Co',
            founder_name='Founder',
            email='founder@example.com',
            description='Test',
            sector='SaaS',
            stage='Seed',
            is_private=True,
        )
        self.client.force_login(self.user)

    def test_profile_workspace_promotes_zelda_products_not_duplicate_tools(self):
        response = self.client.get(reverse('accounts:profile', args=[self.user.username]))
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, 'Put Zelda to work on Workspace Co')
        self.assertContains(response, 'Truth Delta')
        self.assertContains(response, 'Zelda IC Memo')
        self.assertContains(response, 'Entity Integrity')
        self.assertContains(response, 'Business Valuation')
        self.assertContains(response, 'Saved Reports')

        # Operational actions belong in navigation/dashboard, not this profile card.
        self.assertNotContains(response, '> Post a Job</a>')

    def test_founder_navbar_keeps_crm_one_click_away(self):
        response = self.client.get(reverse('accounts:profile', args=[self.user.username]))
        self.assertContains(response, reverse('matchmaking:fundraising_crm'))
        self.assertContains(response, '>CRM</a>')
