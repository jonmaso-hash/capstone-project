"""
BW-005 / RA-010 / RA-112: the company overview looked its company up by name.

Company names are not unique, so /matchmaking/memo/<name>/ raised
MultipleObjectsReturned (a 500) as soon as two founders shared a name, and
every report's "Company overview" link pointed there. The overview is now
linked by the founder profile's id, and the legacy name URL serves a page
only when exactly one company this viewer may see carries the name.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from zelda_api.report_nav import OVERVIEW, build_report_nav
from zelda_api.truth_delta_models import TruthDeltaReport
from zelda_api.vector_models import DocumentSource, IntelligenceMemo

from .models import Application, InvestorApplication
from .tests import _mock_embedding_generation

User = get_user_model()


class CompanyOverviewIdentityTests(TestCase):
    NAME = 'Twin Co'
    LEGACY_SLUG = 'twin-co'

    def setUp(self):
        _mock_embedding_generation(self)
        self.first, self.first_deck = self.founder('twin_first', 'First twin builds ledgers.')
        self.second, self.second_deck = self.founder('twin_second', 'Second twin sells boats.')
        self.hidden, _ = self.founder('twin_hidden', 'Hidden twin is private.', is_private=True)

        self.investor = User.objects.create_user('twin_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor, full_name='I', company_name='Fund', email='i@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.staff = User.objects.create_user('twin_staff', password='x', is_staff=True)
        self.other_founder = User.objects.create_user('twin_other_founder', password='x')
        Application.objects.create(user=self.other_founder, company_name='Elsewhere',
                                   founder_name='O', email='o@t.com')

    def founder(self, username, summary, **fields):
        user = User.objects.create_user(username, password='x')
        app = Application.objects.create(
            user=user, company_name=self.NAME, founder_name='F', email=f'{username}@t.com',
            description=summary, sector='SaaS', stage='Seed', **fields,
        )
        deck = DocumentSource.objects.create(
            uploaded_by=user, filename='deck.pdf', source_entity=self.NAME,
            document_type='pitch_deck', status='analyzed',
        )
        IntelligenceMemo.objects.create(
            document=deck, executive_summary=summary, evidence_level='PARTLY_EVIDENCED',
            completeness_score=0.5, citations_count=1,
        )
        TruthDeltaReport.objects.create(
            document=deck, overall_truth_score=60.0, credibility_risk='low', summary='ok',
            details={'claims': [], 'per_claim': []},
        )
        return app, deck

    def overview_url(self, app):
        return reverse('matchmaking:company_overview', args=[app.pk])

    def legacy_url(self, slug=LEGACY_SLUG):
        return reverse('matchmaking:standalone_memo', args=[slug])

    # --- document -> profile links ---

    def test_each_documents_overview_link_names_its_own_profile(self):
        self.client.force_login(self.investor)
        for app, deck, other in ((self.first, self.first_deck, self.second),
                                 (self.second, self.second_deck, self.first)):
            with self.subTest(company=app.user.username):
                page = self.client.get(reverse('zelda_api:truth_delta_ui', args=[deck.id]))
                self.assertEqual(page.status_code, 200)
                self.assertContains(page, f'href="{self.overview_url(app)}"')
                self.assertNotContains(page, f'href="{self.overview_url(other)}"')
                self.assertNotContains(page, f'href="{self.legacy_url()}"')

    def test_report_nav_links_the_overview_by_profile_id(self):
        nav = build_report_nav(self.investor, self.second.user, 'evidence')
        overview = next(item for item in nav if item['key'] == OVERVIEW)
        self.assertEqual(overview['url'], self.overview_url(self.second))

    # --- permitted viewers ---

    def test_investor_sees_the_linked_profile_and_not_its_namesake(self):
        self.client.force_login(self.investor)
        response = self.client.get(self.overview_url(self.first))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'First twin builds ledgers.')
        self.assertNotContains(response, 'Second twin sells boats.')
        self.assertNotContains(response, 'Hidden twin is private.')

    def test_staff_can_open_any_profile_including_a_private_one(self):
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(self.overview_url(self.second)), 'Second twin sells boats.')
        self.assertContains(self.client.get(self.overview_url(self.hidden)), 'Hidden twin is private.')

    # --- unauthorized viewers ---

    def test_private_profile_answers_like_a_missing_one_for_investors(self):
        self.client.force_login(self.investor)
        self.assertEqual(self.client.get(self.overview_url(self.hidden)).status_code, 404)
        missing = Application.objects.order_by('-pk').first().pk + 1000
        self.assertEqual(self.client.get(reverse('matchmaking:company_overview', args=[missing])).status_code, 404)

    def test_non_investor_founders_are_refused(self):
        self.client.force_login(self.other_founder)
        self.assertEqual(self.client.get(self.overview_url(self.first)).status_code, 403)
        self.assertEqual(self.client.get(self.overview_url(self.hidden)).status_code, 404)

    def test_anonymous_viewers_are_sent_to_login(self):
        for url in (self.overview_url(self.first), self.legacy_url()):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse('accounts:login'), response['Location'])

    # --- legacy name URLs ---

    def test_legacy_url_with_duplicated_visible_names_never_picks_one(self):
        self.client.force_login(self.investor)
        response = self.client.get(self.legacy_url())
        self.assertEqual(response.status_code, 404)
        for summary in ('First twin', 'Second twin', 'Hidden twin'):
            self.assertNotContains(response, summary, status_code=404)

    def test_legacy_url_serves_the_one_company_this_viewer_may_see(self):
        self.second.is_private = True
        self.second.save(update_fields=['is_private'])
        self.client.force_login(self.investor)
        response = self.client.get(self.legacy_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'First twin builds ledgers.')
        self.assertNotContains(response, 'Second twin sells boats.')
        self.assertNotContains(response, 'Hidden twin is private.')

    def test_legacy_url_for_a_name_only_hidden_profiles_carry_is_a_404(self):
        for app in (self.first, self.second):
            app.archived_at = app.created_at
            app.save(update_fields=['archived_at'])
        self.client.force_login(self.investor)
        self.assertEqual(self.client.get(self.legacy_url()).status_code, 404)

    def test_legacy_url_stays_ambiguous_for_staff_rather_than_guessing(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.legacy_url()).status_code, 404)
