"""
Task 8: DataForB2B facts -> Truth Delta observations, end to end.

The agreed matrix (2026-10-03):
  deck claim + DataForB2B agrees, no establishing source
      -> INSUFFICIENT ('corroboration_only'), DataForB2B attached as
         corroboration, cited as linkedin_derived. Two weak sources never
         vote a fact into truth.
  establishing source agrees + DataForB2B agrees
      -> verified; DataForB2B recorded as independent corroboration.
  DataForB2B fails
      -> the report is still written; the failure is a provider outcome,
         never an absence reason for claims it cannot speak to.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from matchmaking.models import Application
from matchmaking.tests import _mock_embedding_generation
from zelda_api import dataforb2b as d4b
from zelda_api import dataforb2b_adapter as adapter
from zelda_api.grounded_context import CORROBORATES, INSUFFICIENT, GroundedContext
from zelda_api.principal import ORIGIN_TASK, Principal
from zelda_api.source_capabilities import (
    CAN_CORROBORATE, CAN_ESTABLISH, INFORMATIONAL_ONLY, LINKEDIN_DERIVED, THIRD_PARTY_DATABASE,
)
from zelda_api.tests_dataforb2b import FakeResponse, FakeSession, company
from zelda_api.truth_delta_engine import TruthDeltaEngine
from zelda_api.truth_delta_models import ClaimedDatapoint, ExternalDataSource, ObservedDatapoint
from zelda_api.vector_models import DocumentSource

KEY = 'dfb2b_ADAPTER_TEST_KEY_123'
ROUTES_OK = {
    '/search/count': FakeResponse(200, {'total_results': 1, 'total_results_is_capped': False}),
    '/search/companies': FakeResponse(200, {'results': [{'id': 'org_acme1'}], 'credits_used': 0.75}),
    '/enrich/company': FakeResponse(200, company(name='Acme')),       # equity rounds sum to $865M
}


class _Adapter(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.user = get_user_model().objects.create_user('d4b_owner', password='x')
        self.app = Application.objects.create(
            user=self.user, company_name='Acme', founder_name='F', email='f@acme.test', description='d',
            sector='Fintech', stage='Series B', company_website='https://www.acme.io/about',
            linkedin_url='https://www.linkedin.com/in/the-founder')
        self.doc = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Acme', uploaded_by=self.user,
            document_type='pitch_deck', status='analyzed')

    def claim(self, category='funding_raised', value=850e6):
        return ClaimedDatapoint.objects.create(
            document=self.doc, category=category, claimed_value=f'{category}: {value}',
            currency='USD' if category == 'funding_raised' else '',
            claimed_value_numeric=value, page_number=2, chunk_hash='h', confidence_in_extraction=90.0)

    def provider(self, routes=None):
        session = FakeSession(dict(routes or ROUTES_OK))
        return d4b.DataForB2BClient(api_key=KEY, session=session), session

    def rows(self):
        return ObservedDatapoint.objects.filter(document=self.doc, source__source_type='dataforb2b')


# -- the adapter's own gates -----------------------------------------------------------

class GateTests(_Adapter):

    def test_not_asked_without_a_relevant_claim(self):
        claims = [self.claim('revenue', 4e6), self.claim('customers', 300)]
        client, session = self.provider()
        self.assertEqual(adapter.observe(self.doc, claims, client=client), adapter.NOT_NEEDED)
        self.assertEqual(session.calls, [])

    def test_unconfigured_writes_nothing(self):
        client = d4b.DataForB2BClient(api_key='', session=FakeSession({}))
        self.assertEqual(adapter.observe(self.doc, [self.claim()], client=client), d4b.UNCONFIGURED)
        self.assertFalse(self.rows().exists())

    def test_no_deterministic_identifier_is_not_asked(self):
        self.app.company_website = ''
        self.app.save()                                  # linkedin_url is a person's /in/ page
        client, session = self.provider()
        self.assertEqual(adapter.observe(self.doc, [self.claim()], client=client), d4b.UNRESOLVABLE)
        self.assertEqual(session.calls, [])

    def test_identifiers_come_from_the_profile(self):
        self.assertEqual(adapter.identifiers_for(self.doc), {'domain': 'acme.io'})
        self.app.linkedin_url = 'https://www.linkedin.com/company/acme'
        self.app.save()
        self.assertEqual(adapter.identifiers_for(self.doc),
                         {'domain': 'acme.io', 'linkedin': 'https://www.linkedin.com/company/acme'})


class WriteTests(_Adapter):

    def test_rows_carry_role_origin_and_provenance(self):
        claims = [self.claim('funding_raised'), self.claim('employees', 1200)]
        client, _ = self.provider()
        self.assertEqual(adapter.observe(self.doc, claims, client=client), d4b.SUCCESS)
        rows = {row.category: row for row in self.rows()}
        self.assertEqual(set(rows), {'funding_raised', 'employees'})
        funding, employees = rows['funding_raised'], rows['employees']
        self.assertEqual((funding.role, funding.evidence_origin), (CAN_CORROBORATE, LINKEDIN_DERIVED))
        self.assertEqual((employees.role, employees.evidence_origin), (INFORMATIONAL_ONLY, LINKEDIN_DERIVED))
        self.assertEqual(funding.observed_value_numeric, 865e6)
        self.assertEqual(funding.registrant, 'org_0lox54iG5IEZSb71mZWLR8z9CVPtpuHOmUOf')
        for key in ('provider', 'provider_id', 'provider_field', 'lookup_method', 'lookup_identifier', 'retrieved_at'):
            with self.subTest(key=key):
                self.assertTrue(funding.provenance.get(key))
        self.assertEqual((funding.provenance['lookup_method'], funding.provenance['provider_field']),
                         ('domain', 'funding.rounds'))
        self.assertIn('LinkedIn-associated', employees.observed_value)

    def test_never_writes_an_establishing_row(self):
        client, _ = self.provider()
        adapter.observe(self.doc, [self.claim(), self.claim('employees', 1200)], client=client)
        self.assertFalse(self.rows().filter(role=CAN_ESTABLISH).exists())

    def test_success_replaces_only_its_own_rows(self):
        other = ExternalDataSource.objects.get_or_create(source_type='crunchbase', defaults={'source_name': 'Crunchbase'})[0]
        kept = ObservedDatapoint.objects.create(
            document=self.doc, category='funding_raised', observed_value='$1', observed_value_numeric=1.0,
            source=other, role=CAN_CORROBORATE, evidence_origin=THIRD_PARTY_DATABASE)
        client, _ = self.provider()
        adapter.observe(self.doc, [self.claim()], client=client)
        adapter.observe(self.doc, [self.claim()], client=self.provider()[0])
        self.assertEqual(self.rows().filter(category='funding_raised').count(), 1)
        self.assertTrue(ObservedDatapoint.objects.filter(pk=kept.pk).exists())

    def test_a_failed_refresh_keeps_the_previous_rows(self):
        adapter.observe(self.doc, [self.claim()], client=self.provider()[0])
        before = list(self.rows().values_list('pk', flat=True))
        failing, _ = self.provider({'/search/count': FakeResponse(200, {'total_results': 3})})
        self.assertEqual(adapter.observe(self.doc, [self.claim()], client=failing), d4b.AMBIGUOUS)
        self.assertEqual(list(self.rows().values_list('pk', flat=True)), before)


# -- end to end through the real engine ------------------------------------------------------

JUDGMENT = {'overall_truth_score': 80.0, 'credibility_risk': 'low', 'summary': 'judged', 'per_claim': []}


class EndToEndTests(_Adapter):

    def verify(self, *, establishing_funding=None, routes=None):
        """Run verify_document with the existing sources stubbed and DataForB2B on a fake session."""
        def existing_sources(document, company_name, domain=None, diagnostics=None):
            if establishing_funding is not None:
                filing = ExternalDataSource.objects.get_or_create(
                    source_type='corporate', defaults={'source_name': 'Corporate filing'})[0]
                ObservedDatapoint.objects.create(
                    document=document, category='funding_raised', observed_value=str(establishing_funding),
                    currency='USD',
                    observed_value_numeric=establishing_funding, source=filing, source_credibility=0.95,
                    role=CAN_ESTABLISH, evidence_origin='company_document', time_period='to date')
            return []

        client, _ = self.provider(routes)
        engine = TruthDeltaEngine()
        with mock.patch('zelda_api.truth_delta_engine.data_source_manager.create_observed_datapoints',
                        side_effect=existing_sources), \
                mock.patch('zelda_api.truth_delta_engine.data_source_manager.fetch_news_headlines', return_value=[]), \
                mock.patch('zelda_api.dataforb2b_adapter.DataForB2BClient', return_value=client), \
                mock.patch.object(TruthDeltaEngine, '_call_claude_for_verification', return_value=dict(JUDGMENT)) as judge:
            report = engine.verify_document(self.doc.id)
        return report, judge

    def test_corroboration_alone_never_establishes(self):
        self.claim('funding_raised', 850e6)
        report, judge = self.verify()
        self.assertEqual(report.category_states()['funding_raised'], 'no_data')
        self.assertEqual(report.grounding_reasons()['funding_raised'], 'corroboration_only')
        row = report.details['comparison'][0]
        self.assertIsNone(row['observed_value'])
        self.assertEqual(len(row['corroboration']), 1)
        self.assertTrue(row['corroboration'][0]['agrees'])          # 850M vs 865M: within 10%
        self.assertEqual(row['corroboration'][0]['origin'], LINKEDIN_DERIVED)
        self.assertIsNone(report.overall_truth_score, 'no establishing evidence, so no score')
        judge.assert_not_called()
        self.assertIn('corroboration only', report.summary)
        self.assertEqual(report.details['provider_outcomes'], {'dataforb2b': d4b.SUCCESS})

    def test_establishing_source_verifies_and_dataforb2b_corroborates(self):
        self.claim('funding_raised', 850e6)
        report, judge = self.verify(establishing_funding=850e6)
        self.assertEqual(report.category_states()['funding_raised'], 'verified')
        row = report.details['comparison'][0]
        self.assertEqual(row['observed_value_numeric'], 850e6)
        self.assertEqual(row['observed_role'], CAN_ESTABLISH)
        corroboration = row['corroboration'][0]
        self.assertEqual((corroboration['agrees'], corroboration['independent'], corroboration['origin']),
                         (True, True, LINKEDIN_DERIVED))
        judge.assert_called_once()

    def test_dissenting_dataforb2b_never_overturns_the_establishing_source(self):
        self.claim('funding_raised', 400e6)
        report, _ = self.verify(establishing_funding=400e6)        # DataForB2B says 865M
        self.assertEqual(report.category_states()['funding_raised'], 'verified')
        self.assertFalse(report.details['comparison'][0]['corroboration'][0]['agrees'])

    def test_provider_failure_still_writes_the_report_and_stays_out_of_absence_reasons(self):
        self.claim('funding_raised', 850e6)
        self.claim('revenue', 4e6)
        import requests
        report, _ = self.verify(routes={'/search/count': requests.Timeout('slow')})
        self.assertIsNotNone(report)
        self.assertEqual(report.details['provider_outcomes'], {'dataforb2b': d4b.TIMEOUT})
        self.assertNotIn('dataforb2b', report.details['source_diagnostics'])
        self.assertNotEqual(report.grounding_reasons().get('revenue'), 'source_unavailable')

    def test_the_memo_receives_it_as_corroboration(self):
        self.claim('funding_raised', 850e6)
        self.verify()
        context = GroundedContext.build(Principal.for_user(self.user, ORIGIN_TASK), self.doc)
        item = next(i for i in context.items if i.kind == 'claim' and i.category == 'funding_raised')
        self.assertEqual((item.status, item.reason), (INSUFFICIENT, 'corroboration_only'))
        self.assertEqual([(e.role, e.origin, e.agrees) for e in item.external],
                         [(CORROBORATES, LINKEDIN_DERIVED, True)])
