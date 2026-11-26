"""
A report a founder buys about another business is never the founder's own.

Reproduced at 613805e (isolated local walk, fixture data): a discoverable
founder with an analyzed deck bought a 3-Report Pack about another company.
Fulfilment clones the purchase evidence into an analyzed pitch_deck owned by
the founder and marked is_external_subject. Every "the founder's latest deck"
lookup then picked that clone, so:

- the investor-facing Company overview showed the purchased analysis of the
  other company as the founder's own;
- the IC memo, even opened through the founder's own deck id, showed it to a
  connected investor (and the purchased valuation with it);
- report links, the investor's Library and the profile pointed at the clone.

DocumentSource.is_external_subject already means "evidence about another
business, never the uploader profile"; company_document_filter applies that at
every lookup of a company's own documents. Purchased reports stay readable to
their owner through billing (checked below).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from billing.models import ZeldaOrder
from matchmaking.models import Application, Connection, InvestorApplication, InvestorInterestEvent
from matchmaking.tests import _mock_embedding_generation
from zelda_api.ic_memo import MEMO_SECTIONS, latest_analyzed_pitch_deck_and_memo
from zelda_api.truth_delta_models import TruthDeltaReport
from zelda_api.vector_models import BusinessValuationReport, DocumentSource, IntelligenceMemo

User = get_user_model()
OWN = '[OWN-DECK]'
BOUGHT = '[PURCHASED-OTHER-CO]'
OTHER_CO = 'Outside Target Holdings'


def _memo(document, marker, score):
    fields = {field: f'{marker} {label}.' for field, label in MEMO_SECTIONS}
    fields['information_readiness'] = f'Score: {score}/100\n{marker} readiness.'
    return IntelligenceMemo.objects.create(document=document, **fields)


class PurchasedReportFixture(TestCase):
    """A discoverable founder with an older own deck and a newer purchased report about another company."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('pr_founder', password='x')
        self.founder = Application.objects.create(
            user=self.founder_user, company_name='Larkspur Grid', founder_name='F', email='f@t.test',
            description='Own company description.', sector='SaaS', stage='Seed')
        self.own_deck = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='own-deck.pdf', source_entity='Larkspur Grid',
            document_type='pitch_deck', status='analyzed')
        _memo(self.own_deck, OWN, 41)
        TruthDeltaReport.objects.create(document=self.own_deck, summary=f'{OWN} evidence summary.')
        self.own_valuation = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='own-valuation.pdf', source_entity='Larkspur Grid',
            document_type='business_valuation', status='analyzed', valuation_tier='full')
        BusinessValuationReport.objects.create(document=self.own_valuation, business_overview=f'{OWN} valuation.',
                                               valuation_summary=f'{OWN} valuation summary.')
        old = timezone.now() - timedelta(days=3)
        DocumentSource.objects.filter(pk__in=[self.own_deck.pk, self.own_valuation.pk]).update(created_at=old)

        # Exactly what intake + fulfilment leave behind for a paid 3-Report Pack.
        source = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='target.txt', source_entity=OTHER_CO,
            document_type='research_report', status='ingested', is_product_input=True, is_external_subject=True)
        self.clone = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='target.txt', source_entity=OTHER_CO,
            document_type='pitch_deck', status='analyzed', is_external_subject=True)
        _memo(self.clone, BOUGHT, 97)
        TruthDeltaReport.objects.create(document=self.clone, summary=f'{BOUGHT} evidence summary.')
        self.clone_valuation = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='target.txt', source_entity=OTHER_CO,
            document_type='business_valuation', status='analyzed', is_external_subject=True, valuation_tier='full')
        BusinessValuationReport.objects.create(document=self.clone_valuation, business_overview=f'{BOUGHT} valuation.',
                                               valuation_summary=f'{BOUGHT} valuation summary.')
        self.order = ZeldaOrder.objects.create(
            user=self.founder_user, source_document=source, product='three_pack',
            reports=['intelligence_memo', 'truth_delta', 'valuation'], amount=2499, status='ready',
            stripe_session_id='cs_purchased_private', paid_at=timezone.now(), finished_at=timezone.now(),
            analysis_document=self.clone, valuation_document=self.clone_valuation)

        self.investor_user = User.objects.create_user('pr_investor', password='x')
        self.investor = InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', email='i@t.test', company_name='Harbor Capital',
            investment_focus='SaaS', investment_stage='Seed')
        Connection.objects.create(investor=self.investor, founder=self.founder, status='ACCEPTED')

    def get(self, user, url):
        self.client.force_login(user)
        return self.client.get(url)

    def assertOwnNotBought(self, response, *, own_required=True):
        content = response.content.decode()
        self.assertNotIn(BOUGHT, content)
        self.assertNotIn(OTHER_CO, content)
        self.assertNotIn(f'/documents/{self.clone.id}/', content)
        self.assertNotIn(f'/valuation/{self.clone_valuation.id}/', content)
        if own_required:
            self.assertIn(OWN, content, 'positive control: the founder\'s own deck is what is shown')


class CompanyLookupTests(PurchasedReportFixture):
    def test_the_latest_company_deck_is_the_founders_own(self):
        document, memo = latest_analyzed_pitch_deck_and_memo(self.founder_user)
        self.assertEqual(document, self.own_deck)
        self.assertIn(OWN, memo.executive_summary)

    def test_investor_company_overview_shows_the_founders_own_analysis(self):
        response = self.get(self.investor_user, reverse('matchmaking:company_overview', args=[self.founder.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertOwnNotBought(response)

    def test_ic_memo_through_the_own_deck_shows_only_the_founders_company(self):
        for user in (self.investor_user, self.founder_user):
            with self.subTest(user=user.username):
                response = self.get(user, reverse('zelda_api:ic_memo', args=[self.own_deck.id]))
                self.assertEqual(response.status_code, 200)
                self.assertOwnNotBought(response)

    def test_full_ic_memo_uses_the_founders_own_valuation(self):
        # The valuation section only renders at the full tier (founder Premium).
        Application.objects.filter(pk=self.founder.pk).update(is_premium=True)
        self.founder.refresh_from_db()
        from zelda_api.ic_memo import build_ic_memo_context
        valuation = build_ic_memo_context(self.founder, tier='full', viewer=self.investor_user)['valuation']
        self.assertIn(OWN, valuation['valuation_summary'])
        response = self.get(self.investor_user, reverse('zelda_api:ic_memo', args=[self.own_deck.id]))
        self.assertContains(response, f'{OWN} valuation summary.')
        self.assertOwnNotBought(response)

    def test_ic_memo_routes_refuse_a_purchased_document_id(self):
        for name in ('zelda_api:ic_memo', 'zelda_api:ic_memo_download'):
            for user in (self.investor_user, self.founder_user):
                with self.subTest(name=name, user=user.username):
                    self.assertEqual(self.get(user, reverse(name, args=[self.clone.id])).status_code, 404)

    def test_report_links_point_at_the_founders_own_documents(self):
        from zelda_api.report_nav import build_report_nav
        for viewer in (self.investor_user, self.founder_user):
            with self.subTest(viewer=viewer.username):
                urls = {item['key']: item['url'] for item in build_report_nav(viewer, self.founder_user, None)}
                self.assertEqual(urls['evidence'], reverse('zelda_api:truth_delta_ui', args=[self.own_deck.id]))
                self.assertEqual(urls['analysis'], reverse('zelda_api:ic_memo', args=[self.own_deck.id]))
        owner_urls = {item['key']: item['url'] for item in build_report_nav(self.founder_user, self.founder_user, None)}
        self.assertEqual(owner_urls['valuation'], reverse('zelda_api:valuation_report', args=[self.own_valuation.id]))

    def test_investor_library_offers_the_founders_own_brief(self):
        InvestorInterestEvent.objects.create(investor=self.investor_user, founder=self.founder, event_type='memo_view')
        data = self.get(self.investor_user, '/api/v1/zelda/library/').json()
        recent = next(s for s in data['sections'] if s['key'] == 'recent_companies')['items']
        self.assertEqual([c['brief_document_id'] for c in recent], [self.own_deck.id])
        self.assertNotIn(BOUGHT, str(data))

    def test_profile_counts_and_links_only_the_founders_own_reports(self):
        response = self.get(self.investor_user, reverse('accounts:profile', kwargs={'username': self.founder_user.username}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['verification_reports_count'], 1)
        self.assertEqual(response.context['ic_memo_document_id'], self.own_deck.id)
        self.assertOwnNotBought(response, own_required=False)

    def test_deal_room_summary_reads_the_founders_own_reports(self):
        from matchmaking.views import _get_deal_zelda_summary
        summary = _get_deal_zelda_summary(self.founder)
        self.assertEqual(summary['latest_memo'].document, self.own_deck)
        self.assertEqual(summary['latest_truth_delta'].document, self.own_deck)

    def test_share_card_score_comes_from_the_founders_own_deck(self):
        from growth.templatetags.growth_tags import _lookup_score
        self.assertEqual(_lookup_score(self.founder_user), ('founder', 41))

    def test_investor_analysis_never_selects_a_purchased_document(self):
        from zelda_api.views import _usable_pitch_deck_document
        DocumentSource.objects.filter(pk=self.own_deck.pk).update(raw_text_full='Own deck text. ' * 200)
        DocumentSource.objects.filter(pk=self.clone.pk).update(raw_text_full='Purchased text. ' * 200)
        self.assertEqual(_usable_pitch_deck_document(self.founder_user), self.own_deck)


class PurchasedReportStillWorksTests(PurchasedReportFixture):
    def test_the_owner_still_reads_the_purchase_and_sees_it_in_library(self):
        response = self.get(self.founder_user, reverse('billing:zelda_report', args=[self.order.id, 'intelligence_memo']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, BOUGHT)
        purchases = self.get(self.founder_user, '/api/v1/zelda/library/').json()['purchases']
        self.assertEqual([p['order_id'] for p in purchases], [str(self.order.id)])
        self.assertEqual(purchases[0]['company'], OTHER_CO)

    def test_nobody_else_reads_the_purchase(self):
        response = self.get(self.investor_user, reverse('billing:zelda_report', args=[self.order.id, 'intelligence_memo']))
        self.assertEqual(response.status_code, 404)
