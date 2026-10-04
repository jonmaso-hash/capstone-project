"""
R-003: the model may explain Zelda's verdict; it may not create, alter or
contradict it.

Nike rerun, report 80: the canonical state was revenue no_data/period_unknown
and 0 of 2 verified, while the stored summary -- written by the model, which
had been shown the 13.8% gap but not the state -- said "materially overstated
... a significant red flag". Every test here stubs the model to say the wrong
thing on purpose, once per canonical outcome, and checks that what is STORED
and SERVED follows the state anyway. A test where the model happened to agree
would prove nothing.

The model is stubbed at `_call_claude_for_verification`; the SEC source is a
fake integration; the grounding rules are real. For `contradicted` the only
help given is a comparable period on the real comparison rows, because claims
carry no period yet (L-007) and nothing else in the pipeline can produce one.
"""
import re
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.models import Application
from matchmaking.tests import _mock_embedding_generation
from zelda_api import truth_delta_narrative as narrative
from zelda_api.source_capabilities import CAN_CORROBORATE, LINKEDIN_DERIVED
from zelda_api.truth_delta_engine import TruthDeltaEngine
from zelda_api.truth_delta_models import (
    TRUTH_DELTA_SEMANTICS, ClaimedDatapoint, ExternalDataSource, ObservedDatapoint)
from zelda_api.truth_delta_sources import DataSourceManager
from zelda_api.vector_models import DocumentSource

CONTRADICTION_WORDS = re.compile(r'overstat|red flag|contradict|inaccura|inflat', re.I)
# The model's affirmative phrasings. Canonical text may say "could not be confirmed".
VERIFICATION_WORDS = re.compile(r'verified by|confirmed by|headcount confirmed|funding verified|consistent with', re.I)
MODEL_SUMMARY = 'MODEL SUMMARY: the revenue claim is materially overstated, a significant red flag.'


def fake_sec(revenue, period='FY2026 10-K (period ending 2026-05-31)'):
    class FakeSEC:
        source_name = 'SEC EDGAR'
        source_type = 'sec'
        last_failure_reason = None

        def authenticate(self):
            return True

        def fetch_company_data(self, company_name, domain=None):
            return {'_cik': '0000320187'} if revenue is not None else {}

        def extract_time_period(self, data):
            return period

        def extract_revenue(self, data):
            return (revenue, '$')

        def extract_customers(self, data):
            return None

        def extract_employees(self, data):
            return None

        def extract_funding(self, data):
            return None
    return FakeSEC


def model_says(per_claim, summary=MODEL_SUMMARY, score=42.0):
    return {'overall_truth_score': score, 'credibility_risk': 'high', 'summary': summary,
            'per_claim': per_claim}


class _Verify(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.user = get_user_model().objects.create_user('r003_owner', password='x')
        Application.objects.create(user=self.user, company_name='NIKE, Inc.', founder_name='F',
                                   email='r@t.test', description='d', sector='Retail', stage='Public')
        self.doc = DocumentSource.objects.create(
            filename='nike.pptx', source_entity='NIKE, Inc.', uploaded_by=self.user,
            document_type='pitch_deck', status='analyzed')

    def claim(self, category, value, numeric, page=3):
        return ClaimedDatapoint.objects.create(
            document=self.doc, category=category, claimed_value=value, claimed_value_numeric=numeric,
            page_number=page, chunk_hash='h', confidence_in_extraction=95.0)

    def verify(self, model_result, revenue=None, headlines=(), comparable_period=False):
        patches = [
            mock.patch.object(DataSourceManager, 'INTEGRATIONS', {'sec': fake_sec(revenue)}),
            mock.patch.object(DataSourceManager, 'fetch_news_headlines', return_value=list(headlines)),
            mock.patch.object(TruthDeltaEngine, '_call_claude_for_verification', return_value=model_result),
            mock.patch('zelda_api.dataforb2b_adapter.observe', return_value='unconfigured'),
        ]
        if comparable_period:
            real = TruthDeltaEngine._build_comparison

            def with_period(engine, claims, observed):
                rows = real(engine, claims, observed)
                for row in rows:
                    row['claim_period'] = row.get('observed_time_period')
                return rows
            patches.append(mock.patch.object(TruthDeltaEngine, '_build_comparison', with_period))
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.report = TruthDeltaEngine().verify_document(self.doc.id)
        return self.report

    def rows(self):
        return {row['category']: row for row in self.report.details['per_claim']}

    def assertNoContradictionLanguage(self, text):
        self.assertIsNone(CONTRADICTION_WORDS.search(text), text)

    def assertModelSummaryNotStored(self):
        self.assertNotIn('MODEL SUMMARY', self.report.summary)


class EachCanonicalOutcomeWinsOverTheModelTests(_Verify):

    def test_verified_the_model_calls_it_overstated(self):
        self.claim('revenue', '$46.4 billion', 46.4e9)
        self.verify(model_says([{'category': 'revenue', 'assessment': 'Materially overstated versus the 10-K.'}]),
                    revenue=46.398e9)
        self.assertEqual(self.report.category_states(), {'revenue': 'verified'})
        self.assertModelSummaryNotStored()
        self.assertNoContradictionLanguage(self.report.summary)
        self.assertIn('1 of 1 checkable claim verified', self.report.summary)
        row = self.rows()['revenue']
        self.assertEqual(row['explanation_source'], 'zelda')
        self.assertNoContradictionLanguage(row['assessment'])

    def test_contradicted_the_model_calls_it_consistent(self):
        self.claim('revenue', '$80 billion', 80e9)
        self.verify(model_says([{'category': 'revenue', 'assessment': 'The claim is consistent with SEC data.'}],
                               summary='MODEL SUMMARY: the figures are consistent with SEC data.'),
                    revenue=46.398e9, comparable_period=True)
        self.assertEqual(self.report.category_states(), {'revenue': 'contradicted'})
        self.assertModelSummaryNotStored()
        self.assertIn('1 contradicted', self.report.summary)
        self.assertIsNone(VERIFICATION_WORDS.search(self.report.summary), self.report.summary)
        row = self.rows()['revenue']
        self.assertEqual(row['explanation_source'], 'zelda')
        self.assertIn('Differs from', row['assessment'])

    def test_period_unknown_the_model_calls_it_a_red_flag(self):
        # The Nike case.
        self.claim('revenue', '$52.8 billion', 52.8e9)
        self.claim('employees', '81,500 people worldwide', 81500.0, page=6)
        self.verify(model_says([
            {'category': 'revenue', 'assessment': 'A material and unexplained overstatement - a red flag.'},
            {'category': 'employees', 'assessment': 'No independent data was available.'},
        ]), revenue=46.398e9)
        self.assertEqual(self.report.category_states(), {'revenue': 'no_data', 'employees': 'no_data'})
        self.assertEqual(self.report.grounding_reasons()['revenue'], 'period_unknown')
        self.assertModelSummaryNotStored()
        self.assertNoContradictionLanguage(self.report.summary)
        self.assertIn('0 of 2 checkable claims verified', self.report.summary)
        self.assertIn('$46.4 billion', self.report.summary)
        self.assertIn('could not be compared', self.report.summary)
        rows = self.rows()
        self.assertEqual(rows['revenue']['assessment'], narrative.REASON_SENTENCES['period_unknown'])
        self.assertEqual(rows['revenue']['explanation_source'], 'zelda')

    def test_no_external_evidence_the_model_calls_it_confirmed(self):
        # Headlines exist, so the model is consulted although nothing establishing was found.
        self.claim('employees', '81,500 people worldwide', 81500.0, page=6)
        self.verify(model_says([{'category': 'employees', 'assessment': 'Confirmed by public data.'}],
                               summary='MODEL SUMMARY: headcount confirmed.'),
                    revenue=None, headlines=['Nike hires'])
        self.assertEqual(self.report.grounding_reasons(), {'employees': 'no_external_evidence'})
        self.assertModelSummaryNotStored()
        self.assertIsNone(VERIFICATION_WORDS.search(self.report.summary), self.report.summary)
        self.assertIn('context only', self.report.summary)
        row = self.rows()['employees']
        self.assertEqual(row['assessment'], narrative.REASON_SENTENCES['no_external_evidence'])

    def test_corroboration_only_the_model_calls_it_verified(self):
        self.claim('funding_raised', '$865 million', 865e6)
        source, _ = ExternalDataSource.objects.get_or_create(
            source_type='dataforb2b', defaults={'source_name': 'DataForB2B'})
        ObservedDatapoint.objects.create(
            document=self.doc, category='funding_raised', observed_value='$865,000,000',
            observed_value_numeric=865e6, source=source, role=CAN_CORROBORATE, evidence_origin=LINKEDIN_DERIVED)
        self.verify(model_says([{'category': 'funding_raised', 'assessment': 'Verified by LinkedIn data.'}],
                               summary='MODEL SUMMARY: funding verified.'),
                    revenue=None, headlines=['Nike raises'])
        self.assertEqual(self.report.grounding_reasons(), {'funding_raised': 'corroboration_only'})
        self.assertModelSummaryNotStored()
        self.assertIsNone(VERIFICATION_WORDS.search(self.report.summary), self.report.summary)
        row = self.rows()['funding_raised']
        self.assertEqual(row['assessment'], narrative.REASON_SENTENCES['corroboration_only'])
        self.assertEqual(row['observed'], 'Lower-authority data only')


class AnExplanationThatAgreesIsKeptTests(_Verify):
    """Positive control: the guard refuses verdicts, not explanations."""

    def test_an_agreeing_explanation_survives(self):
        self.claim('revenue', '$52.8 billion', 52.8e9)
        honest = 'The deck gives no period for this figure, so it could not be verified against the 10-K.'
        self.verify(model_says([{'category': 'revenue', 'assessment': honest}]), revenue=46.398e9)
        row = self.rows()['revenue']
        self.assertEqual((row['assessment'], row['explanation_source']), (honest, 'model'))

    def test_corroboration_may_be_described_as_consistent(self):
        self.assertTrue(narrative.explanation_consistent(
            'LinkedIn-derived data is consistent with the claim.', 'no_data', 'corroboration_only'))
        self.assertFalse(narrative.explanation_consistent(
            'LinkedIn-derived data confirms the claim.', 'no_data', 'corroboration_only'))


class TheModelCannotShapeTheTableTests(_Verify):

    def test_rows_are_the_comparison_rows_not_the_models_list(self):
        self.claim('revenue', '$52.8 billion', 52.8e9)
        self.claim('employees', '81,500 people worldwide', 81500.0, page=6)
        self.verify(model_says([
            # Drops employees, invents customers.
            {'category': 'revenue', 'assessment': 'No period is stated.', 'observed': '$99 trillion (made up)'},
            {'category': 'customers', 'assessment': 'Confirmed 2 million customers.'},
        ]), revenue=46.398e9)
        rows = self.rows()
        self.assertEqual(set(rows), {'revenue', 'employees'})
        self.assertEqual(rows['revenue']['observed'], '$46.4 billion (SEC EDGAR, FY2026 10-K (period ending 2026-05-31))')
        self.assertEqual(rows['employees']['observed'], 'No external data found')

    def test_the_report_is_stamped_with_the_new_semantics(self):
        self.claim('revenue', '$52.8 billion', 52.8e9)
        self.verify(model_says([]), revenue=46.398e9)
        self.assertEqual(self.report.engine_version, TRUTH_DELTA_SEMANTICS)
        self.assertIn(TRUTH_DELTA_SEMANTICS, ('td.2', 'td.3'))   # td.3 = R-003b, which keeps R-003

    def test_the_models_score_is_not_stored(self):
        # R-003b: the score is Zelda's too (zelda_api/tests_score_follows_verdict.py).
        self.claim('revenue', '$52.8 billion', 52.8e9)
        self.verify(model_says([], score=42.0), revenue=46.398e9)
        self.assertEqual((self.report.overall_truth_score, self.report.credibility_risk), (None, 'unknown'))

    def test_the_numeric_fallback_also_writes_canonical_rows(self):
        self.claim('revenue', '$52.8 billion', 52.8e9)
        self.verify(None, revenue=46.398e9)
        self.assertNoContradictionLanguage(self.report.summary)
        self.assertEqual(self.rows()['revenue']['assessment'], narrative.REASON_SENTENCES['period_unknown'])


class TheServedReportFollowsTheVerdictTests(_Verify):

    def test_the_api_and_page_serve_the_canonical_summary(self):
        self.claim('revenue', '$52.8 billion', 52.8e9)
        self.verify(model_says([{'category': 'revenue', 'assessment': 'A significant red flag.'}]),
                    revenue=46.398e9)
        self.client.force_login(self.user)
        payload = self.client.get(reverse('zelda_api:truth_delta_score', args=[self.doc.id])).json()
        self.assertNoContradictionLanguage(payload['summary'])
        for row in payload['details']['per_claim']:
            self.assertNoContradictionLanguage(row['assessment'])
        page = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.doc.id]))
        self.assertNoContradictionLanguage(page.context['summary'] if 'summary' in page.context else '')
        self.assertNotIn('red flag', page.content.decode().lower())
