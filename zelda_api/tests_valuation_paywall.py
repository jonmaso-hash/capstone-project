"""
A valuation's range and methodology appear only where the valuation itself is
unlocked (three-deck audit, A-1).

The valuation page hides a 'preview'-tier report's range and methodology until
the founder unlocks it, for every viewer including staff
(valuation_preview.build_valuation_response). The IC memo copied both straight
from the report: the Nike audit owner's valuation page said "Upgrade to Zelda
AI — $9.99", while the same owner's IC memo printed "Range: $105,600,000,000 –
$184,800,000,000". An IC memo is built to be shared with investors. The seller
dashboard did the same with its "suggested asking price".

Each test pairs the locked state with the unlocked one, so a fix that simply
deleted the range everywhere would fail too.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.models import Application, Connection, InvestorApplication, SellerApplication
from matchmaking.tests import _mock_embedding_generation
from zelda_api.ic_memo import VALUATION_LOCKED_NOTE, build_ic_memo_context, render_ic_memo_markdown
from zelda_api.vector_models import BusinessValuationReport, DocumentSource, IntelligenceMemo

User = get_user_model()

RANGE_TEXT = '105,600,000'                  # appears in any rendering of the range
METHODOLOGY = 'METHODOLOGY: a revenue multiple applied to the stated figure.'


def add_valuation(user, tier, name='MemoCo'):
    doc = DocumentSource.objects.create(uploaded_by=user, filename='fin.pptx', source_entity=name,
                                        document_type='business_valuation', status='analyzed', valuation_tier=tier)
    BusinessValuationReport.objects.create(
        document=doc, business_overview='Overview.', financial_summary='Revenue $52.8B (disclosed).',
        risk_report='1. Risk.', valuation_summary=METHODOLOGY, valuation_low=Decimal('105600000000'),
        valuation_high=Decimal('184800000000'), confidence_score=0.56)
    return doc


class ICMemoValuationPaywallTests(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder = User.objects.create_user('vp_founder', password='x')
        self.app = Application.objects.create(user=self.founder, company_name='MemoCo', founder_name='F',
                                              email='f@t.test', description='d', sector='SaaS', stage='Seed',
                                              is_premium=True)        # full IC memo, so the section renders
        self.deck = DocumentSource.objects.create(uploaded_by=self.founder, filename='deck.pdf', source_entity='MemoCo',
                                                  document_type='pitch_deck', status='analyzed')
        IntelligenceMemo.objects.create(document=self.deck, executive_summary='We build tools.',
                                        evidence_level='PARTLY_EVIDENCED', completeness_score=0.8, citations_count=1)
        self.staff = User.objects.create_user('vp_staff', password='x', is_staff=True)
        self.investor = User.objects.create_user('vp_investor', password='x')
        investor_app = InvestorApplication.objects.create(user=self.investor, full_name='I', company_name='Fund',
                                                          email='i@t.test', investment_focus='SaaS', investment_stage='Seed')
        Connection.objects.create(investor=investor_app, founder=self.app, status='ACCEPTED', initiated_by='INVESTOR')

    def page(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse('zelda_api:ic_memo', args=[self.deck.id]))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def download(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse('zelda_api:ic_memo_download', args=[self.deck.id]))
        self.assertEqual(response.status_code, 200)
        return b''.join(response.streaming_content).decode() if response.streaming else response.content.decode()

    def test_a_locked_valuation_shows_no_range_or_methodology_to_anyone(self):
        add_valuation(self.founder, 'preview')
        for user in (self.founder, self.staff, self.investor):
            with self.subTest(viewer=user.username):
                html = self.page(user)
                self.assertNotIn(RANGE_TEXT, html)
                self.assertNotIn(METHODOLOGY, html)
                self.assertIn(VALUATION_LOCKED_NOTE, html)
                self.assertIn('Disclosure Coverage', html)       # what the free preview shows stays

    def test_a_locked_valuation_is_not_in_the_export(self):
        add_valuation(self.founder, 'preview')
        for user in (self.founder, self.staff):
            with self.subTest(viewer=user.username):
                text = self.download(user)
                self.assertNotIn(RANGE_TEXT, text)
                self.assertNotIn(METHODOLOGY, text)
                self.assertIn(VALUATION_LOCKED_NOTE, text)

    def test_the_locked_figures_are_absent_from_the_context_not_just_hidden(self):
        add_valuation(self.founder, 'preview')
        valuation = build_ic_memo_context(self.app, tier='full')['valuation']
        self.assertEqual(set(valuation), {'unlocked', 'disclosure_coverage', 'locked_note'})
        self.assertNotIn(RANGE_TEXT, render_ic_memo_markdown(build_ic_memo_context(self.app)))

    def test_an_unlocked_valuation_shows_its_range_and_methodology(self):
        # Positive control: the fix must not remove the range a founder paid for.
        add_valuation(self.founder, 'full')
        for user in (self.founder, self.staff, self.investor):
            with self.subTest(viewer=user.username):
                html = self.page(user)
                self.assertIn(RANGE_TEXT, html)
                self.assertIn(METHODOLOGY, html)
                self.assertNotIn(VALUATION_LOCKED_NOTE, html)
        self.assertIn(RANGE_TEXT, self.download(self.founder))

    def test_unlocking_reveals_the_range(self):
        doc = add_valuation(self.founder, 'preview')
        self.assertNotIn(RANGE_TEXT, self.page(self.founder))
        from zelda_api.quotas import unlock_valuation_document
        unlock_valuation_document(doc, 'report')
        self.assertIn(RANGE_TEXT, self.page(self.founder))


class SellerDashboardValuationPaywallTests(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.seller = User.objects.create_user('vp_seller', password='x')
        SellerApplication.objects.create(user=self.seller, company_name='Widgets', seller_name='S',
                                         email='s@t.test', description='A business.')

    def dashboard(self):
        self.client.force_login(self.seller)
        response = self.client.get(reverse('matchmaking:seller_dashboard'))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_a_locked_valuation_is_not_suggested_as_an_asking_price(self):
        add_valuation(self.seller, 'preview', name='Widgets')
        html = self.dashboard()
        self.assertNotIn(RANGE_TEXT, html)
        self.assertIn('Your most recent Zelda valuation is a free preview', html)

    def test_an_unlocked_valuation_is_suggested(self):
        add_valuation(self.seller, 'full', name='Widgets')
        html = self.dashboard()
        self.assertIn(RANGE_TEXT, html)
        self.assertNotIn('is a free preview', html)
