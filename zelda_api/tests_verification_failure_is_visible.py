"""
A Truth Delta failure must reach the person waiting for the answer.

From the 2026-09-26 walk. The engine hit an OperationalError and what the
user saw was:

    ingest                -> HTTP 201
    message               -> "queued for both Zelda Intelligence and Truth
                              Delta verification"
    status endpoint       -> "analyzed"
    TruthDeltaReport rows -> 0
    the report page       -> "Verification Not Available -- hasn't been run
                              yet for this document"

The memo was written, the pipeline logged success, the API reported success,
and no report existed, with nothing anywhere saying why. The proximate cause
was a local missing migration; the behaviour is general.

The defect is not that verification can fail. It is that FAILED and NOT YET
STARTED are the same state, so a reader cannot tell "still working" from
"this will never arrive". That is the same conflation the grounding layer
already refuses to make one level down -- a source that could not be reached
is not evidence of absence -- applied to the run itself.

    verify_document_truth_delta had no exception handling at all, so a raise
    left nothing recorded anywhere a user can see.

    extract_claims_from_insights caught everything, logged, returned an error
    dict and never queued verification -- so verification silently never ran.

The invariants:

    A FAILURE IS RECORDED. When verification cannot complete, the document
    says so durably. Nothing is inferred from the absence of a report.

    EVERY SURFACE THAT CLAIMS SUCCESS TELLS THE TRUTH. The status endpoint
    and the report page each answered "fine" independently, so each is
    asserted separately.

    SUCCESS CLEARS IT. A later run that works must not leave a stale failure
    showing, or the state becomes permanent once tripped.

    A STALE REPORT IS NOT A CURRENT ANSWER. If an older report exists and a
    newer run failed, the reader is told the retry failed rather than being
    shown the old report as though it were current.

    THE INTERNAL REASON STAYS INTERNAL. The technical cause goes to staff and
    the logs, never to an end user -- the same rule as
    pages/tests_exception_responses.py.
"""
import re
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .truth_delta_engine import TruthDeltaEngine
from .truth_delta_models import ClaimedDatapoint, TruthDeltaReport
from .vector_models import DocumentSource

User = get_user_model()

# A recognisable technical detail, so a test can prove where it did and did
# not travel. Stands in for "no column named engine_version".
INTERNAL_DETAIL = 'no column named engine_version'

# The reader-facing half of the contract, and a DIFFERENT authority from
# verification_state. The state field answers what happened to the run; this
# answers what a reader is permitted to infer from it. verification_failed=True
# proves the application knows the run died; it does not stop a reader seeing a
# red panel above stat cards reading "0 verified" and concluding that Zelda
# checked and found nothing. Only the words do that.
#
# Asserted against the script-stripped page, because `details` reaches the
# browser through json_script -- data in the HTML is not the same as something
# a person is told. Checked for presence in the failure case and absence in the
# success case against this one constant, so neither a typo nor a panel that
# always renders can satisfy it.
NOT_A_FINDING = 'not a finding about the company'

SCRIPTS = re.compile(r'<script.*?</script>', re.DOTALL | re.IGNORECASE)


def readable(html):
    """The page with its <script> blocks removed -- what a reader receives."""
    return SCRIPTS.sub('', html)


class VerificationFailureHarness(TestCase):

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        self.owner = User.objects.create_user('vf_owner', password='x')
        self.document = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Northwind Grid',
            uploaded_by=self.owner, document_type='pitch_deck', status='analyzed',
        )
        ClaimedDatapoint.objects.create(
            document=self.document, category='revenue', claimed_value='$4M',
            claimed_value_numeric=4_000_000.0, unit='$', source_chunk='Insight: Revenue',
            text_excerpt='Revenue of about $4M.',
        )

    def run_failing_verification(self):
        """The real task, with the engine raising the way it did on the walk."""
        from .truth_delta_tasks import verify_document_truth_delta
        with mock.patch.object(TruthDeltaEngine, 'verify_document',
                               side_effect=Exception(INTERNAL_DETAIL)):
            try:
                verify_document_truth_delta(self.document.id)
            except Exception:
                # Celery must still see this as a failed task; whether it
                # propagates is asserted separately below.
                pass
        self.document.refresh_from_db()

    def page(self, as_user=None):
        self.client.force_login(as_user or self.owner)
        response = self.client.get(
            reverse('zelda_api:truth_delta_ui', args=[self.document.id]))
        self.assertEqual(response.status_code, 200)
        return response

    def status_api(self, as_user=None):
        self.client.force_login(as_user or self.owner)
        response = self.client.get(
            reverse('zelda_api:document_status', args=[self.document.id]))
        self.assertEqual(response.status_code, 200)
        return response.json()


class AFailureIsRecordedTests(VerificationFailureHarness):

    def test_the_harness_really_produces_no_report(self):
        """
        Positive control. Every assertion below is about the state left behind
        by a failed run; if a report were somehow created, they would all be
        testing the wrong scenario.
        """
        self.run_failing_verification()
        self.assertFalse(TruthDeltaReport.objects.filter(document=self.document).exists(),
                         'a report was created, so this is not the failure case')

    def test_the_document_records_that_verification_failed(self):
        self.run_failing_verification()
        self.assertIsNotNone(
            self.document.verification_failed_at,
            'verification failed and nothing was recorded, so the page cannot '
            'tell a reader anything')

    def test_the_technical_reason_is_kept_for_diagnosis(self):
        self.run_failing_verification()
        self.assertIn(INTERNAL_DETAIL, self.document.verification_error)

    def test_the_failure_still_reaches_the_operator(self):
        """
        Recording it for the user must not swallow it for us. A caught
        exception that is never re-raised leaves Celery reporting the task as
        succeeded, which is how this stayed invisible.
        """
        from .truth_delta_tasks import verify_document_truth_delta
        with mock.patch.object(TruthDeltaEngine, 'verify_document',
                               side_effect=Exception(INTERNAL_DETAIL)):
            with self.assertRaises(Exception):
                verify_document_truth_delta(self.document.id)

    def test_a_failure_before_verification_is_recorded_too(self):
        """
        The other silent path. extract_claims_from_insights caught everything
        and returned an error dict WITHOUT queueing verification, so the run
        never happened and the page said "hasn't been run yet" -- which was
        true, and useless.
        """
        from .truth_delta_tasks import extract_claims_from_insights
        # A failing DB read, which is what the walk actually hit -- and it is
        # on the path unconditionally, unlike the per-insight create, which a
        # document with no insights never reaches.
        with mock.patch('zelda_api.vector_models.IntelligenceInsight.objects.filter',
                        side_effect=Exception(INTERNAL_DETAIL)):
            try:
                extract_claims_from_insights(self.document.id)
            except Exception:
                pass
        self.document.refresh_from_db()
        self.assertIsNotNone(
            self.document.verification_failed_at,
            'claim extraction died and verification will never run, silently')


class SuccessClearsTheFailureTests(VerificationFailureHarness):

    def test_a_working_rerun_clears_a_previous_failure(self):
        """
        Otherwise the state is permanent once tripped: a document that failed
        yesterday and verified fine today would still be shown as broken.
        """
        self.run_failing_verification()
        self.assertIsNotNone(self.document.verification_failed_at, 'setup did not fail')

        from .truth_delta_tasks import verify_document_truth_delta
        report = TruthDeltaReport.objects.create(
            document=self.document, overall_truth_score=None,
            credibility_risk='unknown', summary='ok', details={})
        with mock.patch.object(TruthDeltaEngine, 'verify_document', return_value=report):
            verify_document_truth_delta(self.document.id)

        self.document.refresh_from_db()
        self.assertIsNone(self.document.verification_failed_at,
                          'a successful run left the old failure showing')
        self.assertEqual(self.document.verification_error, '')

    def test_no_claims_is_not_a_failure(self):
        """
        verify_document returns None when a document has no claims. That is an
        ordinary outcome, not a breakage, and must not be recorded as one.
        """
        from .truth_delta_tasks import verify_document_truth_delta
        with mock.patch.object(TruthDeltaEngine, 'verify_document', return_value=None):
            verify_document_truth_delta(self.document.id)
        self.document.refresh_from_db()
        self.assertIsNone(self.document.verification_failed_at,
                          'having nothing to verify was reported as a failure')


class EverySurfaceTellsTheTruthTests(VerificationFailureHarness):
    """
    The status endpoint and the report page each decided independently that
    everything was fine -- the endpoint because it reports the INTELLIGENCE
    pipeline's status (still 'analyzed'), the page because no report means
    "hasn't been run yet". Asserted separately: a shared conclusion is not a
    shared code path.
    """

    def test_the_status_endpoint_stops_implying_success(self):
        self.run_failing_verification()
        payload = self.status_api()
        self.assertEqual(payload.get('verification_state'), 'failed',
                         'the polling contract still reported a healthy document')

    def test_the_status_endpoint_still_says_pending_before_any_run(self):
        """
        Paired control. A field hardcoded to 'failed' would satisfy the test
        above while destroying the distinction this PR exists to create.
        """
        self.assertEqual(self.status_api().get('verification_state'), 'pending')

    def test_the_status_endpoint_says_complete_once_a_report_exists(self):
        TruthDeltaReport.objects.create(
            document=self.document, overall_truth_score=None,
            credibility_risk='unknown', summary='ok', details={})
        self.assertEqual(self.status_api().get('verification_state'), 'complete')

    def test_the_report_page_distinguishes_failed_from_not_yet_run(self):
        self.run_failing_verification()
        self.assertTrue(self.page().context['verification_failed'],
                        'the page still presents a crash as "not run yet"')

    def test_the_report_page_does_not_cry_failure_before_any_run(self):
        self.assertFalse(self.page().context['verification_failed'])

    def test_a_reader_is_told_in_words_that_it_failed(self):
        """
        A context flag nobody renders is the inert-field failure. The page has
        to actually say something.
        """
        self.run_failing_verification()
        html = self.page().content.decode()
        self.assertIn("couldn't be completed", html)


class AStaleReportIsNotACurrentAnswerTests(VerificationFailureHarness):

    def test_a_newer_failure_is_reported_over_an_older_report(self):
        """
        An old report plus a failed retry is the subtlest case: the report is
        real but no longer current, and showing it alone reads as "verified"
        when the latest attempt did not finish.
        """
        TruthDeltaReport.objects.create(
            document=self.document, overall_truth_score=88.0,
            credibility_risk='low', summary='An older, successful run.', details={})
        self.run_failing_verification()

        self.assertTrue(self.page().context['verification_failed'],
                        'a failed retry was hidden behind a stale report')
        self.assertEqual(self.status_api().get('verification_state'), 'failed')

    def test_a_report_written_after_the_failure_wins(self):
        """
        The opposite order, so the comparison is a real timestamp comparison
        and not "a failure always wins".
        """
        self.run_failing_verification()
        TruthDeltaReport.objects.create(
            document=self.document, overall_truth_score=88.0,
            credibility_risk='low', summary='A later, successful run.', details={})

        self.assertFalse(self.page().context['verification_failed'],
                         'a successful later report was still shown as failed')
        self.assertEqual(self.status_api().get('verification_state'), 'complete')


class TheInternalReasonStaysInternalTests(VerificationFailureHarness):
    """
    Same rule as pages/tests_exception_responses.py: the technical cause is
    for the logs and for staff. An end user gets told that it failed and what
    they can do, never a database error.
    """

    def test_the_owner_is_not_shown_the_technical_cause(self):
        self.run_failing_verification()
        self.assertNotIn(INTERNAL_DETAIL, self.page().content.decode())

    def test_the_owner_is_not_shown_the_technical_cause_by_the_api(self):
        self.run_failing_verification()
        self.assertNotIn(INTERNAL_DETAIL, str(self.status_api()))

    def test_staff_can_see_the_technical_cause(self):
        """
        Paired positive. Without this, hiding the reason from everyone would
        pass the two tests above while making the failure undiagnosable.
        """
        self.run_failing_verification()
        staff = User.objects.create_user('vf_staff', password='x', is_staff=True)
        self.assertIn(INTERNAL_DETAIL, self.page(as_user=staff).content.decode())


class AFailedRunIsNotAFindingTests(VerificationFailureHarness):
    """
    The lesson this whole PR turns on:

        A failed verification run is not evidence that verification found
        nothing.

    It is the Truth Delta analogue of the source-grounding rule -- a source
    that could not be reached is not evidence of absence -- one level up, at
    the run rather than the source. Without it the system converts an
    infrastructure failure into an apparently meaningful statement about the
    company, which is the single most damaging thing this surface can do to a
    business that did nothing wrong.

    This is a contract, not copy. The sentence was previously present only by
    convention, so a later edit could remove it while every state assertion
    kept passing.
    """

    def test_a_failed_run_says_it_is_not_a_finding_about_the_company(self):
        self.run_failing_verification()
        self.assertIn(NOT_A_FINDING, readable(self.page().content.decode()),
                      'the page reported a failure without saying it is not a '
                      'judgement about the company, so zeroes read as findings')

    def test_a_completed_run_does_not_carry_the_disclaimer(self):
        """
        Paired negative. A panel rendered unconditionally would satisfy the
        test above while telling every reader of every healthy report that it
        is not a finding -- which is both false and would train readers to
        ignore the notice when it matters.
        """
        TruthDeltaReport.objects.create(
            document=self.document, overall_truth_score=88.0,
            credibility_risk='low', summary='A completed run.', details={})
        self.assertNotIn(NOT_A_FINDING, readable(self.page().content.decode()),
                         'a healthy report was disclaimed as not a finding')

    def test_the_failure_notice_does_not_name_a_credibility_verdict(self):
        """
        The adjacent way this goes wrong: a failure panel that also reports a
        risk band or a score would be asserting a judgement the run never
        reached. Nothing was computed, so nothing may be characterised.
        """
        self.run_failing_verification()
        page = readable(self.page().content.decode())
        notice = page.split(NOT_A_FINDING)[0][-600:]
        for verdict in ('unsupported claim', 'contradicted', 'high risk', 'critical'):
            with self.subTest(verdict=verdict):
                self.assertNotIn(verdict, notice.lower())
