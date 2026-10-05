"""
The founder dashboard has no "Optimize Match Vector" button.

The button sat in a "Refresh My Matches" card and posted the founder's
*application* id to the Truth Delta verify endpoint, which expects a
*document* id. It never refreshed matches: at best it failed, at worst it ran
verification on someone else's document number. The investor dashboard
carried a second, uncalled copy of the same script.

Both are removed with no replacement: matches already recalculate when a
profile is saved.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Application, InvestorApplication

User = get_user_model()

REMOVED = (
    'Optimize Match Vector',
    'Refresh My Matches',
    'triggerAutonomousScraper',
    'scraper-status-global',
    'truth-delta/verify/',
    'Ready to execute crawler queries',
)


class NoOptimizeMatchVectorTests(TestCase):

    def setUp(self):
        patcher = mock.patch('matchmaking.signals.generate_profile_embedding', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.founder_user = User.objects.create_user('omv_founder', password='x')
        Application.objects.create(
            user=self.founder_user, company_name='OmvCo', founder_name='F', email='omvf@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.investor_user = User.objects.create_user('omv_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='OmvFund', email='omvi@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )

    def _dashboard(self, user, name):
        self.client.force_login(user)
        response = self.client.get(reverse(name))
        self.assertEqual(response.status_code, 200)
        return response

    def test_the_founder_dashboard_has_no_optimize_button_or_its_script(self):
        response = self._dashboard(self.founder_user, 'matchmaking:founder_dashboard')
        # Positive control: this is the rendered dashboard, not an error page.
        self.assertContains(response, 'Pending Inbound Requests')
        for text in REMOVED:
            with self.subTest(text=text):
                self.assertNotContains(response, text)

    def test_the_investor_dashboard_has_no_leftover_script(self):
        response = self._dashboard(self.investor_user, 'matchmaking:investor_dashboard')
        # Positive control: the Zelda analysis buttons' status targets stay.
        self.assertContains(response, 'analyzeFounderWithZelda')
        for text in REMOVED:
            with self.subTest(text=text):
                self.assertNotContains(response, text)
