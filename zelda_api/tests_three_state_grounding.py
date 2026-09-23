"""
A contradiction has to be an auditable conclusion, not a label.

PR #89 made `verified` mean "the pipeline stored an ObservedDatapoint in this
category". That was the right fix for a model writing corroboration into prose,
but existence is not reconciliation: a category holding a datapoint 470% away
from the claim reads `verified` today, because no tolerance is ever applied.

This adds `contradicted` as a third state, computed only from stored numbers:

    verified      a pairing exists and at least one claim is within the
                  category's tolerance
    contradicted  a pairing exists, the pair is PERIOD-COMPARABLE, no claim is
                  within tolerance
    no_data       no defensible comparison, with the reason recorded

Two gates make `contradicted` auditable rather than asserted:

    no period-comparable pair  -> no contradiction
    no persisted provenance    -> no contradiction

The period rule is deliberately ASYMMETRIC. ClaimedDatapoint stores no period,
so requiring one for agreement too would send Apple's revenue -- which matched
SEC EDGAR to 0.04% in run 2 -- to `no_data`, losing a real verification
because the rule tightened on the side that did not need it. Two independent
figures agreeing that closely are themselves evidence of the same period; a
large disagreement is exactly what a period mismatch looks like.

Run 3 supplies the other requirement. The only divergence found across four
subjects was Zelda's own extraction defect: a deck reading "raised $9 million
in growth capital" produced a $4,000,000 funding claim, while the profile
correctly said 9,000,000. A state that cannot show the sentence it came from
turns that into an accusation against the founder.
"""
from django.contrib.auth.models import User
from django.test import TestCase

from .truth_delta_models import TruthDeltaReport
from .vector_models import DocumentSource

# One comparison row, as the engine will persist it.
def row(category='revenue', claimed=416_000_000_000.0, observed=416_161_000_000.0,
        claim_period=None, observed_period='FY2025 10-K', **extra):
    data = {
        'category': category,
        'claim_raw_text': '$416 billion',
        'claimed_value_numeric': claimed,
        'observed_raw_value': str(observed) if observed is not None else None,
        'observed_value_numeric': observed,
        'observed_source': 'SEC EDGAR',
        'source_credibility': 0.95,
        'claim_period': claim_period,
        'observed_time_period': observed_period,
        'discrepancy_pct': (None if (claimed is None or not observed)
                            else round((claimed - observed) / observed * 100, 1)),
    }
    data.update(extra)
    return data


class _GroundingCast(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('tsg_owner', password='x')
        self.document = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Subject Co',
            uploaded_by=self.owner, document_type='pitch_deck',
        )

    def report(self, comparison=None, observed=None, claims=None, per_claim=None):
        details = {
            'claims': claims if claims is not None else [{'category': 'revenue'}],
            'per_claim': per_claim or [],
            'observed': observed if observed is not None else [
                {'category': 'revenue', 'observed_value': '416161000000.0', 'source': 'SEC EDGAR'}],
        }
        if comparison is not None:
            details['comparison'] = comparison
        return TruthDeltaReport.objects.create(
            document=self.document, overall_truth_score=90.0, credibility_risk='low',
            summary='test', details=details,
        )


class ReconciliationDecidesTheStateTests(_GroundingCast):

    def test_a_reconciling_pair_is_verified(self):
        """Apple's run-2 case: 416,000,000,000 against 416,161,000,000."""
        report = self.report(comparison=[row()])
        self.assertEqual(report.category_states(), {'revenue': 'verified'})

    def test_a_material_divergence_with_comparable_periods_is_contradicted(self):
        report = self.report(comparison=[
            row(claimed=11_400_000.0, observed=2_000_000.0,
                claim_period='FY2025', observed_period='FY2025')])
        self.assertEqual(report.category_states(), {'revenue': 'contradicted'})

    def test_existence_of_a_datapoint_is_no_longer_enough(self):
        """
        The change this PR makes: a datapoint 470% away used to read verified,
        because no tolerance was ever applied.
        """
        report = self.report(comparison=[
            row(claimed=11_400_000.0, observed=2_000_000.0,
                claim_period='FY2025', observed_period='FY2025')])
        self.assertNotEqual(report.category_states()['revenue'], 'verified')

    def test_one_agreeing_claim_carries_the_category(self):
        """
        Set-based, per run 3: a deck states revenue twice and one matches.
        Collapsing to a single claim reported a false divergence.
        """
        report = self.report(comparison=[
            row(claimed=4_000_000.0, observed=11_400_000.0, claim_period='FY2025', observed_period='FY2025'),
            row(claimed=11_400_000.0, observed=11_400_000.0, claim_period='FY2025', observed_period='FY2025'),
        ])
        self.assertEqual(report.category_states(), {'revenue': 'verified'})

    def test_the_agreeing_claim_carries_it_whichever_order_it_arrives_in(self):
        """
        Same set as above, reversed. A rule that looked at one row -- the
        first, the last, the highest-confidence -- would pass one ordering and
        fail the other.
        """
        report = self.report(comparison=[
            row(claimed=11_400_000.0, observed=11_400_000.0, claim_period='FY2025', observed_period='FY2025'),
            row(claimed=4_000_000.0, observed=11_400_000.0, claim_period='FY2025', observed_period='FY2025'),
        ])
        self.assertEqual(report.category_states(), {'revenue': 'verified'})

    def test_a_category_with_no_agreeing_claim_is_contradicted(self):
        report = self.report(comparison=[
            row(claimed=4_000_000.0, observed=11_400_000.0, claim_period='FY2025', observed_period='FY2025'),
            row(claimed=5_000_000.0, observed=11_400_000.0, claim_period='FY2025', observed_period='FY2025'),
        ])
        self.assertEqual(report.category_states(), {'revenue': 'contradicted'})

    def test_evidence_in_one_category_never_grounds_another(self):
        report = self.report(
            comparison=[row(category='revenue'), row(category='employees', claimed=164000.0, observed=None)],
            claims=[{'category': 'revenue'}, {'category': 'employees'}],
        )
        states = report.category_states()
        self.assertEqual(states['revenue'], 'verified')
        self.assertEqual(states['employees'], 'no_data')


class PeriodComparabilityIsAsymmetricTests(_GroundingCast):

    def test_agreement_survives_an_unknown_period(self):
        """Apple: the claim carries no period, and the figures still reconcile."""
        report = self.report(comparison=[row(claim_period=None)])
        self.assertEqual(report.category_states(), {'revenue': 'verified'})

    def test_a_divergence_without_a_comparable_period_is_not_contradicted(self):
        """A period mismatch is exactly what a large gap looks like."""
        report = self.report(comparison=[
            row(claimed=11_400_000.0, observed=2_000_000.0, claim_period=None)])
        self.assertEqual(report.category_states(), {'revenue': 'no_data'})

    def test_that_case_records_why(self):
        report = self.report(comparison=[
            row(claimed=11_400_000.0, observed=2_000_000.0, claim_period=None)])
        self.assertEqual(report.grounding_reasons()['revenue'], 'period_unknown')

    def test_mismatched_periods_are_not_comparable(self):
        report = self.report(comparison=[
            row(claimed=11_400_000.0, observed=2_000_000.0,
                claim_period='FY2023', observed_period='FY2025 10-K')])
        self.assertEqual(report.category_states(), {'revenue': 'no_data'})
        self.assertEqual(report.grounding_reasons()['revenue'], 'period_unknown')


class ToleranceIsPerCategoryTests(_GroundingCast):

    def test_revenue_is_held_to_ten_percent(self):
        inside = self.report(comparison=[
            row(claimed=105_000_000.0, observed=100_000_000.0, claim_period='FY2025', observed_period='FY2025')])
        self.assertEqual(inside.category_states()['revenue'], 'verified')

    def test_revenue_outside_ten_percent_contradicts(self):
        outside = self.report(comparison=[
            row(claimed=130_000_000.0, observed=100_000_000.0, claim_period='FY2025', observed_period='FY2025')])
        self.assertEqual(outside.category_states()['revenue'], 'contradicted')

    def test_headcount_is_held_to_twenty_percent(self):
        """A deck states headcount loosely; 15% off is not a contradiction."""
        report = self.report(
            comparison=[row(category='employees', claimed=115.0, observed=100.0,
                            claim_period='2026', observed_period='2026')],
            claims=[{'category': 'employees'}],
        )
        self.assertEqual(report.category_states()['employees'], 'verified')

    def test_a_category_without_its_own_band_uses_the_default(self):
        """
        Every other test here names a category with an explicit tolerance, so
        DEFAULT_TOLERANCE went unpinned: a mutation setting it to 5.0 (500%)
        broke nothing. `growth_rate` has no entry in GROUNDING_TOLERANCE and
        falls back to it.
        """
        inside = self.report(
            comparison=[row(category='growth_rate', claimed=110.0, observed=100.0,
                            claim_period='2026', observed_period='2026')],
            claims=[{'category': 'growth_rate'}],
        )
        self.assertEqual(inside.category_states()['growth_rate'], 'verified')

    def test_a_category_without_its_own_band_still_contradicts_beyond_it(self):
        outside = self.report(
            comparison=[row(category='growth_rate', claimed=300.0, observed=100.0,
                            claim_period='2026', observed_period='2026')],
            claims=[{'category': 'growth_rate'}],
        )
        self.assertEqual(outside.category_states()['growth_rate'], 'contradicted')
        self.assertEqual(
            outside.grounding_chain()['growth_rate'][0]['tolerance_applied'],
            TruthDeltaReport.DEFAULT_TOLERANCE,
        )

    def test_market_size_can_never_be_contradicted(self):
        """
        A grounding RULE, not a wide tolerance: TAM estimates legitimately
        differ by multiples, and a later tolerance edit must not be able to
        make them contradictory.
        """
        report = self.report(
            comparison=[row(category='market_size', claimed=2_400_000_000.0, observed=200_000_000.0,
                            claim_period='2026', observed_period='2026')],
            claims=[{'category': 'market_size'}],
        )
        self.assertNotEqual(report.category_states()['market_size'], 'contradicted')


class ADecisionMustBeReconstructableTests(_GroundingCast):

    def test_a_contradiction_without_provenance_is_refused(self):
        """No persisted evidence chain -> no contradiction."""
        report = self.report(comparison=[{
            'category': 'revenue', 'claimed_value_numeric': 11_400_000.0,
            'observed_value_numeric': 2_000_000.0,
            'claim_period': 'FY2025', 'observed_time_period': 'FY2025',
            'discrepancy_pct': 470.0,
            # no claim_raw_text, no source
        }])
        self.assertEqual(report.category_states()['revenue'], 'no_data')
        self.assertEqual(report.grounding_reasons()['revenue'], 'extraction_insufficient')

    def test_the_chain_is_served_with_the_state(self):
        report = self.report(comparison=[
            row(claimed=11_400_000.0, observed=2_000_000.0, claim_period='FY2025', observed_period='FY2025')])
        chain = report.grounding_chain()['revenue'][0]
        self.assertEqual(chain['claim_raw_text'], '$416 billion')
        self.assertEqual(chain['observed_source'], 'SEC EDGAR')
        self.assertEqual(chain['source_credibility'], 0.95)
        self.assertEqual(chain['discrepancy_pct'], 470.0)
        self.assertEqual(chain['tolerance_applied'], 0.10)
        self.assertEqual(chain['state'], 'contradicted')

    def test_the_discrepancy_is_measured_against_the_evidence(self):
        """
        (claimed - observed) / observed. Claimed 11.4M against observed 4M is
        +185%, not +64.9%; the two straddle every plausible tolerance, so the
        denominator is pinned here.
        """
        report = self.report(comparison=[
            row(claimed=11_400_000.0, observed=4_000_000.0, claim_period='FY2025', observed_period='FY2025')])
        self.assertEqual(report.grounding_chain()['revenue'][0]['discrepancy_pct'], 185.0)

    def test_the_sign_survives(self):
        """Positive means the company's figure is higher than the evidence."""
        under = self.report(comparison=[
            row(claimed=2_000_000.0, observed=11_400_000.0, claim_period='FY2025', observed_period='FY2025')])
        self.assertLess(under.grounding_chain()['revenue'][0]['discrepancy_pct'], 0)


class MissingEvidenceNeverContradictsTests(_GroundingCast):

    def test_no_datapoint_is_no_data_not_contradicted(self):
        report = self.report(comparison=[row(observed=None, observed_period=None)], observed=[])
        self.assertEqual(report.category_states(), {'revenue': 'no_data'})
        self.assertEqual(report.grounding_reasons()['revenue'], 'no_external_evidence')

    def test_a_report_with_no_comparison_falls_back_to_the_existing_rule(self):
        """
        Reports stored before this change have no comparison. They keep the
        PR #89 behaviour -- a datapoint in the category means verified -- so
        history does not silently re-read as contradicted.
        """
        report = self.report(comparison=None)
        self.assertEqual(report.category_states(), {'revenue': 'verified'})

    def test_an_old_report_with_no_evidence_stays_no_data(self):
        report = self.report(comparison=None, observed=[])
        self.assertEqual(report.category_states(), {'revenue': 'no_data'})


class TheEngineBuildsAndKeepsTheComparisonTests(TestCase):
    """
    The rows above are hand-built; these exercise the engine that produces
    them. Without this, a mutation to the discrepancy formula or to the
    persistence step would survive every test in this file.
    """

    def setUp(self):
        from .truth_delta_models import ClaimedDatapoint, ExternalDataSource, ObservedDatapoint
        self.owner = User.objects.create_user('tsg_engine_owner', password='x')
        self.document = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Subject Co',
            uploaded_by=self.owner, document_type='pitch_deck',
        )
        source, _ = ExternalDataSource.objects.get_or_create(
            source_type='sec_edgar', defaults={'source_name': 'SEC EDGAR'})
        ClaimedDatapoint.objects.create(
            document=self.document, category='revenue',
            claimed_value='$11.4 million in annual recurring revenue',
            claimed_value_numeric=11_400_000.0)
        ObservedDatapoint.objects.create(
            document=self.document, category='revenue', observed_value='4000000.0',
            observed_value_numeric=4_000_000.0, source=source, source_credibility=0.95,
            time_period='FY2025 10-K')

    def comparison(self):
        from .truth_delta_engine import TruthDeltaEngine
        from .truth_delta_models import ClaimedDatapoint, ObservedDatapoint
        return TruthDeltaEngine()._build_comparison(
            list(ClaimedDatapoint.objects.filter(document=self.document)),
            list(ObservedDatapoint.objects.filter(document=self.document)),
        )

    def test_the_discrepancy_is_measured_against_the_evidence(self):
        """11.4M against 4M is +185%; dividing by the claim would give +64.9%."""
        self.assertEqual(self.comparison()[0]['discrepancy_pct'], 185.0)

    def test_a_claim_below_the_evidence_reports_a_negative(self):
        from .truth_delta_models import ClaimedDatapoint
        ClaimedDatapoint.objects.filter(document=self.document).update(claimed_value_numeric=2_000_000.0)
        self.assertLess(self.comparison()[0]['discrepancy_pct'], 0)

    def test_the_engine_records_the_provenance(self):
        row_out = self.comparison()[0]
        self.assertEqual(row_out['claim_raw_text'], '$11.4 million in annual recurring revenue')
        self.assertEqual(row_out['observed_source'], 'SEC EDGAR')
        self.assertEqual(row_out['source_credibility'], 0.95)
        self.assertIn('claim_period', row_out)   # explicitly unknown, not omitted

    def test_the_comparison_is_persisted_on_the_report(self):
        """It used to be built, handed to Claude, and dropped."""
        from unittest import mock
        from .truth_delta_engine import TruthDeltaEngine
        engine = TruthDeltaEngine()
        claude = {'overall_truth_score': 40.0, 'credibility_risk': 'high',
                  'summary': 'x', 'per_claim': [{'category': 'revenue', 'observed': '$4M'}]}
        with mock.patch.object(engine, '_call_claude_for_verification', return_value=claude), \
             mock.patch('zelda_api.truth_delta_engine.data_source_manager') as sources:
            sources.create_observed_datapoints.return_value = None
            sources.fetch_news_headlines.return_value = []
            report = engine.verify_document(self.document.id)
        stored = (report.details or {}).get('comparison')
        self.assertTrue(stored, 'the comparison was not persisted')
        self.assertEqual(stored[0]['discrepancy_pct'], 185.0)
        self.assertEqual(stored[0]['observed_source'], 'SEC EDGAR')


class CountsAcrossThreeStatesTests(_GroundingCast):

    def test_verifiability_counts_only_reconciled_claims(self):
        report = self.report(
            comparison=[
                row(category='revenue'),
                row(category='employees', claimed=200.0, observed=100.0,
                    claim_period='2026', observed_period='2026'),
                row(category='funding_raised', claimed=5_000_000.0, observed=None),
            ],
            claims=[{'category': 'revenue'}, {'category': 'employees'}, {'category': 'funding_raised'}],
        )
        self.assertEqual(report.category_states(), {
            'revenue': 'verified', 'employees': 'contradicted', 'funding_raised': 'no_data',
        })
        stats = report.verifiability_stats()
        self.assertEqual(stats['verified'], 1)
        self.assertEqual(stats['total'], 3)

    def test_a_contradicted_category_is_not_counted_as_unverified_silence(self):
        """
        'no external data' and 'the evidence disagrees' are different findings
        and must not be summed into one number.
        """
        report = self.report(
            comparison=[
                row(category='employees', claimed=200.0, observed=100.0,
                    claim_period='2026', observed_period='2026'),
                row(category='funding_raised', claimed=5_000_000.0, observed=None),
            ],
            claims=[{'category': 'employees'}, {'category': 'funding_raised'}],
        )
        stats = report.verifiability_stats()
        self.assertEqual(stats.get('contradicted'), 1)
        self.assertEqual(stats.get('no_data'), 1)
