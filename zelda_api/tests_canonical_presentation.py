"""
Phase 1 close-out PR 3, part 1: presentation derived from canonical state
(Nike baseline L-005, L-008).

The Nike shape: revenue has an SEC figure (so it is `grounded` -- there is
something to show) but no comparable period (so its state is no_data, reason
period_unknown). The baseline page drew a check mark from `grounded`, counted
"1/2 claims verified" beside a "0 verified" stat card, and the Intelligence
Report said "Zelda found external support for several of the deck's checkable
claims". Every surface must now say what the canonical state says.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from matchmaking.models import Application, InvestorApplication
from matchmaking.tests import _mock_embedding_generation
from zelda_api.ic_memo import coverage_sentence, truth_delta_signal, zelda_report_observations
from zelda_api.truth_delta_models import TruthDeltaReport
from zelda_api.vector_models import DocumentSource, IntelligenceMemo

User = get_user_model()

NIKE_ROW = {
    'category': 'revenue', 'claimed_value': '$52.8 billion', 'claimed_value_numeric': 52.8e9,
    'observed_value': '46398000000.0', 'observed_value_numeric': 46.398e9, 'observed_source': 'SEC EDGAR',
    'observed_registrant': '0000320187', 'observed_time_period': 'FY2026 10-K (period ending 2026-05-31)',
    'discrepancy_pct': 13.8, 'claim_raw_text': '$52.8 billion', 'claim_period': None,
}
EMPLOYEES_ROW = {
    'category': 'employees', 'claimed_value': '81,500 people', 'claimed_value_numeric': 81500.0,
    'observed_value': None, 'observed_value_numeric': None, 'observed_source': None,
    'observed_registrant': None, 'observed_time_period': None, 'discrepancy_pct': None,
    'claim_raw_text': '81,500 people', 'claim_period': None,
}


class _NikeShape(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.owner = User.objects.create_user('present_owner', password='x')
        self.app = Application.objects.create(user=self.owner, company_name='Present Co', founder_name='F',
                                              email='p@t.test', description='d', sector='Retail', stage='Public')
        self.doc = DocumentSource.objects.create(
            filename='deck.pptx', source_entity='Present Co', uploaded_by=self.owner,
            document_type='pitch_deck', status='analyzed')
        IntelligenceMemo.objects.create(document=self.doc, executive_summary='Summary.',
                                        evidence_level='LIMITED_EVIDENCE')
        self.report = TruthDeltaReport.objects.create(
            document=self.doc, overall_truth_score=42.0, credibility_risk='high', summary='model prose',
            details={
                'claims': [], 'observed': [{'category': 'revenue', 'observed_value': '46398000000.0',
                                            'source': 'SEC EDGAR', 'time_period': 'FY2026'}],
                'comparison': [NIKE_ROW, EMPLOYEES_ROW],
                'per_claim': [
                    {'category': 'employees', 'claimed': '81,500', 'observed': 'no external data found',
                     'assessment': 'No source.'},
                    {'category': 'revenue', 'claimed': '$52.8 billion',
                     'observed': '$46.4 billion (SEC EDGAR FY2026 10-K)', 'assessment': 'Material gap.'},
                ],
            })


class ServedRowsTests(_NikeShape):
    """L-005: rows carry the canonical state; `grounded` keeps its narrower meaning."""

    def test_nike_revenue_is_grounded_but_not_verified(self):
        rows = {row['category']: row for row in self.report.per_claim_rows()}
        self.assertEqual((rows['revenue']['grounded'], rows['revenue']['state'], rows['revenue']['reason']),
                         (True, 'no_data', 'period_unknown'))
        self.assertEqual((rows['employees']['grounded'], rows['employees']['state']), (False, 'no_data'))

    def test_counts_and_rows_cannot_disagree(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.doc.id]))
        rows = response.context['details']['per_claim']
        self.assertEqual(response.context['verified_count'],
                         sum(1 for row in rows if row['state'] == 'verified'))
        self.assertEqual(response.context['verified_count'], 0)

    def test_the_api_serves_the_same_states(self):
        self.client.force_login(self.owner)
        payload = self.client.get(reverse('zelda_api:truth_delta_score', args=[self.doc.id])).json()
        states = {row['category']: row['state'] for row in payload['details']['per_claim']}
        self.assertEqual(states, {'revenue': 'no_data', 'employees': 'no_data'})


class CoverageSentenceTests(SimpleTestCase):

    def test_says_what_the_counts_say(self):
        self.assertEqual(coverage_sentence({'total': 2, 'verified': 0, 'contradicted': 0}),
                         '0 of 2 checkable claims verified against a public source; 2 could not be confirmed.')
        self.assertEqual(coverage_sentence({'total': 3, 'verified': 1, 'contradicted': 1}),
                         '1 of 3 checkable claims verified against a public source; 1 contradicted; '
                         '1 could not be confirmed.')
        self.assertEqual(coverage_sentence({'total': 1, 'verified': 1, 'contradicted': 0}),
                         '1 of 1 checkable claim verified against a public source.')
        self.assertIn('None of', coverage_sentence({'total': 0}))


class IntelligenceReportTests(_NikeShape):
    """L-008: the investor-facing card and observations follow the canonical state."""

    def test_signal_carries_the_canonical_sentence(self):
        self.assertEqual(truth_delta_signal(self.doc)['coverage_sentence'],
                         '0 of 2 checkable claims verified against a public source; 2 could not be confirmed.')

    def test_the_report_page_no_longer_claims_external_support(self):
        investor = User.objects.create_user('present_investor', password='x')
        InvestorApplication.objects.create(user=investor, full_name='I', email='i@t.test', company_name='Ic',
                                           investment_focus='Retail', investment_stage='Growth')
        self.client.force_login(investor)
        response = self.client.get(reverse('matchmaking:standalone_memo', args=['present-co']))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'found external support')
        self.assertContains(response, '0 of 2 checkable claims verified against a public source')

    def test_observations_say_why_nothing_was_confirmed(self):
        noticed = zelda_report_observations(IntelligenceMemo.objects.get(document=self.doc), self.doc)['noticed']
        text = ' '.join(noticed)
        self.assertIn('An external figure was found for revenue, but its period could not be confirmed', text)
        self.assertIn('No public source was found to check employees', text)
        self.assertNotIn('No public source was found to check employees and revenue', text)
