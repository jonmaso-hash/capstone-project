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
