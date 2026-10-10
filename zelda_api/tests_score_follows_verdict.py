"""
R-003b: the credibility score follows Zelda's verdict, not the model's.

    score = verified / (verified + contradicted) * 100

Only claims Zelda established either way count. A no_data claim is excluded
however far apart its raw numbers are, and with nothing scoreable there is no
score and the risk is 'unknown'. Nike's rerun report scored 42/100 'high' --
chosen by a model shown a 13.8% gap Zelda had ruled not comparable -- beside
0 verified / 0 contradicted.

Every engine test stubs the model to return a score and risk of its own, so a
pass proves they were ignored rather than coincidentally equal.
"""
from django.test import SimpleTestCase
from django.urls import reverse

from zelda_api.tests_summary_follows_verdict import _Verify, model_says
from zelda_api.truth_delta_engine import canonical_score
from zelda_api.truth_delta_models import TRUTH_DELTA_SEMANTICS, ExternalDataSource, ObservedDatapoint
from zelda_api.source_capabilities import CAN_CORROBORATE, LINKEDIN_DERIVED


class TheFormulaTests(SimpleTestCase):

    def test_scoreable_counts(self):
        cases = [
            ({'verified': 2, 'contradicted': 0, 'no_data': 5}, (100.0, 'low')),
            ({'verified': 1, 'contradicted': 1, 'no_data': 0}, (50.0, 'high')),
            ({'verified': 0, 'contradicted': 3, 'no_data': 1}, (0.0, 'critical')),
            ({'verified': 3, 'contradicted': 1, 'no_data': 9}, (75.0, 'medium')),
        ]
        for stats, expected in cases:
            with self.subTest(stats=stats):
                self.assertEqual(canonical_score(stats), expected)

    def test_nothing_scoreable_is_no_score_not_zero(self):
        for stats in ({'verified': 0, 'contradicted': 0, 'no_data': 2}, {'total': 0}, {}):
            with self.subTest(stats=stats):
                self.assertEqual(canonical_score(stats), (None, 'unknown'))

    def test_no_data_never_moves_the_score(self):
        self.assertEqual(canonical_score({'verified': 1, 'contradicted': 0, 'no_data': 0}),
                         canonical_score({'verified': 1, 'contradicted': 0, 'no_data': 40}))


class TheEngineStoresZeldasScoreTests(_Verify):

    def test_nike_period_unknown_has_no_score_whatever_the_model_says(self):
        self.claim('revenue', '$52.8 billion', 52.8e9)
        self.claim('employees', '81,500 people worldwide', 81500.0, page=6)
        self.verify(model_says([], score=42.0), revenue=46.398e9)
        self.assertEqual(self.report.grounding_reasons()['revenue'], 'period_unknown')
        self.assertEqual((self.report.overall_truth_score, self.report.credibility_risk), (None, 'unknown'))
        self.assertEqual(self.report.engine_version, TRUTH_DELTA_SEMANTICS)
        self.assertEqual(TRUTH_DELTA_SEMANTICS, 'td.5')

    def test_verified_scores_100_even_when_the_model_says_12(self):
        self.claim('revenue', '$46.4 billion', 46.4e9)
        self.verify(model_says([], score=12.0), revenue=46.398e9)
        self.assertEqual((self.report.overall_truth_score, self.report.credibility_risk), (100.0, 'low'))

    def test_contradicted_scores_0_even_when_the_model_says_95(self):
        self.claim('revenue', '$80 billion', 80e9)
        self.verify(model_says([], score=95.0), revenue=46.398e9, comparable_period=True)
        self.assertEqual(self.report.category_states(), {'revenue': 'contradicted'})
        self.assertEqual((self.report.overall_truth_score, self.report.credibility_risk), (0.0, 'critical'))

    def test_corroboration_only_is_not_scored(self):
        self.claim('funding_raised', '$865 million', 865e6)
        source, _ = ExternalDataSource.objects.get_or_create(
            source_type='dataforb2b', defaults={'source_name': 'DataForB2B'})
        ObservedDatapoint.objects.create(
            document=self.doc, category='funding_raised', observed_value='$865,000,000',
            observed_value_numeric=865e6, source=source, role=CAN_CORROBORATE, evidence_origin=LINKEDIN_DERIVED)
        self.verify(model_says([], score=99.0), revenue=None, headlines=['Nike raises'])
        self.assertEqual((self.report.overall_truth_score, self.report.credibility_risk), (None, 'unknown'))

    def test_no_external_evidence_is_not_scored(self):
        self.claim('employees', '81,500 people worldwide', 81500.0, page=6)
        self.verify(model_says([], score=99.0), revenue=None, headlines=['Nike hires'])
        self.assertEqual((self.report.overall_truth_score, self.report.credibility_risk), (None, 'unknown'))

    def test_the_fallback_scores_the_same_way(self):
        # The old fallback turned Nike's 13.8% gap into an 86.2 score.
        self.claim('revenue', '$52.8 billion', 52.8e9)
        self.verify(None, revenue=46.398e9)
        self.assertEqual((self.report.overall_truth_score, self.report.credibility_risk), (None, 'unknown'))
        self.assertIn('unavailable', self.report.summary)

    def test_the_api_serves_no_score_for_nike(self):
        self.claim('revenue', '$52.8 billion', 52.8e9)
        self.verify(model_says([], score=42.0), revenue=46.398e9)
        self.client.force_login(self.user)
        payload = self.client.get(reverse('zelda_api:truth_delta_score', args=[self.doc.id])).json()
        self.assertEqual((payload['overall_truth_score'], payload['credibility_risk']), (None, 'unknown'))

    def test_the_page_calls_no_score_not_scored_limited_public_evidence(self):
        self.claim('revenue', '$52.8 billion', 52.8e9)
        self.verify(model_says([], score=42.0), revenue=46.398e9)
        self.client.force_login(self.user)
        body = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.doc.id])).content.decode()
        self.assertIn('NOT SCORED · LIMITED PUBLIC EVIDENCE', body)
        self.assertNotIn('NO EXTERNAL DATA', body)
        self.assertNotIn('INSUFFICIENT EVIDENCE', body)
