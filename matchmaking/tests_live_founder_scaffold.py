from django.contrib.auth import get_user_model
from django.test import TestCase

from matchmaking.models import Application, InvestorApplication


User = get_user_model()


class LiveFounderScaffoldMigrationContractTests(TestCase):
    def test_scaffold_shape_matches_safe_live_defaults(self):
        user = User.objects.create_user(
            username='jonmason',
            email='jonmaso@gmail.com',
            password='x',
        )
        Application.objects.create(
            user=user,
            company_name='Interlink Foundry',
            founder_name='jonmason',
            email=user.email,
            description='',
            sector='Other',
            stage='Seed',
            is_private=True,
        )

        profile = Application.objects.get(user=user)
        self.assertEqual(profile.company_name, 'Interlink Foundry')
        self.assertTrue(profile.is_private)
        self.assertEqual(profile.description, '')

    def test_existing_marketplace_role_blocks_founder_scaffold_assumption(self):
        user = User.objects.create_user(
            username='jonmason',
            email='jonmaso@gmail.com',
            password='x',
        )
        InvestorApplication.objects.create(
            user=user,
            investment_focus='SaaS',
            investment_stage='Seed',
        )

        self.assertFalse(Application.objects.filter(user=user).exists())
