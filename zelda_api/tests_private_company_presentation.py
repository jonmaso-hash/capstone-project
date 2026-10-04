"""
Private-company presentation: limited public evidence is not a failing grade,
and a real contradiction is never hidden.

Three fixtures, built from real comparison rows so the canonical states come
from the real grounding rules:

    PRIVATE  three claims, no public source for any (the launch market)
    NIKE     revenue has an SEC figure but no comparable period; employees none
    MIXED    revenue contradicted (comparable period), employees verified,
             customers not established

Invariants pinned here:

1. Coverage is counts, never a percentage: no "%" and no "checkable" on any
   coverage surface, and "Limited public evidence" when nothing is scoreable.
2. If any claim's canonical state is `contradicted`, at least one visible
   coverage/observation surface shows it as contradicted, and it is never
   counted as "not established". The IC memo and Intelligence Report bars used
   to compute `total - verified` and file it under "No external data", and
   "What Zelda noticed" never mentioned it.
3. Every surface reads ic_memo.coverage_counts(); no template recomputes.
"""
import re

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from matchmaking.models import Application, InvestorApplication
from matchmaking.tests import _mock_embedding_generation
from zelda_api.ic_memo import (
    build_ic_memo_context, coverage_counts, coverage_sentence, render_ic_memo_markdown,
    truth_delta_signal, zelda_report_observations)
from zelda_api.truth_delta_models import TruthDeltaReport
from zelda_api.vector_models import DocumentSource, IntelligenceMemo

User = get_user_model()


def row(category, claimed, observed=None, period=None, claim_period=None, source='SEC EDGAR'):
    return {
        'category': category, 'claimed_value': str(claimed), 'claimed_value_numeric': float(claimed),
        'observed_value': None if observed is None else str(observed),
        'observed_value_numeric': None if observed is None else float(observed),
        'observed_source': source if observed is not None else None,
        'observed_registrant': '0000000001' if observed is not None else None,
        'observed_time_period': period, 'claim_period': claim_period,
        'discrepancy_pct': None if observed is None else round((claimed - observed) / observed * 100, 1),
        'claim_raw_text': str(claimed),
    }


FIXTURES = {
    'PRIVATE': [row('revenue', 2.4e6), row('employees', 18), row('customers', 140)],
    'NIKE': [row('revenue', 52.8e9, 46.398e9, period='FY2026 10-K'), row('employees', 81500)],
    'MIXED': [row('revenue', 80e9, 46.398e9, period='FY2026 10-K', claim_period='FY2026 10-K'),
              row('employees', 81000, 81500, period='FY2026 10-K'),
              row('customers', 140)],
}

PERCENT = re.compile(r'\d+(?:\.\d+)?\s*%')


class _Fixture(TestCase):
    fixture = 'PRIVATE'

    def setUp(self):
        _mock_embedding_generation(self)
        self.owner = User.objects.create_user('pcp_owner', password='x')
        self.app = Application.objects.create(user=self.owner, company_name='Private Co', founder_name='F',
                                              email='p@t.test', description='d', sector='Retail', stage='Seed')
        self.doc = DocumentSource.objects.create(filename='deck.pptx', source_entity='Private Co',
                                                 uploaded_by=self.owner, document_type='pitch_deck', status='analyzed')
        self.memo = IntelligenceMemo.objects.create(document=self.doc, executive_summary='Summary.',
                                                    evidence_level='LIMITED_EVIDENCE')
        rows = FIXTURES[self.fixture]
        observed = [{'category': r['category'], 'observed_value': r['observed_value'], 'source': 'SEC EDGAR',
                     'time_period': r['observed_time_period'], 'role': 'can_establish'}
                    for r in rows if r['observed_value'] is not None]
        self.report = TruthDeltaReport.objects.create(
            document=self.doc, overall_truth_score=None, credibility_risk='unknown', summary='s',
            details={'claims': [], 'observed': observed, 'comparison': rows,
                     'per_claim': [{'category': r['category'], 'claimed': r['claimed_value'],
                                    'observed': 'x', 'assessment': 'y'} for r in rows]})

    def surfaces(self):
        """Every coverage/observation surface, as a reader receives it."""
        self.client.force_login(self.owner)
        td_page = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.doc.id]))
        api = self.client.get(reverse('zelda_api:truth_delta_score', args=[self.doc.id])).json()
        signal = truth_delta_signal(self.doc)
        observations = zelda_report_observations(self.memo, self.doc)
        markdown = render_ic_memo_markdown(build_ic_memo_context(self.app))
        return td_page, api, signal, observations, markdown


class PrivateCompanyTests(_Fixture):
    fixture = 'PRIVATE'

    def test_nothing_scoreable_reads_as_limited_public_evidence(self):
        td_page, api, signal, observations, markdown = self.surfaces()
        expected = 'Limited public evidence: none of the 3 claims could be verified or contradicted against a public source.'
        self.assertEqual(signal['coverage_sentence'], expected)
        self.assertEqual(api['coverage_sentence'], expected)
        self.assertEqual(td_page.context['coverage_sentence'], expected)
        self.assertEqual(signal['counts'], {'verified': 0, 'contradicted': 0, 'not_established': 3,
                                            'total': 3, 'scoreable': 0})

    def test_no_percentage_and_no_checkable_on_any_coverage_surface(self):
        td_page, api, signal, observations, markdown = self.surfaces()
        coverage_texts = [signal['coverage_sentence'], signal['coverage_line'], api['coverage_sentence'],
                          td_page.context['coverage_sentence'], *observations['noticed'],
                          next(line for line in markdown.splitlines() if 'Evidence coverage' in line)]
        for text in coverage_texts:
            with self.subTest(text=text[:60]):
                self.assertIsNone(PERCENT.search(text), text)
                self.assertNotIn('checkable', text)

    def test_the_truth_delta_page_labels(self):
        self.client.force_login(self.owner)
        body = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.doc.id])).content.decode()
        self.assertIn('Not established', body)
        self.assertIn('NOT SCORED · LIMITED PUBLIC EVIDENCE', body)
        self.assertNotIn('>Unverified<', body)
        self.assertNotIn("label: 'No external data'", body)
        self.assertNotIn('claims verified against external data (', body)


class NikeShapeTests(_Fixture):
    fixture = 'NIKE'

    def test_an_uncomparable_figure_is_not_established_not_no_external_data(self):
        td_page, api, signal, observations, markdown = self.surfaces()
        self.assertEqual(signal['counts']['not_established'], 2)
        self.assertIn('Limited public evidence', signal['coverage_sentence'])
        self.assertNotIn('No external data', render_ic_memo_markdown(build_ic_memo_context(self.app)))


class MixedWithAContradictionTests(_Fixture):
    fixture = 'MIXED'

    def test_the_fixture_really_holds_a_contradiction(self):
        self.assertEqual(self.report.category_states(),
                         {'revenue': 'contradicted', 'employees': 'verified', 'customers': 'no_data'})

    def test_a_contradiction_is_never_counted_as_not_established(self):
        td_page, api, signal, observations, markdown = self.surfaces()
        self.assertEqual(signal['counts'], {'verified': 1, 'contradicted': 1, 'not_established': 1,
                                            'total': 3, 'scoreable': 2})
        self.assertEqual((api['contradicted_count'], api['unverified_count']), (1, 1))
        self.assertEqual((td_page.context['contradicted_count'], td_page.context['unverified_count']), (1, 1))

    def test_a_contradiction_is_visible_on_every_coverage_surface(self):
        td_page, api, signal, observations, markdown = self.surfaces()
        self.assertEqual(signal['coverage_sentence'], '1 verified · 1 contradicted · 1 not established (of 3).')
        self.assertIn('1 contradicted', markdown)
        self.assertTrue(observations['noticed'][0].startswith('Revenue: the public figure differs'),
                        observations['noticed'])
        self.assertEqual(observations['worth_investigating'][0]['topic'], 'Revenue — contradicted by a public source')
        body = td_page.content.decode()
        self.assertIn('Contradicted', body)

    def test_the_ic_memo_and_intelligence_report_bars_show_it(self):
        # The full IC memo and the Intelligence Report's bar are Premium-owner
        # surfaces (existing gating, unchanged here).
        Application.objects.filter(pk=self.app.pk).update(is_premium=True)
        self.client.force_login(self.owner)
        ic_html = self.client.get(reverse('zelda_api:ic_memo', args=[self.doc.id])).content.decode()
        self.assertIn('Contradicted — 1', ic_html)
        self.assertIn('Not established — 1', ic_html)
        self.assertNotIn('No external data —', ic_html)

        investor = User.objects.create_user('pcp_investor', password='x')
        InvestorApplication.objects.create(user=investor, full_name='I', email='i@t.test', company_name='Ic',
                                           investment_focus='Retail', investment_stage='Seed', is_premium=True)
        self.client.force_login(investor)
        report_html = self.client.get(reverse('matchmaking:standalone_memo', args=['private-co'])).content.decode()
        self.assertIn('1 verified · 1 contradicted · 1 not established (of 3).', report_html)
        self.assertIn('Revenue: the public figure differs', report_html)


class CoverageCountsTests(SimpleTestCase):

    def test_not_established_is_the_no_data_count_never_total_minus_verified(self):
        self.assertEqual(coverage_counts({'total': 3, 'verified': 1, 'contradicted': 1, 'no_data': 1})['not_established'], 1)

    def test_one_claim_reads_naturally(self):
        self.assertEqual(coverage_sentence({'total': 1, 'verified': 0, 'contradicted': 0, 'no_data': 1}),
                         'Limited public evidence: the claim could not be verified or contradicted against a public source.')
