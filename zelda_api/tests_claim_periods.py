"""
Claim periods, and the comparison gate they open.

Until now no claim carried a period, so every disagreement ended as
period_unknown and `contradicted` was unreachable. Attaching periods is the
change that makes it reachable, so the evidence principles require the
comparability rule to be defined and its failure edges tested FIRST
(docs: project evidence principle 4, "contradiction has an admission gate").

The expectations in zelda_api/data/claim_periods/ were frozen before the code:
the period phrases, the frozen decks, the comparison matrix, and two recorded
EDGAR payloads (Nike FY2026, the answer key's C01; Apple FY2020, where a 90-day
Q4 row shares the full year's end date). See expectations.json "decisions".
"""
import copy
import json
from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from .truth_delta_engine import TruthDeltaEngine
from .truth_delta_models import (
    TRUTH_DELTA_SEMANTICS, ClaimedDatapoint, ExternalDataSource, ObservedDatapoint, TruthDeltaReport,
)
from .truth_delta_sources import SECFilingsIntegration
from .vector_models import DocumentSource

DATA = Path(__file__).parent / 'data' / 'claim_periods'
EXPECTED = json.loads((DATA / 'expectations.json').read_text(encoding='utf-8'))


def edgar(name):
    return json.loads((DATA / f'{name}.json').read_text(encoding='utf-8'))


def as_date(value):
    return date.fromisoformat(value) if value else None


class ClaimPeriodPhraseTests(SimpleTestCase):
    """The frozen phrase inventory: kind, fiscal year and end date, or nothing."""

    def test_frozen_phrases(self):
        from .claim_periods import claim_period
        for case in EXPECTED['phrases']:
            with self.subTest(text=case['text']):
                period = claim_period(case['text'])
                self.assertEqual(
                    (period.kind, period.fiscal_year, period.period_end),
                    (case['kind'], case['fiscal_year'], as_date(case['period_end'])), case['why'])

    def test_a_fiscal_year_never_becomes_a_december_end_date(self):
        from .claim_periods import claim_period
        for text in ('FY2024 revenue of $5.2M', 'Fiscal 2025 sales were $46.3B'):
            with self.subTest(text=text):
                self.assertIsNone(claim_period(text).period_end)

    def test_the_raw_phrase_is_kept_when_a_period_attaches(self):
        from .claim_periods import claim_period
        self.assertIn('FY2024', claim_period('FY2024 revenue of $5.2M').phrase)
        self.assertEqual(claim_period('Revenue was $5M').phrase, '')


class SecFullYearSelectionTests(SimpleTestCase):
    """The observed side: a full fiscal year, labelled by the filer's own filing."""

    def test_the_q4_row_sharing_the_year_end_is_never_chosen_in_either_order(self):
        sec = SECFilingsIntegration()
        payload = edgar('edgar_apple_fy2020_revenue')
        for order in ('as served', 'quarter first'):
            data = copy.deepcopy(payload)
            rows = next(iter(data['facts']['us-gaap'].values()))['units']['USD']
            if order == 'quarter first':
                rows.sort(key=lambda r: (date.fromisoformat(r['end']) - date.fromisoformat(r['start'])).days)
            with self.subTest(order=order):
                fact = sec._latest_annual_fact(data, sec.REVENUE_TAGS)
                self.assertEqual((fact['start'], fact['end'], fact['val']), ('2019-09-29', '2020-09-26', 274515000000))

    def test_the_observed_period_uses_the_filers_own_fiscal_year_label(self):
        sec = SECFilingsIntegration()
        for key in ('nike_fy2026', 'apple_fy2020'):
            spec = EXPECTED['observed'][key]
            with self.subTest(key=key):
                period = sec.extract_period(edgar(spec['fixture']))
                self.assertEqual(
                    (period['kind'], period['fiscal_year'], period['period_end']),
                    (spec['kind'], spec['fiscal_year'], as_date(spec['period_end'])))

    def test_a_restated_prior_year_keeps_its_original_fiscal_year_label(self):
        # Nike's FY2025 row also appears in the FY2026 10-K with fy 2026.
        sec = SECFilingsIntegration()
        data = edgar('edgar_nike_fy2026_revenue')
        rows = next(iter(data['facts']['us-gaap'].values()))['units']['USD']
        rows[:] = [r for r in rows if r['end'] == '2025-05-31']
        self.assertEqual(sec.extract_period(data)['fiscal_year'], 2025)


class PeriodComparisonTests(TestCase):
    """The frozen comparison matrix, through the real comparison builder and report states."""

    def setUp(self):
        owner = get_user_model().objects.create_user('period_verify', password='x')
        self.doc = DocumentSource.objects.create(filename='p.txt', source_entity='Nike', uploaded_by=owner,
                                                 document_type='pitch_deck')
        self.source = ExternalDataSource.objects.create(source_type='sec', source_name='SEC EDGAR')

    def pair(self, claim_spec, observed_key, claimed):
        spec = EXPECTED['observed'][observed_key]
        claim = ClaimedDatapoint.objects.create(
            document=self.doc, category='revenue', claimed_value=f'${claimed}', claimed_value_numeric=claimed,
            currency='USD', period_kind=claim_spec.get('kind', ''),
            period_fiscal_year=claim_spec.get('fiscal_year'), period_end=as_date(claim_spec.get('period_end')))
        observed = ObservedDatapoint.objects.create(
            document=self.doc, category='revenue', observed_value=str(spec['value']),
            observed_value_numeric=spec['value'], source=self.source, role='can_establish',
            source_credibility=.95, currency='USD', time_period='FY2026 10-K',
            period_kind=spec['kind'], period_fiscal_year=spec['fiscal_year'], period_end=as_date(spec['period_end']))
        return TruthDeltaEngine()._build_comparison([claim], [observed])

    def test_frozen_comparison_matrix_under_current_semantics(self):
        self.assertNotEqual(TRUTH_DELTA_SEMANTICS, 'td.4', 'new comparison rules need a new semantics version')
        for case in EXPECTED['comparisons']:
            with self.subTest(case=case['name']):
                rows = self.pair(case['claim'], case['observed'], case['claimed'])
                report = TruthDeltaReport(engine_version=TRUTH_DELTA_SEMANTICS, details={'comparison': rows})
                self.assertEqual(report.category_states()['revenue'], case['state'])
                self.assertEqual(report.grounding_reasons().get('revenue'), case['reason'])

    def test_historical_reports_keep_their_recorded_rules(self):
        # Under td.4 an agreeing figure verified whatever the claim's period said.
        rows = self.pair({'kind': 'annual', 'fiscal_year': 2025}, 'nike_fy2026', 46400000000)
        historical = TruthDeltaReport(engine_version='td.4', details={'comparison': rows})
        self.assertEqual(historical.category_states()['revenue'], 'verified')
        current = TruthDeltaReport(engine_version=TRUTH_DELTA_SEMANTICS, details={'comparison': rows})
        self.assertEqual(current.grounding_reasons()['revenue'], 'period_mismatch')  # control

    def test_comparison_rows_carry_both_structured_periods(self):
        row = self.pair({'kind': 'annual', 'fiscal_year': 2026}, 'nike_fy2026', 52800000000)[0]
        self.assertEqual((row['claim_period_kind'], row['claim_fiscal_year'], row['claim_period_end']),
                         ('annual', 2026, None))
        self.assertEqual((row['observed_period_kind'], row['observed_fiscal_year'], row['observed_period_end']),
                         ('annual', 2026, '2026-05-31'))


class FrozenDeckPeriodTests(TestCase):
    """Real extraction over the frozen decks: no period attaches, by design (B2)."""

    def test_frozen_decks_attach_no_periods(self):
        from .tests_claim_extraction_recall import FrozenDeckExtractionTests
        harness = FrozenDeckExtractionTests()
        harness.setUp()
        for name, key in (('manychat', 'manychat'), ('ben_jerrys', 'ben_jerrys')):
            spec = EXPECTED['frozen_decks'][key]
            with self.subTest(deck=name):
                _, claims = harness.extract(name)
                self.assertEqual(len(claims), spec['claims'])
                self.assertEqual(sum(bool(c.period_kind) for c in claims), spec['with_period'], spec['why'])

    def test_a_same_sentence_period_reaches_the_stored_claim(self):
        from unittest import mock
        from . import truth_delta_tasks
        from .vector_models import DocumentChunk, IntelligenceInsight
        owner = get_user_model().objects.create_user('period_extract', password='x')
        doc = DocumentSource.objects.create(filename='n.pptx', source_entity='Nike', uploaded_by=owner,
                                            document_type='pitch_deck')
        text = 'FY2026 revenue reached USD 52.8 billion'
        chunk = DocumentChunk.objects.create(document=doc, chunk_index=0, page_number=2, section_title='',
                                             raw_text=text, token_count=10)
        insight = IntelligenceInsight.objects.create(document=doc, insight_type='statement', category='Revenue',
                                                     insight_text=text, confidence_score=80)
        insight.source_chunks.set([chunk])
        with mock.patch.object(truth_delta_tasks.verify_document_truth_delta, 'delay'):
            truth_delta_tasks.extract_claims_from_insights(doc.id)
        claim = ClaimedDatapoint.objects.get(document=doc)
        self.assertEqual((claim.period_kind, claim.period_fiscal_year, claim.period_end), ('annual', 2026, None))
        self.assertIn('FY2026', claim.time_period)
