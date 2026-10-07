from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.models import ZeldaOrder
from matchmaking.models import Application
from zelda_api.vector_models import DocumentSource


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
        self.assertContains(response, 'Zelda Intelligence Memo')
        self.assertContains(response, 'Zelda IC Memo')
        self.assertContains(response, 'Truth Delta Report')
        self.assertContains(response, 'Zelda Complete Intelligence Bundle')
        self.assertContains(response, 'Zelda 3-Report Pack')
        self.assertContains(response, 'Entity Integrity Report')
        self.assertContains(response, 'Business valuation')
        self.assertContains(response, 'Saved Reports')
        self.assertNotContains(response, 'Founder Premium')
        self.assertNotContains(response, 'Investor premium')
        self.assertNotContains(response, 'Seller Premium')
        self.assertNotContains(response, 'Buyer Premium')

        # Operational actions belong in navigation/dashboard, not this profile card.
        self.assertNotContains(response, '> Post a Job</a>')

    def test_purchased_report_shows_checkmark_last_updated_and_update_prompt(self):
        source = DocumentSource.objects.create(
            uploaded_by=self.user,
            source_entity='Workspace Co',
            filename='workspace-evidence.txt',
            raw_text_full='Evidence',
            is_external_subject=True,
            is_product_input=True,
        )
        purchased_at = timezone.now()
        ZeldaOrder.objects.create(
            user=self.user,
            source_document=source,
            product='truth_delta',
            reports=['truth_delta'],
            amount=1999,
            status='ready',
            paid_at=purchased_at,
            stripe_session_id='cs_workspace_truth',
        )

        response = self.client.get(reverse('accounts:profile', args=[self.user.username]))

        self.assertContains(response, 'Purchased')
        self.assertContains(response, 'Report last updated')
        self.assertContains(response, 'Update report')

    def test_founder_dashboard_keeps_crm_available_after_navbar_cleanup(self):
        profile = self.client.get(reverse('accounts:profile', args=[self.user.username]))
        self.assertNotContains(profile, '>CRM</a>')

        dashboard = self.client.get(reverse('matchmaking:founder_dashboard'))
        self.assertContains(dashboard, reverse('matchmaking:fundraising_crm'))
