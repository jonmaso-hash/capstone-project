"""
A run that finds nothing to check is a finished run (B-1).

When claim extraction produced zero claims, verification ran, found nothing,
and wrote nothing. The one authority that answers "where is verification?"
(DocumentSource.verification_state) could only infer from the absence of a
report, so it said 'pending' -- forever:

    status endpoint   -> verification_state 'pending', so a poller never stops
    report page       -> "PENDING VERIFICATION", over a fallback that read
                         "no public data found for this company"
    score endpoint    -> 404, which the page shows as "Verification Unavailable"
    memo context      -> verification 'not_run'

The states this keeps apart:

    never ran                      -> pending
    ran, extracted nothing         -> no_claims
    ran and failed                 -> failed   (tests_verification_failure_is_visible)
    ran and produced a report      -> complete

NO_CLAIMS IS NOT NO PUBLIC DATA. No claim reached a public source, so nothing
about public data was learned. Every surface is checked for the phrase.

THE NEWEST OUTCOME WINS. Each transition is driven through the real task, and
one test leaves a stale timestamp behind on purpose to prove the state does
not depend on the writers having cleared it.

The zero-claims path is the real one: extract_claims_from_insights over a
document with no extractable insights, which queues the real
verify_document_truth_delta against the real engine. Only the hand-off to the
memo is stubbed -- it is asserted, not executed.
"""
import re
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .truth_delta_engine import TruthDeltaEngine
from .truth_delta_models import ClaimedDatapoint, TruthDeltaReport
from .vector_models import DocumentSource

User = get_user_model()

# The existing sentence the page has always had for this case, and which no
# production run could reach. Asserted as the reader receives it.
NO_CLAIMS_SENTENCE = 'No verifiable claims were extracted from this'
NO_PUBLIC_DATA = 'no public data'

SCRIPTS = re.compile(r'<script.*?</script>', re.DOTALL | re.IGNORECASE)


def readable(html):
    """The page with its <script> blocks removed -- what a reader receives."""
    return SCRIPTS.sub('', html)


class NoClaimsHarness(TestCase):

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        self.owner = User.objects.create_user('nc_owner', password='x')
        self.document = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Northwind Grid',
            uploaded_by=self.owner, document_type='pitch_deck', status='analyzed',
        )

    def run_zero_claims_pipeline(self):
        """
        Claim extraction over a document with nothing extractable, which queues
        the real verification task against the real engine. Returns the mock
        standing in for the memo hand-off.
        """
        from . import truth_delta_tasks
        with mock.patch.object(truth_delta_tasks.verify_document_truth_delta, 'delay',
                               side_effect=truth_delta_tasks.verify_document_truth_delta) as queued, \
                mock.patch('zelda_api.tasks.generate_intelligence_memo.delay') as memo:
            result = truth_delta_tasks.extract_claims_from_insights(self.document.id)
        self.assertEqual(result, {'status': 'success', 'claims_created': 0}, 'not the zero-claims path')
        queued.assert_called_once_with(self.document.id)
        self.document.refresh_from_db()
        return memo

    def run_verification_returning(self, outcome):
        """The real task, with the engine's answer fixed: a report or an exception."""
        from .truth_delta_tasks import verify_document_truth_delta
        kwargs = {'side_effect': outcome} if isinstance(outcome, Exception) else {'return_value': outcome}
        with mock.patch.object(TruthDeltaEngine, 'verify_document', **kwargs), \
                mock.patch('zelda_api.tasks.generate_intelligence_memo.delay'):
            try:
                verify_document_truth_delta(self.document.id)
            except Exception:
                pass
        self.document.refresh_from_db()

    def make_report(self, **kwargs):
        fields = dict(document=self.document, overall_truth_score=88.0,
                      credibility_risk='low', summary='A successful run.', details={})
        fields.update(kwargs)
        return TruthDeltaReport.objects.create(**fields)

    def page(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.document.id]))
        self.assertEqual(response.status_code, 200)
        return response

    def status_api(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('zelda_api:document_status', args=[self.document.id]))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def score_api(self):
        self.client.force_login(self.owner)
        return self.client.get(reverse('zelda_api:truth_delta_score', args=[self.document.id]))

    def grounded_verification(self):
        from .grounded_context import GroundedContext
        from .principal import ORIGIN_TASK, Principal
        principal = Principal.for_user(self.owner, ORIGIN_TASK, label='tests_verification_no_claims')
        return GroundedContext.build(principal, self.document).verification


class TheOutcomeIsRecordedTests(NoClaimsHarness):

    def test_the_real_path_writes_no_report(self):
        """Positive control: every test here is about a run that wrote nothing."""
        self.run_zero_claims_pipeline()
        self.assertFalse(ClaimedDatapoint.objects.filter(document=self.document).exists())
        self.assertFalse(TruthDeltaReport.objects.filter(document=self.document).exists())

    def test_the_timestamp_is_persisted(self):
        self.run_zero_claims_pipeline()
        self.assertIsNotNone(self.document.verification_no_claims_at,
                             'a finished run left nothing behind, so it reads as never started')

    def test_the_state_is_no_claims(self):
        self.run_zero_claims_pipeline()
        self.assertEqual(self.document.verification_state, DocumentSource.NO_CLAIMS)

    def test_it_is_not_recorded_as_a_failure(self):
        self.run_zero_claims_pipeline()
        self.assertIsNone(self.document.verification_failed_at)

    def test_the_memo_is_still_queued(self):
        memo = self.run_zero_claims_pipeline()
        memo.assert_called_once_with(self.document.id)


class EverySurfaceSaysNoClaimsTests(NoClaimsHarness):
    """Each surface decided independently before, so each is asserted separately."""

    def test_the_status_endpoint_stops_saying_pending(self):
        self.run_zero_claims_pipeline()
        self.assertEqual(self.status_api().get('verification_state'), 'no_claims',
                         'a poller waiting on this document would never stop')

    def test_the_page_shows_the_no_claims_sentence(self):
        self.run_zero_claims_pipeline()
        response = self.page()
        self.assertIn(NO_CLAIMS_SENTENCE, readable(response.content.decode()))
        self.assertEqual(response.context['credibility_risk'], 'no_claims')
        self.assertFalse(response.context['verification_failed'])

    def test_the_page_never_says_no_public_data(self):
        """Checked against the whole page, scripts included: the fallbacks lived there."""
        self.run_zero_claims_pipeline()
        self.assertNotIn(NO_PUBLIC_DATA, self.page().content.decode().lower())

    def test_the_score_endpoint_answers_with_the_result(self):
        self.run_zero_claims_pipeline()
        response = self.score_api()
        self.assertEqual(response.status_code, 200,
                         'a finished run was served as an error, which the page shows as unavailable')
        payload = response.json()
        self.assertEqual(payload['status'], 'no_claims')
        self.assertEqual(payload['credibility_risk'], 'no_claims')
        self.assertIsNone(payload['overall_truth_score'])
        self.assertNotIn(NO_PUBLIC_DATA, payload['summary'].lower())

    def test_the_memo_context_says_no_claims(self):
        self.run_zero_claims_pipeline()
        self.assertEqual(self.grounded_verification(), 'no_claims')


class AnUntouchedDocumentIsStillPendingTests(NoClaimsHarness):
    """
    Paired controls. A state hardcoded to 'no_claims' would pass every test
    above while destroying the distinction this exists to make.
    """

    def test_state_and_status_endpoint(self):
        self.assertEqual(self.document.verification_state, DocumentSource.PENDING)
        self.assertEqual(self.status_api().get('verification_state'), 'pending')

    def test_page(self):
        response = self.page()
        self.assertEqual(response.context['credibility_risk'], 'pending')
        self.assertNotIn(NO_CLAIMS_SENTENCE, readable(response.content.decode()))
        self.assertNotIn(NO_PUBLIC_DATA, response.content.decode().lower())

    def test_score_endpoint(self):
        self.assertEqual(self.score_api().status_code, 404)

    def test_memo_context(self):
        self.assertEqual(self.grounded_verification(), 'not_run')


class TheNewestOutcomeWinsTests(NoClaimsHarness):

    def test_no_claims_then_a_report(self):
        self.run_zero_claims_pipeline()
        self.run_verification_returning(self.make_report())
        self.assertIsNone(self.document.verification_no_claims_at, 'a report did not supersede no_claims')
        self.assertEqual(self.document.verification_state, DocumentSource.COMPLETE)
        self.assertEqual(self.status_api().get('verification_state'), 'complete')
        self.assertEqual(self.grounded_verification(), 'complete')

    def test_failure_then_no_claims(self):
        self.run_verification_returning(RuntimeError('EDGAR down'))
        self.assertEqual(self.document.verification_state, DocumentSource.FAILED, 'setup did not fail')
        self.run_zero_claims_pipeline()
        self.assertIsNone(self.document.verification_failed_at, 'no_claims did not clear the older failure')
        self.assertEqual(self.document.verification_state, DocumentSource.NO_CLAIMS)
        self.assertFalse(self.page().context['verification_failed'])

    def test_no_claims_then_failure(self):
        self.run_zero_claims_pipeline()
        self.run_verification_returning(RuntimeError('EDGAR down'))
        self.assertIsNone(self.document.verification_no_claims_at, 'a failure did not supersede no_claims')
        self.assertEqual(self.document.verification_state, DocumentSource.FAILED)
        self.assertEqual(self.status_api().get('verification_state'), 'failed')

    def test_report_then_no_claims_hides_the_stale_report(self):
        self.make_report(summary='An older, successful run.')
        self.run_zero_claims_pipeline()
        self.assertEqual(self.document.verification_state, DocumentSource.NO_CLAIMS)
        response = self.page()
        self.assertIsNone(response.context['report'], 'the older report was shown as the current answer')
        self.assertIn(NO_CLAIMS_SENTENCE, readable(response.content.decode()))
        self.assertEqual(self.score_api().json()['status'], 'no_claims')
        self.assertEqual(self.grounded_verification(), 'no_claims')

    def test_a_stale_timestamp_loses_without_being_cleared(self):
        """
        The writers clear superseded timestamps, but the state must not depend
        on it. An old no_claims left in place still loses to a newer report,
        and a newer one still beats an older report.
        """
        report = self.make_report()
        DocumentSource.objects.filter(pk=self.document.pk).update(
            verification_no_claims_at=report.created_at - timedelta(minutes=5))
        self.document.refresh_from_db()
        self.assertEqual(self.document.verification_state, DocumentSource.COMPLETE)

        DocumentSource.objects.filter(pk=self.document.pk).update(
            verification_no_claims_at=report.created_at + timedelta(minutes=5))
        self.document.refresh_from_db()
        self.assertEqual(self.document.verification_state, DocumentSource.NO_CLAIMS)

    def test_a_stale_no_claims_loses_to_a_newer_failure(self):
        now = timezone.now()
        DocumentSource.objects.filter(pk=self.document.pk).update(
            verification_no_claims_at=now - timedelta(minutes=5), verification_failed_at=now)
        self.document.refresh_from_db()
        self.assertEqual(self.document.verification_state, DocumentSource.FAILED)
