"""
The wire, not the ends.

PR #93 taught the report to distinguish two different declines:

    no_external_evidence   a claim about the WORLD -- we looked, nothing was there
    source_unavailable     a claim about the ATTEMPT -- we could not establish
                           what the source said

and it tested both ends. `resolve_with_diagnostics` was proved to return
'timeout' and to refuse to cache it; `grounding_reasons()` was proved to say
`source_unavailable` when handed a report whose details already carried
`{'sec': 'timeout'}`.

Neither test ran the path between them, and that path did not exist.
`DataSourceManager.create_observed_datapoints` took a `diagnostics` argument
and never wrote to it, so in production a real SEC timeout arrived at the
report as an empty diagnostics dict and was reported as
`no_external_evidence` -- the precise claim #93 was written to prevent. Both
ends green, wire missing.

So every test here asserts at the REPORT, after running the real engine, and
the seam is pushed down to the HTTP boundary (`_find_cik_exact`) so that
everything above it -- resolution, the manager's fetch loop, datapoint
creation, the engine, and the report's own grounding logic -- is the code
that ships.

The control matters as much as the case: the same path with a source that
answered and found nothing must still say `no_external_evidence`. Without it
a test asserting `source_unavailable` could pass because everything had
become `source_unavailable`.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from .truth_delta_engine import TruthDeltaEngine
from .truth_delta_models import ClaimedDatapoint, TruthDeltaReport
from .truth_delta_sources import DataSourceManager, SECFilingsIntegration
from .vector_models import DocumentSource

User = get_user_model()


class ASourceFailureSurvivesToTheReportTests(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.owner = User.objects.create_user('wire_owner', password='x')
        self.document = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Subject Co',
            uploaded_by=self.owner, document_type='pitch_deck', status='analyzed',
        )
        ClaimedDatapoint.objects.create(
            document=self.document, category='revenue',
            claimed_value='$416 billion', claimed_value_numeric=416_000_000_000.0,
            unit='$', source_chunk='Insight: Revenue',
            text_excerpt='Total revenue for fiscal 2025 was approximately $416 billion.',
        )

    def verify_with_sec_answering(self, resolution):
        """
        Runs the REAL engine with SEC's HTTP boundary answering `resolution`.

        Only `_find_cik_exact` is stubbed -- the lowest point where a network
        answer enters. Resolution, the manager's fetch loop, datapoint
        creation and the report's grounding all run for real, which is the
        whole point: the defect this file exists for lived between them.

        News and Crunchbase are held out so the test cannot make a live call
        and cannot contribute diagnostics of their own; SEC is the source
        under test.
        """
        with mock.patch.object(DataSourceManager, 'INTEGRATIONS', {'sec': SECFilingsIntegration}), \
             mock.patch.object(DataSourceManager, 'fetch_news_headlines', return_value=[]), \
             mock.patch.object(SECFilingsIntegration, '_find_cik_exact', return_value=resolution):
            report = TruthDeltaEngine().verify_document(self.document.id)
        self.assertIsNotNone(report, 'the engine produced no report at all')
        return report

    # --- the case the wire exists for ------------------------------------
    def test_a_sec_timeout_reaches_the_report_as_source_unavailable(self):
        report = self.verify_with_sec_answering((None, 'timeout'))
        self.assertEqual(report.grounding_reasons()['revenue'], 'source_unavailable')

    def test_a_request_error_reaches_the_report_as_source_unavailable(self):
        report = self.verify_with_sec_answering((None, 'request_error'))
        self.assertEqual(report.grounding_reasons()['revenue'], 'source_unavailable')

    def test_the_diagnostics_actually_arrive_in_the_stored_report(self):
        """
        The mechanism, asserted separately from the meaning: if the dict is
        empty the reason above can only ever be a coincidence.
        """
        report = self.verify_with_sec_answering((None, 'timeout'))
        diagnostics = (report.details or {}).get('source_diagnostics') or {}
        self.assertTrue(diagnostics, 'no diagnostics were recorded for a failed source')
        self.assertIn('timeout', diagnostics.values())

    # --- controls: the same path must still tell the other story ---------
    def test_a_source_that_answered_and_found_nothing_is_still_an_absence(self):
        """
        The control that gives the tests above their meaning. A successful
        query with no match is evidence about the company, and must NOT be
        reported as an unreachable source.
        """
        report = self.verify_with_sec_answering((None, 'not_found'))
        self.assertEqual(report.grounding_reasons()['revenue'], 'no_external_evidence')

    def test_an_unidentifiable_company_is_not_an_unreachable_source(self):
        """
        Ambiguity is the resolver refusing to choose between filers, not SEC
        failing to answer. It is not a source failure, and must not borrow
        the vocabulary of one.
        """
        report = self.verify_with_sec_answering((None, 'ambiguous'))
        self.assertEqual(report.grounding_reasons()['revenue'], 'no_external_evidence')

    # --- the invariant the whole thing protects --------------------------
    def test_an_unreachable_source_never_produces_a_contradiction(self):
        report = self.verify_with_sec_answering((None, 'timeout'))
        self.assertNotEqual(report.category_states()['revenue'], 'contradicted')
        self.assertEqual(report.verifiability_stats()['contradicted'], 0)
