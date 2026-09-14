"""
Private, archived and denied companies can't be reached by name (PR #57).

Three routes looked a founder up by company name or username with no
visibility check:

- /<company name>/ (MemoIntelligenceView): a score for any company, to any
  signed-in user -- removed; nothing called it
- matchmaking/memo/<company_slug>/ (the Zelda Intelligence Report)
- api/v1/zelda/analyze/founder/<username>/ and its /confirm/ step, which could
  spend an investor's credit analyzing a hidden founder

The rule is the existing one: Application.objects.discoverable() (not private,
not archived), not DENIED. The owner and staff always pass. Anyone else gets
exactly what a company that doesn't exist gives them, so a 404 never confirms
that a hidden company is there.
"""
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from matchmaking.models import Application, InvestorApplication
from matchmaking.tests import _mock_embedding_generation
from zelda_api.models import AnalysisCreditCharge

User = get_user_model()
HIDDEN = ('private', 'archived', 'denied')


class _Companies(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('vis_founder', password='x')
        self.founder = Application.objects.create(
            user=self.founder_user, company_name='Northwind Grid', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.investor_user = User.objects.create_user('vis_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', email='i@t.com', company_name='Harbor Capital',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.staff = User.objects.create_user('vis_staff', password='x', is_staff=True)

    def _set_visibility(self, how):
        self.founder.is_private = how == 'private'
        self.founder.archived_at = timezone.now() if how == 'archived' else None
        self.founder.review_status = 'DENIED' if how == 'denied' else 'APPROVED'
        self.founder.save()


class CompanyNameCatchAllRemovedTests(_Companies):

    def test_the_company_name_route_is_gone(self):
        with self.assertRaises(NoReverseMatch):
            reverse('memo-intelligence', args=['Northwind Grid'])
        self.client.force_login(self.investor_user)
        self.assertEqual(self.client.get('/Northwind%20Grid/').status_code, 404)

    def test_an_unknown_single_segment_url_is_a_404_signed_in_or_out(self):
        self.assertEqual(self.client.get('/no-such-page/').status_code, 404)
        self.client.force_login(self.investor_user)
        self.assertEqual(self.client.get('/no-such-page/').status_code, 404)


class IntelligenceReportVisibilityTests(_Companies):

    def _report(self, user, slug='northwind-grid'):
        self.client.force_login(user)
        return self.client.get(reverse('matchmaking:standalone_memo', args=[slug]))

    def test_control_an_investor_opens_a_visible_companys_report(self):
        self.assertEqual(self._report(self.investor_user).status_code, 200)

    def test_an_investor_gets_404_for_a_hidden_company_same_as_no_company(self):
        self.assertEqual(self._report(self.investor_user, slug='no-such-company').status_code, 404)
        for how in HIDDEN:
            with self.subTest(how=how):
                self._set_visibility(how)
                self.assertEqual(self._report(self.investor_user).status_code, 404)

    def test_a_signed_in_user_without_a_role_gets_404_not_403_for_a_hidden_company(self):
        roleless = User.objects.create_user('vis_roleless', password='x')
        self._set_visibility('private')
        self.assertEqual(self._report(roleless).status_code, 404)

    def test_staff_still_open_a_hidden_companys_report(self):
        for how in HIDDEN:
            with self.subTest(how=how):
                self._set_visibility(how)
                self.assertEqual(self._report(self.staff).status_code, 200)


class AnalyzeFounderVisibilityTests(_Companies):

    def _analyze(self, username):
        self.client.force_login(self.investor_user)
        return self.client.get(reverse('zelda_api:analyze_founder', args=[username]))

    def test_control_an_investor_can_look_up_a_visible_founder(self):
        response = self._analyze(self.founder_user.username)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'no_deck')

    def test_a_hidden_founder_looks_exactly_like_a_user_with_no_founder_profile(self):
        roleless = User.objects.create_user('vis_no_profile', password='x')
        no_profile = self._analyze(roleless.username)
        self.assertEqual(no_profile.status_code, 404)
        for how in HIDDEN:
            with self.subTest(how=how):
                self._set_visibility(how)
                response = self._analyze(self.founder_user.username)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), no_profile.json())

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_confirm_cannot_spend_a_credit_on_a_hidden_founder(self):
        self.founder.pitch_deck = SimpleUploadedFile('deck.pdf', b'%PDF-1.4 deck', content_type='application/pdf')
        self._set_visibility('private')
        self.client.force_login(self.investor_user)
        with mock.patch('zelda_api.quotas.has_credits_for', return_value=True), \
                mock.patch('zelda_api.utils._extract_pdf_text', return_value=('deck text', 1)), \
                mock.patch('zelda_api.tasks.process_document_pipeline.delay'):
            response = self.client.post(
                reverse('zelda_api:analyze_founder_confirm', args=[self.founder_user.username]))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(AnalysisCreditCharge.objects.exists())
