"""Frozen currency contract, with controls proving the comparison gate can fail."""
import json
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from .financial_metrics import currency_value
from .truth_delta_engine import TruthDeltaEngine, canonical_score
from .truth_delta_models import (
    TRUTH_DELTA_SEMANTICS, ClaimedDatapoint, ExternalDataSource, ObservedDatapoint, TruthDeltaReport,
)
from .vector_models import DocumentSource, DocumentChunk

EXPECTED = json.loads((Path(__file__).parent / 'data/claim_currency/expectations.json').read_text(encoding='utf-8'))


class CurrencyAmountTests(SimpleTestCase):
    def test_frozen_amounts_keep_values_and_currency(self):
        from .financial_metrics import currency_amount
        for text, value, currency in EXPECTED['amounts']:
            with self.subTest(text=text):
                amount = currency_amount(text)
                self.assertEqual(currency_value(text), value)
                self.assertEqual(amount, (value, currency))

    def test_euro_billion_is_not_lost_or_read_as_7_point_9(self):
        self.assertEqual(currency_value('Unilever generated €7.9bn in 2024 sales'), 7.9e9)

    def test_a_currency_from_another_amount_cannot_qualify_a_bare_dollar(self):
        from .financial_metrics import currency_amount
        self.assertEqual(currency_amount('$1M revenue; EUR 9M market size'), (1e6, ''))


class CurrencyExtractionTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('currency_owner', password='x')

    def extract(self, text, name='Currency Co'):
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .truth_delta_tasks import extract_claims_from_insights
        doc = DocumentSource.objects.create(filename='currency.txt', source_entity=name,
                                            uploaded_by=self.owner, document_type='pitch_deck')
        DocumentChunk.objects.create(document=doc, chunk_index=0, page_number=3,
                                     raw_text=text, token_count=50)
        ZeldaIntelligencePipelineV2()._analyze_document(doc, '')
        with mock.patch('zelda_api.truth_delta_tasks.verify_document_truth_delta.delay'):
            result = extract_claims_from_insights(doc.id)
        self.assertEqual(result['status'], 'success')
        return doc, list(ClaimedDatapoint.objects.filter(document=doc).order_by('id'))

    def test_real_pipeline_preserves_euro_and_pound_amounts_without_inventing_periods(self):
        # Since claim periods (td.5), "annually" in the claim's own sentence is
        # an annual basis; currency never adds or removes a period.
        for text, value, code, period in [('Our revenue is €7.9bn annually', 7.9e9, 'EUR', ('annually', 'annual')),
                                          ('Our revenue is £2.4 million', 2.4e6, 'GBP', ('', ''))]:
            with self.subTest(text=text):
                _, claims = self.extract(text)
                self.assertEqual(len(claims), 1)
                claim = claims[0]
                claim.refresh_from_db()
                self.assertEqual((claim.category, claim.claimed_value_numeric, getattr(claim, 'currency', None)),
                                 ('revenue', value, code))
                self.assertEqual((claim.time_period, claim.period_kind), period)
                self.assertIn(claim.claimed_value, text)
                self.assertEqual(claim.page_number, 3)

    def test_prefixes_survive_source_binding_and_bare_dollar_stays_unknown(self):
        for prefix, code in [('US$', 'USD'), ('USD ', 'USD'), ('C$', 'CAD'), ('A$', 'AUD'), ('$', '')]:
            with self.subTest(prefix=prefix):
                text = f'Our revenue is {prefix}1.2M'
                _, claims = self.extract(text)
                self.assertEqual(len(claims), 1)
                self.assertEqual(getattr(claims[0], 'currency', None), code)
                self.assertTrue(claims[0].claimed_value.startswith(prefix))

    def test_equal_numbers_in_different_currencies_are_not_deduplicated(self):
        _, claims = self.extract('Revenue is EUR 1M. Revenue is USD 1M.')
        self.assertEqual(sorted((c.claimed_value_numeric, getattr(c, 'currency', None)) for c in claims),
                         [(1e6, 'EUR'), (1e6, 'USD')])

    def test_currency_does_not_borrow_the_nearby_market_figure(self):
        _, claims = self.extract('The addressable market is EUR 9M and our revenue is GBP 2M')
        money = {c.category: (c.claimed_value_numeric, getattr(c, 'currency', None)) for c in claims}
        self.assertEqual(money, {'revenue': (2e6, 'GBP'), 'market_size': (9e6, 'EUR')})

    def test_frozen_decks_keep_their_claims_categories_source_spans_and_negatives(self):
        from .tests_claim_extraction_recall import load_fixture, FrozenDeckExtractionTests
        harness = FrozenDeckExtractionTests()
        harness.user, harness.DocumentSource = self.owner, DocumentSource
        for name, spec in EXPECTED['decks'].items():
            with self.subTest(deck=name):
                fixture, claims = harness.extract(name)
                self.assertEqual(len(claims), spec['claim_count'])
                actual = sorted((c.category, c.claimed_value_numeric, c.unit, c.page_number, c.claimed_value)
                                for c in claims)
                expected = sorted((c['category'], c['value'], c['unit'], c['page'], c['claimed_value'])
                                  for c in load_fixture(name)['expected_claims'])
                self.assertEqual(actual, expected)
                for c in claims:
                    self.assertEqual(getattr(c, 'currency', None), '')
                    self.assertEqual(c.time_period, '')
                harness.assert_sources(fixture, claims)
                harness.assert_negatives(fixture, claims)


class CurrencyComparisonTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('currency_verify', password='x')
        self.doc = DocumentSource.objects.create(filename='c.txt', source_entity='Currency Co',
                                                 uploaded_by=self.owner, document_type='pitch_deck')
        self.source = ExternalDataSource.objects.create(source_type='sec', source_name='SEC EDGAR')

    def claim(self, currency='EUR', category='revenue', value=1e6):
        c = ClaimedDatapoint.objects.create(document=self.doc, category=category,
                                           claimed_value=f'{currency or "$"} {value}',
                                           claimed_value_numeric=value)
        c.currency = currency
        if 'currency' in {f.name for f in c._meta.fields}:
            c.save(update_fields=['currency'])
        return c

    def observed(self, currency='USD', category='revenue', value=1e6, role='can_establish', credibility=.95):
        o = ObservedDatapoint.objects.create(document=self.doc, category=category, observed_value=str(value),
                                             observed_value_numeric=value, source=self.source,
                                             role=role, source_credibility=credibility, time_period='FY2025')
        o.currency = currency
        if 'currency' in {f.name for f in o._meta.fields}:
            o.save(update_fields=['currency'])
        return o

    def report(self, claim, *observations, period=False):
        rows = TruthDeltaEngine()._build_comparison([claim], list(observations))
        if period:
            rows[0]['claim_period'] = 'FY2025'
        return rows[0], TruthDeltaReport(engine_version='td.4', details={'comparison': rows})

    def test_same_number_in_different_currencies_never_verifies(self):
        row, report = self.report(self.claim(), self.observed())
        self.assertEqual(report.category_states(), {'revenue': 'no_data'})
        self.assertEqual(report.grounding_reasons(), {'revenue': 'currency_mismatch'})
        self.assertIsNone(row['discrepancy_pct'])
        self.assertEqual(canonical_score(report.verifiability_stats()), (None, 'unknown'))

    def test_different_numbers_and_matching_periods_never_contradict_across_currencies(self):
        row, report = self.report(self.claim(value=9e6), self.observed(), period=True)
        self.assertEqual(report.grounding_reasons(), {'revenue': 'currency_mismatch'})
        self.assertEqual(report.category_states()['revenue'], 'no_data')
        self.assertIsNone(row['discrepancy_pct'])

    def test_either_missing_currency_blocks_all_money_categories(self):
        for category in ('revenue', 'arr', 'funding_raised', 'market_size'):
            for a, b in [('', 'USD'), ('USD', ''), ('', '')]:
                with self.subTest(category=category, currencies=(a, b)):
                    row, report = self.report(self.claim(a, category), self.observed(b, category))
                    self.assertEqual(report.grounding_reasons(), {category: 'currency_unknown'})
                    self.assertEqual(report.category_states()[category], 'no_data')
                    self.assertIsNone(row['discrepancy_pct'])

    def test_matching_known_currencies_still_verify(self):
        for currency in ('EUR', 'GBP', 'USD', 'CAD', 'AUD'):
            with self.subTest(currency=currency):
                _, report = self.report(self.claim(currency), self.observed(currency))
                self.assertEqual(report.category_states()['revenue'], 'verified')

    def test_matching_currency_keeps_existing_period_and_contradiction_gates(self):
        c, o = self.claim(value=9e6), self.observed('EUR')
        _, missing_period = self.report(c, o)
        self.assertEqual(missing_period.grounding_reasons(), {'revenue': 'period_unknown'})
        _, same_period = self.report(c, o, period=True)
        self.assertEqual(same_period.category_states()['revenue'], 'contradicted')

    def test_currency_does_not_block_a_count(self):
        row, report = self.report(self.claim('', 'employees', 100), self.observed('', 'employees', 100))
        self.assertEqual(report.category_states()['employees'], 'verified')
        self.assertEqual(row['discrepancy_pct'], 0)

    def test_compatible_evidence_is_not_shadowed_by_a_higher_credibility_other_currency(self):
        row, report = self.report(self.claim(), self.observed('USD'), self.observed('EUR', credibility=.9))
        self.assertEqual(report.category_states()['revenue'], 'verified')
        self.assertEqual(row.get('observed_currency'), 'EUR')

    def test_corroboration_cannot_assert_agreement_or_gap_across_currencies(self):
        c = self.claim()
        a = TruthDeltaEngine._corroboration_entry(c, self.observed(role='can_corroborate'), None)
        b = TruthDeltaEngine._corroboration_entry(c, self.observed('EUR', role='can_corroborate'), None)
        self.assertIsNone(a['agrees'])
        self.assertIsNone(a['discrepancy_pct'])
        self.assertEqual(a.get('comparison_reason'), 'currency_mismatch')
        self.assertTrue(b['agrees'])

    def test_model_prose_cannot_override_currency_gate_and_currency_reaches_memo_context(self):
        from .grounded_context import _claim_items
        self.claim()
        self.observed()
        with mock.patch('zelda_api.truth_delta_engine.data_source_manager.create_observed_datapoints'), \
             mock.patch('zelda_api.truth_delta_engine.data_source_manager.fetch_news_headlines', return_value=[]), \
             mock.patch('zelda_api.dataforb2b_adapter.observe', return_value='unconfigured'), \
             mock.patch.object(TruthDeltaEngine, '_call_claude_for_verification', return_value={
                 'per_claim': [{'category': 'revenue', 'assessment': 'Verified by SEC.'}]}):
            report = TruthDeltaEngine().verify_document(self.doc.id)
        self.assertEqual(report.grounding_reasons(), {'revenue': 'currency_mismatch'})
        self.assertEqual((report.overall_truth_score, report.credibility_risk), (None, 'unknown'))
        self.assertEqual(report.engine_version, TRUTH_DELTA_SEMANTICS)
        self.assertEqual(report.details['per_claim'][0]['explanation_source'], 'zelda')
        items = _claim_items(self.doc, list(self.doc.claimed_datapoints.all()), report)
        self.assertEqual(getattr(items[0], 'currency', None), 'EUR')
        self.assertEqual(getattr(items[0].external[0], 'currency', None), 'USD')

    def test_blank_legacy_input_rows_are_unknown_on_new_verification(self):
        _, report = self.report(self.claim(''), self.observed(''))
        self.assertEqual(report.grounding_reasons(), {'revenue': 'currency_unknown'})

    def test_historical_report_rules_are_preserved_and_identified_as_historical(self):
        report = TruthDeltaReport(engine_version='td.3', details={'comparison': [{
            'category': 'revenue', 'claimed_value_numeric': 1e6, 'observed_value_numeric': 1e6}]})
        self.assertEqual(report.category_states()['revenue'], 'verified')
        self.assertTrue(report.predates_current_semantics)

    def test_currency_gate_is_enforced_for_new_rows_without_a_semantics_stamp(self):
        row, _ = self.report(self.claim(), self.observed())
        report = TruthDeltaReport(details={'comparison': [row]})
        self.assertEqual(report.grounding_reasons(), {'revenue': 'currency_mismatch'})

    def test_new_semantics_cannot_use_the_historical_existence_only_fallback(self):
        report = TruthDeltaReport(engine_version='td.4', details={
            'claims': [{'category': 'revenue'}],
            'observed': [{'category': 'revenue', 'observed_value': '1000000'}]})
        self.assertEqual(report.category_states(), {'revenue': 'no_data'})
        self.assertEqual(report.grounding_reasons(), {'revenue': 'currency_unknown'})

    def test_rendering_does_not_relabel_a_euro_observation_as_dollars(self):
        from .truth_delta_narrative import observed_text
        row, _ = self.report(self.claim(), self.observed('EUR', value=7.9e9))
        text = observed_text(row)
        self.assertIn('EUR', text)
        self.assertNotIn('$', text)

    def test_matching_claim_in_same_category_cannot_verify_a_currency_mismatched_claim(self):
        from .grounded_context import _claim_items
        a, b = self.claim('EUR'), self.claim('USD')
        self.observed('USD')
        with mock.patch('zelda_api.truth_delta_engine.data_source_manager.create_observed_datapoints'), \
             mock.patch('zelda_api.truth_delta_engine.data_source_manager.fetch_news_headlines', return_value=[]), \
             mock.patch('zelda_api.dataforb2b_adapter.observe', return_value='unconfigured'), \
             mock.patch.object(TruthDeltaEngine, '_call_claude_for_verification', return_value={
                 'per_claim': [{'category': 'revenue', 'assessment': 'Verified by SEC.'}]}):
            report = TruthDeltaEngine().verify_document(self.doc.id)
        # Existing category aggregation stays intact; individual rows must
        # still describe their own currency gate rather than inherit it.
        self.assertEqual(report.category_states()['revenue'], 'verified')
        rows = {r['claim_id']: r for r in report.per_claim_rows()}
        self.assertEqual((rows[a.pk]['state'], rows[a.pk]['reason']), ('no_data', 'currency_mismatch'))
        self.assertEqual(rows[a.pk]['explanation_source'], 'zelda')
        self.assertEqual(rows[b.pk]['state'], 'verified')
        items = {i.claim_id: i for i in _claim_items(self.doc, [a, b], report)}
        self.assertEqual((items[a.pk].status, items[a.pk].reason), ('INSUFFICIENT', 'currency_mismatch'))
        self.assertEqual(items[b.pk].status, 'VERIFIED')

    def test_unknown_currency_corroboration_does_not_become_numeric_agreement(self):
        row, report = self.report(self.claim(''), self.observed('USD', role='can_corroborate'))
        self.assertEqual(report.grounding_reasons(), {'revenue': 'currency_unknown'})
        self.assertIsNone(row['corroboration'][0]['agrees'])

    def test_provider_declared_currency_is_persisted_and_unqualified_currency_is_not_invented(self):
        from .truth_delta_sources import DataSourceManager
        sec_data = {'_cik': '0000320187', 'facts': {'us-gaap': {'Revenues': {'units': {'USD': [
            {'val': 1e6, 'form': '10-K', 'start': '2025-01-01', 'end': '2025-12-31'}]}}}}}
        cb_data = {'annual_revenue': 2e6, 'total_funding_usd': 3e6}
        with mock.patch.object(DataSourceManager, 'fetch_company_data', return_value={'sec': sec_data, 'crunchbase': cb_data}):
            DataSourceManager.create_observed_datapoints(self.doc, 'Currency Co')
        rows = {(r.source.source_type, r.category): r.currency
                for r in ObservedDatapoint.objects.filter(document=self.doc)}
        self.assertEqual(rows[('sec', 'revenue')], 'USD')
        self.assertEqual(rows[('crunchbase', 'funding_raised')], 'USD')
        self.assertEqual(rows[('crunchbase', 'revenue')], '')

    def test_profile_currency_is_unknown_and_euro_deck_value_is_not_dollars(self):
        from matchmaking.models import Application
        from matchmaking.tests import _mock_embedding_generation
        from .profile_reconciliation import reconcile_profile_with_deck
        _mock_embedding_generation(self)
        Application.objects.create(user=self.owner, company_name='Currency Co', founder_name='F',
                                   email='currency@test.invalid', description='d', sector='SaaS',
                                   stage='Seed', prior_amount_raised=1e6, raising_amount=2e6)
        self.claim('EUR', 'funding_raised')
        row = reconcile_profile_with_deck(self.doc, self.owner)[0]
        self.assertEqual((row.status, row.reason), ('not_comparable', 'profile_currency_unknown'))
        self.assertIn('EUR', row.deck_display)
        self.assertNotIn('$', row.deck_display)


class ProviderCurrencyTests(SimpleTestCase):
    def test_sec_usd_unit_and_crunchbase_usd_funding_have_source_declared_currency(self):
        from .truth_delta_sources import SECFilingsIntegration, CrunchbaseIntegration
        data = {'facts': {'us-gaap': {'Revenues': {'units': {'USD': [
            {'val': 1e6, 'form': '10-K', 'start': '2025-01-01', 'end': '2025-12-31'}]}}}}}
        self.assertEqual(SECFilingsIntegration().extract_currency(data, 'revenue'), 'USD')
        self.assertEqual(CrunchbaseIntegration().extract_currency({'total_funding_usd': 1e6}, 'funding_raised'), 'USD')
        self.assertEqual(CrunchbaseIntegration().extract_currency({'annual_revenue': 1e6}, 'revenue'), '')
