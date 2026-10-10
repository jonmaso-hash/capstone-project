from types import SimpleNamespace

from bs4 import BeautifulSoup
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from pages.home_journeys import HOME_JOURNEYS, home_journey_context


class HomeRoleJourneyTests(SimpleTestCase):
    def context(self, role=None, authenticated=True, pending=None):
        user = SimpleNamespace(is_authenticated=authenticated)
        if role:
            setattr(user, 'match_' + role + '_profile', object())
        return home_journey_context(SimpleNamespace(
            user=user, session={'pending_profile_role': pending},
        ))

    def markup(self, context):
        return BeautifulSoup(render_to_string('pages/_home_role_journeys.html', context), 'html.parser')

    def test_public_homepage_exposes_all_roles_without_open_steps(self):
        soup = self.markup(self.context(authenticated=False))
        self.assertEqual(len(soup.select('[data-journey-role]')), 4)
        self.assertEqual(len(soup.select('[data-journey-panel]')), 4)
        self.assertFalse(soup.select('.role-journey-details[open]'))
        self.assertFalse(soup.select('.role-funding-info[open]'))
        for role in ('founder', 'investor', 'seller', 'buyer'):
            self.assertIsNotNone(soup.select_one(f'a[href$="?role={role}"]'))

    def test_signed_in_member_sees_only_their_role_path(self):
        for journey in HOME_JOURNEYS:
            with self.subTest(role=journey['key']):
                soup = self.markup(self.context(role=journey['key']))
                self.assertFalse(soup.select('[data-journey-role]'))
                panels = soup.select('[data-journey-panel]')
                self.assertEqual(len(panels), 1)
                self.assertEqual(panels[0]['data-journey-panel'], journey['key'])
                self.assertFalse(soup.select('.role-journey-details[open]'))
                self.assertEqual(len(soup.select('.role-journey-steps li')), len(journey['steps']))

    def test_pending_onboarding_role_has_its_own_path(self):
        context = self.context(pending='seller')
        self.assertEqual([j['key'] for j in context['home_journeys']], ['seller'])

    def test_existing_role_wins_over_pending_onboarding_role(self):
        context = self.context(role='investor', pending='seller')
        self.assertEqual([j['key'] for j in context['home_journeys']], ['investor'])

    def test_unassigned_account_is_linked_to_role_setup(self):
        soup = self.markup(self.context(pending='invalid-role'))
        self.assertFalse(soup.select('[data-journey-panel]'))
        self.assertIsNotNone(soup.find('a', string='Select your role'))

    def test_paths_include_bulletin_and_optional_zelda(self):
        founder, investor = HOME_JOURNEYS[:2]
        self.assertEqual(len(founder['steps']), 6)
        self.assertIn('Founders Bulletin', founder['steps'][2]['description'])
        self.assertIn('optional', founder['steps'][5]['title'])
        self.assertIn('Founders Bulletin', investor['steps'][1]['description'])
        self.assertEqual(investor['steps'][2]['title'], 'Start the conversation')
        self.assertEqual(investor['steps'][3]['title'], 'Use your CRM')
        self.assertIn('optional', investor['steps'][4]['title'])
