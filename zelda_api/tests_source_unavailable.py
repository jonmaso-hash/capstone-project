"""
"We could not look" must not be recorded as "there is nothing there."

Found while running the A1x experiment on 2026-09-23. SEC EDGAR answered 503
for Truth Delta's query and 200 slowly (18.2s) for the one beside it, against
a 10s client timeout. The lookup raised Timeout, and
`resolve_with_diagnostics` cached `(None, 'timeout')` under
_CACHE_TTL_NOT_FOUND -- six hours. Every later run then read a cached absence
and reported `no_external_evidence` for a company EDGAR plainly knows, long
after the source recovered.

That is the same conflation the grounding work removed one layer above: "we
could not check" becoming "there is nothing there". A transient failure is not
evidence about a company.

Two rules:

    a transient source failure is never cached as an absence
    a decline caused by an unreachable source says so

The second matters because the artifact's whole purpose is auditable
provenance. `no_external_evidence` asserts something about the world;
`source_unavailable` asserts something about the attempt. Only one of them was
true in run 4, and the artifact said the other.

Deliberately out of scope: the two SEC clients' differing timeouts and
throttling (recorded as D2 in the A1x artifact). Changing those would turn a
correctness fix into a client refactor.
"""
from unittest import mock

import requests
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from .truth_delta_models import TruthDeltaReport
from .truth_delta_sources import SECFilingsIntegration
from .vector_models import DocumentSource

CACHE_KEY = 'sec_edgar_cik_v2:apple inc.'


class ATransientFailureIsNotAnAbsenceTests(SimpleTestCase):
    """The cache must not turn a ten-second blip into a six-hour absence."""

    def setUp(self):
        cache.delete(CACHE_KEY)
        self.addCleanup(cache.delete, CACHE_KEY)

    def resolve_with(self, side_effect):
        integration = SECFilingsIntegration()
        with mock.patch.object(integration.session, 'get', side_effect=side_effect):
            return integration.resolve_with_diagnostics('Apple Inc.')

    def test_a_timeout_is_not_cached(self):
        result = self.resolve_with(requests.exceptions.Timeout())
        self.assertEqual(result, (None, 'timeout'))
        self.assertIsNone(cache.get(CACHE_KEY), 'a transient failure was cached as an absence')

    def test_a_request_error_is_not_cached(self):
        result = self.resolve_with(requests.exceptions.ConnectionError())
        self.assertEqual(result[1], 'request_error')
        self.assertIsNone(cache.get(CACHE_KEY))

    def test_the_next_attempt_retries_rather_than_reading_the_failure(self):
        """The point of not caching: recovery is visible immediately."""
        self.resolve_with(requests.exceptions.Timeout())

        good = mock.Mock(status_code=200, text='<CIK>0000320193</CIK>')
        integration = SECFilingsIntegration()
        with mock.patch.object(integration.session, 'get', return_value=good):
            cik, reason = integration.resolve_with_diagnostics('Apple Inc.')

        self.assertEqual(cik, '0000320193')
        self.assertIsNone(reason)

    def test_a_real_absence_is_still_cached(self):
        """Control: a successful query that found nothing is genuine evidence."""
        empty = mock.Mock(status_code=200, text='<feed></feed>')
        integration = SECFilingsIntegration()
        with mock.patch.object(integration.session, 'get', return_value=empty):
            integration.resolve_with_diagnostics('Apple Inc.')
        self.assertEqual(cache.get(CACHE_KEY), (None, 'not_found'))

    def test_a_resolution_is_still_cached(self):
        """Control: the found path keeps its cache, which is the point of it."""
        good = mock.Mock(status_code=200, text='<CIK>0000320193</CIK>')
        integration = SECFilingsIntegration()
        with mock.patch.object(integration.session, 'get', return_value=good):
            integration.resolve_with_diagnostics('Apple Inc.')
        self.assertEqual(cache.get(CACHE_KEY), ('0000320193', None))


class ADeclineNamesTheRightCauseTests(TestCase):
    """`no_external_evidence` is a claim about the world, not about the attempt."""

    def setUp(self):
        self.owner = User.objects.create_user('su_owner', password='x')
        self.document = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Subject Co',
            uploaded_by=self.owner, document_type='pitch_deck',
        )

    def report(self, diagnostics=None):
        details = {
            'claims': [{'category': 'revenue'}],
            'observed': [],
            'per_claim': [],
            'comparison': [{
                'category': 'revenue', 'claim_raw_text': '$416 billion',
                'claimed_value_numeric': 416_000_000_000.0,
                'observed_value_numeric': None, 'observed_raw_value': None,
                'observed_source': None, 'source_credibility': None,
                'claim_period': None, 'observed_time_period': None,
                'discrepancy_pct': None,
            }],
        }
        if diagnostics is not None:
            details['source_diagnostics'] = diagnostics
        return TruthDeltaReport.objects.create(
            document=self.document, overall_truth_score=None, credibility_risk='unknown',
            summary='test', details=details,
        )

    def test_an_unreachable_source_says_so(self):
        report = self.report(diagnostics={'sec_edgar': 'timeout'})
        self.assertEqual(report.category_states(), {'revenue': 'no_data'})
        self.assertEqual(report.grounding_reasons()['revenue'], 'source_unavailable')

    def test_a_request_error_is_also_the_source_not_the_company(self):
        report = self.report(diagnostics={'sec_edgar': 'request_error'})
        self.assertEqual(report.grounding_reasons()['revenue'], 'source_unavailable')

    def test_a_source_that_answered_and_found_nothing_is_an_absence(self):
        """Control: a successful query with no match is evidence about the company."""
        report = self.report(diagnostics={'sec_edgar': 'not_found'})
        self.assertEqual(report.grounding_reasons()['revenue'], 'no_external_evidence')

    def test_no_diagnostics_at_all_stays_an_absence(self):
        """Control: reports written before diagnostics existed must not change."""
        report = self.report(diagnostics=None)
        self.assertEqual(report.grounding_reasons()['revenue'], 'no_external_evidence')

    def test_an_unreachable_source_never_produces_a_contradiction(self):
        """The invariant this protects: a failed lookup is not a negative finding."""
        report = self.report(diagnostics={'sec_edgar': 'timeout'})
        self.assertNotEqual(report.category_states()['revenue'], 'contradicted')
        self.assertEqual(report.verifiability_stats()['contradicted'], 0)


class TheEngineRecordsWhatTheSourceDidTests(TestCase):

    def setUp(self):
        from .truth_delta_models import ClaimedDatapoint
        self.owner = User.objects.create_user('su_engine_owner', password='x')
        self.document = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Apple Inc.',
            uploaded_by=self.owner, document_type='pitch_deck',
        )
        ClaimedDatapoint.objects.create(
            document=self.document, category='revenue', claimed_value='$416 billion',
            claimed_value_numeric=416_000_000_000.0)

    def test_a_failed_lookup_is_persisted_on_the_report(self):
        """
        Without this the artifact cannot tell run 4's reader whether the source
        said nothing or was never reached.
        """
        from .truth_delta_engine import TruthDeltaEngine
        engine = TruthDeltaEngine()

        def record_failure(document, company_name, domain=None, diagnostics=None):
            if diagnostics is not None:
                diagnostics['sec_edgar'] = 'timeout'
            return []

        with mock.patch('zelda_api.truth_delta_engine.data_source_manager') as sources:
            sources.create_observed_datapoints.side_effect = record_failure
            sources.fetch_news_headlines.return_value = []
            report = engine.verify_document(self.document.id)

        self.assertEqual((report.details or {}).get('source_diagnostics'), {'sec_edgar': 'timeout'})
        self.assertEqual(report.grounding_reasons().get('revenue'), 'source_unavailable')

    def test_a_failed_lookup_is_persisted_when_another_source_did_answer(self):
        """
        The engine writes its report from two places: the branch for "nothing
        at all was found", and the main path taken as soon as ANY source
        answered. Run 4's A1 and A2 took the main path -- news headlines came
        back while EDGAR did not -- so a test that only covers the first branch
        leaves the case those subjects actually hit unguarded.
        """
        from .truth_delta_engine import TruthDeltaEngine
        engine = TruthDeltaEngine()

        def record_failure(document, company_name, domain=None, diagnostics=None):
            if diagnostics is not None:
                diagnostics['sec_edgar'] = 'timeout'
            return []

        claude = {'overall_truth_score': 50.0, 'credibility_risk': 'medium',
                  'summary': 'x', 'per_claim': [{'category': 'revenue', 'observed': 'no external data found'}]}
        with mock.patch('zelda_api.truth_delta_engine.data_source_manager') as sources, \
             mock.patch.object(engine, '_call_claude_for_verification', return_value=claude):
            sources.create_observed_datapoints.side_effect = record_failure
            # A headline is enough to take the main path, and never enough to
            # verify a figure.
            sources.fetch_news_headlines.return_value = ['Apple reports record quarter']
            report = engine.verify_document(self.document.id)

        self.assertEqual((report.details or {}).get('source_diagnostics'), {'sec_edgar': 'timeout'})
        self.assertEqual(report.grounding_reasons().get('revenue'), 'source_unavailable')
