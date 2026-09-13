"""
A user who leaves the page must still learn how their analysis ended.

The precise defect: while the user is on the valuation report page it polls
DocumentStatusView and does show an error state, so failures were never
"invisible". What was missing is anything durable -- close the tab and neither
success nor failure ever reached you.

These tests pin the durable half: one notification per terminal state, no
duplicates, a real destination, and never a raw exception string in front of a
user.

NOTE: zelda_api is excluded from the blocking CI job, so run this module
explicitly when touching the pipeline's terminal states.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from notifications.models import Notification
from zelda_api.terminal_notifications import (
    ANALYSIS_FAILED, ANALYSIS_READY, notify_terminal_state,
)
from zelda_api.vector_models import DocumentSource

User = get_user_model()


class TerminalNotificationTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('tn_owner', password='x')
        self.document = DocumentSource.objects.create(
            filename='deck.pdf',
            document_type='business_valuation',
            source_entity='Harbour Facilities',
            uploaded_by=self.user,
            status='analyzing',
        )

    def _notifications(self):
        return Notification.objects.filter(recipient=self.user)

    def test_success_notifies_the_owner_with_a_link_to_the_report(self):
        notify_terminal_state(self.document, succeeded=True)

        note = self._notifications().get()
        self.assertEqual(note.notification_type, ANALYSIS_READY)
        self.assertIn('ready', note.message.lower())
        self.assertEqual(note.target_url, '/api/v1/zelda/valuation/%d/' % self.document.id)

    def test_failure_notifies_the_owner(self):
        notify_terminal_state(self.document, succeeded=False)

        note = self._notifications().get()
        self.assertEqual(note.notification_type, ANALYSIS_FAILED)
        self.assertIn("couldn't complete", note.message.lower())

    def test_failure_message_never_leaks_the_exception(self):
        """
        error_message holds the raw exception for staff. The user gets a stable
        sentence -- a raw str(exc) means nothing to them and can expose
        internals.
        """
        self.document.error_message = 'KeyError: OPENAI_API_KEY missing from env'
        self.document.save(update_fields=['error_message'])

        notify_terminal_state(self.document, succeeded=False)

        message = self._notifications().get().message
        self.assertNotIn('KeyError', message)
        self.assertNotIn('OPENAI_API_KEY', message)

    def test_repeated_saves_do_not_stack_duplicate_notifications(self):
        """post_save fires on every save; a terminal document can be saved again."""
        notify_terminal_state(self.document, succeeded=False)
        notify_terminal_state(self.document, succeeded=False)
        notify_terminal_state(self.document, succeeded=False)

        self.assertEqual(self._notifications().count(), 1)

    def test_success_and_failure_are_distinct_notifications(self):
        notify_terminal_state(self.document, succeeded=True)
        notify_terminal_state(self.document, succeeded=False)

        self.assertEqual(
            sorted(self._notifications().values_list('notification_type', flat=True)),
            [ANALYSIS_FAILED, ANALYSIS_READY])

    def test_a_notification_failure_never_breaks_the_pipeline(self):
        """Best effort: the analysis already succeeded or failed on its own terms."""
        with mock.patch.object(
            Notification.objects, 'get_or_create', side_effect=RuntimeError('db down')
        ):
            notify_terminal_state(self.document, succeeded=True)  # must not raise

        self.assertEqual(self._notifications().count(), 0)


class PayingInvestorNotificationTests(TestCase):
    """
    An investor who spends an analysis on a founder's deck is who asked for it,
    but the document stays owned by the founder. The notification used to go to
    uploaded_by -- confirmed in a real generation: the founder was told "your
    pitch deck analysis is ready" and the investor who paid heard nothing. The
    AnalysisCreditCharge names the payer.
    """

    def setUp(self):
        from zelda_api.models import AnalysisCreditCharge
        self.founder = User.objects.create_user('tn_paid_founder', password='x')
        self.investor = User.objects.create_user('tn_paid_investor', password='x')
        self.document = DocumentSource.objects.create(
            filename='deck.pdf', document_type='pitch_deck', source_entity='Northwind Grid',
            uploaded_by=self.founder, status='analyzing',
        )
        AnalysisCreditCharge.objects.create(document=self.document, user=self.investor, job_type='memo')
        self.document = DocumentSource.objects.get(pk=self.document.pk)

    def test_success_notifies_the_paying_investor_not_the_founder(self):
        notify_terminal_state(self.document, succeeded=True)

        note = Notification.objects.get(recipient=self.investor)
        self.assertEqual(note.notification_type, ANALYSIS_READY)
        self.assertEqual(note.message, "Zelda's analysis of Northwind Grid is ready.")
        self.assertFalse(Notification.objects.filter(recipient=self.founder).exists())

    def test_the_link_is_the_founder_profile_not_the_connection_gated_ic_memo(self):
        notify_terminal_state(self.document, succeeded=True)

        note = Notification.objects.get(recipient=self.investor)
        self.assertEqual(note.target_url, '/accounts/profile/tn_paid_founder/')

    def test_failure_wording_for_the_investor_makes_no_charge_or_upload_claim(self):
        notify_terminal_state(self.document, succeeded=False)

        note = Notification.objects.get(recipient=self.investor)
        self.assertEqual(note.notification_type, ANALYSIS_FAILED)
        self.assertEqual(note.message, "Zelda couldn't complete the analysis of Northwind Grid. Please try again later.")
        self.assertNotIn('charged', note.message.lower())
        self.assertNotIn('upload', note.message.lower())
        self.assertFalse(Notification.objects.filter(recipient=self.founder).exists())

    def test_repeated_terminal_saves_still_notify_the_investor_once(self):
        for _ in range(3):
            notify_terminal_state(self.document, succeeded=False)
        self.assertEqual(Notification.objects.filter(recipient=self.investor).count(), 1)

    def test_the_real_error_signal_notifies_the_paying_investor(self):
        self.document.status = 'error'
        self.document.error_message = 'boom'
        self.document.save()

        note = Notification.objects.get(recipient=self.investor)
        self.assertEqual(note.notification_type, ANALYSIS_FAILED)
        self.assertNotIn('boom', note.message)
        self.assertFalse(Notification.objects.filter(recipient=self.founder).exists())


class ErrorSignalWritesNotificationTests(TestCase):
    """
    Through the real post_save signal rather than by calling the helper, so a
    disconnected receiver fails the test.
    """

    def setUp(self):
        self.user = User.objects.create_user('tn_signal', password='x')
        self.document = DocumentSource.objects.create(
            filename='deck.pdf',
            document_type='pitch_deck',
            source_entity='Northwind Grid',
            uploaded_by=self.user,
            status='analyzing',
        )

    def test_marking_a_document_error_notifies_its_owner(self):
        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 0)

        self.document.status = 'error'
        self.document.error_message = 'boom'
        self.document.save()

        note = Notification.objects.filter(recipient=self.user).get()
        self.assertEqual(note.notification_type, ANALYSIS_FAILED)
        self.assertNotIn('boom', note.message)

    def test_a_document_that_never_fails_notifies_nobody(self):
        self.document.status = 'analyzing'
        self.document.save()
        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 0)


class ValuationSuccessNotifiesTheRequesterTests(TestCase):
    """
    The pitch-deck pipeline reaches notify_document_processed; the valuation
    task never did, so a finished valuation told nobody (its failures were
    already covered by the error signal). For a valuation the uploader is the
    requester -- the ingest view sets uploaded_by to whoever submitted it, founder
    or investor alike.
    """

    def setUp(self):
        self.user = User.objects.create_user('tn_valuation', password='x')
        self.document = DocumentSource.objects.create(
            filename='financials.pdf', document_type='business_valuation', source_entity='Harbour Facilities',
            uploaded_by=self.user, status='analyzing',
        )

    def test_a_finished_valuation_notifies_whoever_requested_it(self):
        from zelda_api.tasks import process_valuation_document_task

        fake_pipeline = mock.Mock()
        fake_pipeline.process_valuation_document.return_value = {
            'status': 'success', 'chunks_created': 1, 'insights_extracted': 1,
        }
        with mock.patch('zelda_api.tasks.intelligence_pipeline', fake_pipeline):
            result = process_valuation_document_task.apply(args=[self.document.id, 'text']).get()

        self.assertEqual(result['status'], 'success')
        note = Notification.objects.get(recipient=self.user)
        self.assertEqual(note.notification_type, ANALYSIS_READY)
        self.assertEqual(note.target_url, '/api/v1/zelda/valuation/%d/' % self.document.id)
