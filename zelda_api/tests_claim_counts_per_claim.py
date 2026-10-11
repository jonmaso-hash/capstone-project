"""
RA-104 / BW-002: labels that say "claims" count individual claims.

ManyChat's report 87 holds three claims (funding raised, usage, usage) in two
categories. The Truth Delta page said "2 claims analyzed" and "none of the 2
claims" above three claim rows, and the IC memo said "Claims checked: 3" beside
"(of 2)": every count label read category_states(), which has one entry per
category.

The labels now read TruthDeltaReport.claim_stats(), one entry per claim row.
The category aggregation, the verification states and the score formula are
untouched: canonical_score still reads the category counts, so counting claims
can never give an unscored report a score or move a scored one.
"""
import re
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from matchmaking.models import Application, InvestorApplication
from matchmaking.tests import _mock_embedding_generation

from .ic_memo import coverage_counts, coverage_sentence, truth_delta_signal
from .truth_delta_engine import TruthDeltaEngine, canonical_score
from .truth_delta_models import (
    ClaimedDatapoint, ExternalDataSource, ObservedDatapoint, TruthDeltaReport, claim_state_counts,
)
from .vector_models import DocumentSource

User = get_user_model()


def _stat(html, label):
    match = re.search(
        r'<div class="stat-value"[^>]*>\s*(\d+)\s*</div>\s*<div class="stat-label">' + re.escape(label) + '</div>',
        html,
    )
    return int(match.group(1)) if match else None


class ReportFixture:
    def make_people(self):
        _mock_embedding_generation(self)
        self.owner = User.objects.create_user('rc_owner', password='x')
        Application.objects.create(user=self.owner, company_name='CountCo', founder_name='F',
                                   email='rc@t.test', description='d', sector='Software', stage='Seed')
        self.investor = User.objects.create_user('rc_investor', password='x')
        InvestorApplication.objects.create(user=self.investor, full_name='I', company_name='Fund',
                                           email='rci@t.test', investment_focus='SaaS', investment_stage='Seed')
        self.doc = DocumentSource.objects.create(uploaded_by=self.owner, filename='deck.pdf',
                                                 source_entity='CountCo', document_type='pitch_deck',
                                                 status='analyzed')

    def page(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.doc.id]))
        self.assertEqual(response.status_code, 200)
        return response

    def api(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse('zelda_api:truth_delta_score', args=[self.doc.id]))
        self.assertEqual(response.status_code, 200)
        return response.json()


class SavedReportClaimCountTests(ReportFixture, TestCase):
    """A stored report shaped like report 87: three no-evidence claims, two categories."""

    CLAIMS = [('funding_raised', '$23.1M raised', 23.1e6), ('usage', '140 000+ bots', 140000),
              ('usage', '500M messages', 500e6)]

    def setUp(self):
        self.make_people()
        claims = [ClaimedDatapoint.objects.create(document=self.doc, category=c, claimed_value=v,
                                                  claimed_value_numeric=n) for c, v, n in self.CLAIMS]
        self.report = TruthDeltaReport.objects.create(
            document=self.doc, engine_version='td.5', overall_truth_score=None, credibility_risk='unknown',
            summary='No public data could be found to independently verify these claims.',
            details={
                'claims': [{'category': c.category, 'claimed_value': c.claimed_value} for c in claims],
                'observed': [],
                'comparison': [{'category': c.category, 'claim_id': c.pk, 'claimed_value_numeric': c.claimed_value_numeric,
                                'observed_value_numeric': None, 'claim_raw_text': c.claimed_value} for c in claims],
                'per_claim': [{'category': c.category, 'claim_id': c.pk, 'claimed': c.claimed_value,
                               'observed': 'No external data was found for this claim.'} for c in claims],
            },
        )

    def test_claim_counts_count_each_claim_while_categories_stay_categories(self):
        self.assertEqual(self.report.claim_stats(),
                         {'total': 3, 'verified': 0, 'contradicted': 0, 'no_data': 3})
        self.assertEqual(self.report.category_states(), {'funding_raised': 'no_data', 'usage': 'no_data'})
        self.assertEqual(self.report.verifiability_stats()['total'], 2)

    def test_truth_delta_page_counts_the_three_claim_rows(self):
        for user in (self.owner, self.investor):
            with self.subTest(user=user.username):
                response = self.page(user)
                html = response.content.decode()
                self.assertEqual(len(response.context['details']['per_claim']), 3)
                self.assertEqual(response.context['claims_analyzed'], 3)
                self.assertEqual(_stat(html, 'Claims Analyzed'), 3)
                self.assertEqual(_stat(html, 'Verified'), 0)
                self.assertEqual(_stat(html, 'Not established'), 3)
                self.assertRegex(html, r'claims_analyzed:\s*3,')
                self.assertIn('none of the 3 claims', response.context['coverage_sentence'])
                self.assertNotIn('none of the 2 claims', html)
                self.assertNotIn('Of the claim categories', html)

    def test_three_insufficient_evidence_claims_stay_unscored(self):
        response = self.page(self.investor)
        self.assertIsNone(response.context['truth_score'])
        self.assertEqual(response.context['credibility_risk'], 'unknown')
        self.assertEqual(canonical_score(self.report.verifiability_stats()), (None, 'unknown'))
        self.assertEqual(canonical_score(self.report.claim_stats()), (None, 'unknown'))
        self.assertIsNone(self.api(self.investor)['overall_truth_score'])

    def test_api_metadata_agrees_with_the_page(self):
        data = self.api(self.owner)
        self.assertEqual((data['claims_analyzed'], data['verified_count'], data['contradicted_count'],
                          data['unverified_count']), (3, 0, 0, 3))
        self.assertIn('none of the 3 claims', data['coverage_sentence'])
        self.assertEqual(len(data['details']['per_claim']), 3)
        # Categories stay available, labelled as categories.
        self.assertEqual(data['category_states'], {'funding_raised': 'no_data', 'usage': 'no_data'})

    def test_memo_counters_agree_with_each_other_and_the_page(self):
        signal = truth_delta_signal(self.doc)
        self.assertEqual(signal['claims_checked'], 3)
        self.assertEqual(signal['counts']['total'], 3)
        self.assertTrue(signal['coverage_line'].endswith('(of 3)'))
        self.assertIn('none of the 3 claims', signal['coverage_sentence'])

    def test_staff_ic_memo_renders_matching_counters(self):
        from .vector_models import IntelligenceMemo
        IntelligenceMemo.objects.create(document=self.doc, executive_summary='CountCo summary.',
                                        evidence_level='LITTLE_EVIDENCE', completeness_score=0.5,
                                        citations_count=1)
        staff = User.objects.create_user('rc_staff', password='x', is_staff=True)
        self.client.force_login(staff)
        html = self.client.get(reverse('zelda_api:ic_memo', args=[self.doc.id])).content.decode()
        self.assertRegex(html, r'Claims checked:</strong>\s*3')
        self.assertRegex(html, r'\(of 3\)')
        self.assertNotRegex(html, r'\(of 2\)')


class MultipleClaimsOneCategoryTests(TestCase):
    """Two revenue claims, one established and one not: a fresh engine run."""

    def setUp(self):
        self.owner = User.objects.create_user('rc_engine', password='x')
        self.doc = DocumentSource.objects.create(filename='c.txt', source_entity='Count Co',
                                                 uploaded_by=self.owner, document_type='pitch_deck')
        source = ExternalDataSource.objects.create(source_type='sec', source_name='SEC EDGAR')
        self.mismatched = self.claim('EUR')
        self.matching = self.claim('USD')
        observed = ObservedDatapoint.objects.create(
            document=self.doc, category='revenue', observed_value='1000000', observed_value_numeric=1e6,
            source=source, role='can_establish', source_credibility=.95, time_period='FY2025')
        observed.currency = 'USD'
        observed.save(update_fields=['currency'])
        with mock.patch('zelda_api.truth_delta_engine.data_source_manager.create_observed_datapoints'), \
             mock.patch('zelda_api.truth_delta_engine.data_source_manager.fetch_news_headlines', return_value=[]), \
             mock.patch('zelda_api.dataforb2b_adapter.observe', return_value='unconfigured'), \
             mock.patch.object(TruthDeltaEngine, '_call_claude_for_verification', return_value={'per_claim': []}):
            self.report = TruthDeltaEngine().verify_document(self.doc.id)

    def claim(self, currency):
        claim = ClaimedDatapoint.objects.create(document=self.doc, category='revenue',
                                                claimed_value=f'{currency} 1M', claimed_value_numeric=1e6)
        claim.currency = currency
        claim.save(update_fields=['currency'])
        return claim

    def test_category_aggregation_and_score_are_unchanged(self):
        self.assertEqual(self.report.category_states(), {'revenue': 'verified'})
        self.assertEqual(self.report.verifiability_stats()['total'], 1)
        # The score still comes from the category counts.
        self.assertEqual((self.report.overall_truth_score, self.report.credibility_risk), (100.0, 'low'))

    def test_each_claim_is_counted_in_its_own_state(self):
        rows = {row['claim_id']: row['state'] for row in self.report.per_claim_rows()}
        self.assertEqual(rows, {self.mismatched.pk: 'no_data', self.matching.pk: 'verified'})
        self.assertEqual(self.report.claim_stats(),
                         {'total': 2, 'verified': 1, 'contradicted': 0, 'no_data': 1})

    def test_new_report_summary_counts_claims(self):
        self.assertTrue(self.report.summary.startswith(
            '1 verified · 0 contradicted · 1 not established (of 2).'), self.report.summary)


class ZeroClaimTests(ReportFixture, TestCase):
    """Ben & Jerry's 3132 shape: analyzed, no claims extracted, no report."""

    def setUp(self):
        self.make_people()
        self.doc.verification_no_claims_at = timezone.now()
        self.doc.save(update_fields=['verification_no_claims_at'])

    def test_no_claims_state_is_preserved(self):
        response = self.page(self.investor)
        html = response.content.decode()
        self.assertTrue(response.context['verification_no_claims'])
        self.assertEqual(response.context['claims_analyzed'], 0)
        self.assertIsNone(response.context['truth_score'])
        self.assertIsNone(_stat(html, 'Claims Analyzed'))
        self.assertRegex(html, r'claims_analyzed:\s*0,')
        self.assertIsNone(truth_delta_signal(self.doc))

    def test_a_report_without_claims_counts_zero(self):
        report = TruthDeltaReport.objects.create(document=self.doc, engine_version='td.5', details={})
        self.assertEqual(report.claim_stats(), {'total': 0, 'verified': 0, 'contradicted': 0, 'no_data': 0})
        self.assertEqual(coverage_sentence(coverage_counts(report.claim_stats())),
                         "None of the deck's claims had a public source to check against.")
        self.assertEqual(claim_state_counts([]), report.claim_stats())


class VerifiedAndContradictedOneCategoryTests(TestCase):
    """
    One category, one claim verified and one contradicted. The category is
    verified, so the category-count score is 100; a per-claim score would be
    50. The score must stay on the category counts (formula unchanged), while
    the claim labels count both claims.
    """

    def setUp(self):
        from datetime import date
        owner = User.objects.create_user('rc_mixed', password='x')
        self.doc = DocumentSource.objects.create(filename='n.txt', source_entity='Nike', uploaded_by=owner,
                                                 document_type='pitch_deck')
        source = ExternalDataSource.objects.create(source_type='sec', source_name='SEC EDGAR')
        for value in (46398000000, 52800000000):        # matches FY2026 10-K / diverges from it
            ClaimedDatapoint.objects.create(
                document=self.doc, category='revenue', claimed_value=f'USD {value}', claimed_value_numeric=value,
                currency='USD', period_kind='annual', period_fiscal_year=2026)
        ObservedDatapoint.objects.create(
            document=self.doc, category='revenue', observed_value='46398000000',
            observed_value_numeric=46398000000, source=source, role='can_establish', source_credibility=.95,
            currency='USD', time_period='FY2026 10-K', period_kind='annual', period_fiscal_year=2026,
            period_end=date(2026, 5, 31))
        with mock.patch('zelda_api.truth_delta_engine.data_source_manager.create_observed_datapoints'), \
             mock.patch('zelda_api.truth_delta_engine.data_source_manager.fetch_news_headlines', return_value=[]), \
             mock.patch('zelda_api.dataforb2b_adapter.observe', return_value='unconfigured'), \
             mock.patch.object(TruthDeltaEngine, '_call_claude_for_verification', return_value={'per_claim': []}):
            self.report = TruthDeltaEngine().verify_document(self.doc.id)

    def test_score_stays_on_category_counts_while_labels_count_claims(self):
        self.assertEqual(sorted(row['state'] for row in self.report.per_claim_rows()), ['contradicted', 'verified'])
        self.assertEqual(self.report.category_states(), {'revenue': 'verified'})
        self.assertEqual((self.report.overall_truth_score, self.report.credibility_risk), (100.0, 'low'))
        self.assertEqual(self.report.claim_stats(),
                         {'total': 2, 'verified': 1, 'contradicted': 1, 'no_data': 0})
        self.assertTrue(self.report.summary.startswith(
            '1 verified · 1 contradicted · 0 not established (of 2).'), self.report.summary)
