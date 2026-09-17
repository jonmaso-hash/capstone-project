"""
D11: an introduction is answered once.

connection_action_view and acquisition_connection_action_view wrote the
requested answer with no look at the current status. The responder could
accept an introduction after declining it (sending an "accepted" notification
and opening the Deal Room long after the decline), decline or re-accept a
FUNDED/CLOSED deal (undoing an outcome both sides had confirmed), rewrite
accepted_at by accepting again, and log another negative training example
with every repeated decline. The funded/closed branches beside them already
refused anything not in the right state.

The invariant:

    Only the current responder can answer an introduction that is still
    awaiting a response, and each introduction is answered once. Repeating
    the same answer is a no-op; changing an existing answer is refused (409);
    nothing refused or repeated has a side effect -- no status change, no
    timestamp, no notification, no training example, no chat channel.

"Awaiting a response" is `pending` in any case (what every user-created
introduction is, and what the dashboard queues match) plus `requested`, the
status Django admin gives staff introductions. The responder check still
comes first, so anyone else gets 403 whatever the state.

Out of scope, deliberately: what Django admin creates, re-requesting or
undoing a declined introduction, staff status overrides, the dashboard
queues, and the funded/closed claim flow.
"""
import json
from contextlib import contextmanager
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from notifications.models import Notification
from .models import (
    AcquisitionConnection, Application, BuyerApplication, Connection, InvestorApplication,
    SellerApplication, can_view_acquisition_deal_workspace, can_view_deal_workspace,
)
from .tests import _mock_embedding_generation

User = get_user_model()

AWAITING = ('pending', 'PENDING', 'requested')


class _Intros(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.old = timezone.now() - timedelta(days=30)
        self.stranger = User.objects.create_user('ao_stranger', password='x')

        self.founder_user = User.objects.create_user('ao_founder', password='x')
        self.founder = Application.objects.create(
            user=self.founder_user, company_name='Northwind Grid', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.investor_user = User.objects.create_user('ao_investor', password='x')
        self.investor = InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', email='i@t.com', company_name='Harbor Capital',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.seller_user = User.objects.create_user('ao_seller', password='x')
        self.seller = SellerApplication.objects.create(
            user=self.seller_user, company_name='Harbour Facilities', seller_name='Seller',
            email='s@t.com', description='A business.',
        )
        self.buyer_user = User.objects.create_user('ao_buyer', password='x')
        self.buyer = BuyerApplication.objects.create(
            user=self.buyer_user, full_name='Buyer', email='b@t.com', company_name='Keel Acquisitions',
            acquisition_thesis='We acquire things.', budget_min=100, budget_max=200,
        )

        self.channel = self._patch('matchmaking.views.ensure_deal_channel', return_value=None)
        self.training = self._patch('matchmaking.views.log_training_example')

    def _patch(self, target, **kwargs):
        patcher = mock.patch(target, **kwargs)
        started = patcher.start()
        self.addCleanup(patcher.stop)
        return started

    def _act(self, user, connection, action):
        self.client.force_login(user)
        return self.client.post(
            reverse(self.url_name), data=json.dumps({'id': connection.id, 'action': action}),
            content_type='application/json',
        )

    @contextmanager
    def _case(self, status):
        """
        One connection for one case in a loop, always cleared afterwards --
        even when an assertion fails -- so the next case can reuse the same
        pair (both models are unique per pair) and reports its own result.
        """
        connection = self._make(status)
        try:
            yield connection
        finally:
            type(connection).objects.filter(pk=connection.pk).delete()
            Notification.objects.all().delete()
            self.channel.reset_mock()
            self.training.reset_mock()

    def _accepted_notifications(self):
        return Notification.objects.filter(notification_type='INTRO_ACCEPTED').count()

    def assert_unchanged_and_silent(self, connection, status, accepted_at):
        connection.refresh_from_db()
        self.assertEqual(connection.status, status)
        self.assertEqual(connection.accepted_at, accepted_at)
        self.assertEqual(self._accepted_notifications(), 0)
        self.channel.assert_not_called()
        self.training.assert_not_called()


class AnswerOnceMatrix:
    """Shared by both connection models; each subclass supplies the specifics."""

    url_name = None
    outcome_states = ()

    # --- an introduction awaiting a response ---

    def test_an_awaiting_introduction_can_be_accepted(self):
        for status in AWAITING:
            with self.subTest(status=status), self._case(status) as connection:
                response = self._act(self.responder, connection, 'ACCEPTED')
                self.assertEqual(response.status_code, 200, response.content[:200])
                self.assertEqual(response.json()['new_status'], 'ACCEPTED')
                connection.refresh_from_db()
                self.assertEqual(connection.status, 'ACCEPTED')
                self.assertIsNotNone(connection.accepted_at)
                self.assertEqual(self._accepted_notifications(), 1)
                self.channel.assert_called_once()
                self.training.assert_not_called()

    def test_an_awaiting_introduction_can_be_declined(self):
        for status in AWAITING:
            with self.subTest(status=status), self._case(status) as connection:
                response = self._act(self.responder, connection, 'DECLINED')
                self.assertEqual(response.status_code, 200, response.content[:200])
                connection.refresh_from_db()
                self.assertEqual(connection.status, 'DECLINED')
                self.assertIsNone(connection.accepted_at)
                self.training.assert_called_once()
                self.assertIn('declined', self.training.call_args.args)
                self.assertEqual(self._accepted_notifications(), 0)
                self.channel.assert_not_called()

    # --- repeating the same answer ---

    def test_accepting_again_is_a_no_op(self):
        connection = self._make('ACCEPTED')
        response = self._act(self.responder, connection, 'ACCEPTED')
        self.assertEqual(response.status_code, 200, response.content[:200])
        self.assertEqual(response.json()['status'], 'success')
        self.assertEqual(response.json()['new_status'], 'ACCEPTED')
        self.assert_unchanged_and_silent(connection, 'ACCEPTED', self.old)

    def test_declining_again_is_a_no_op(self):
        connection = self._make('DECLINED')
        response = self._act(self.responder, connection, 'DECLINED')
        self.assertEqual(response.status_code, 200, response.content[:200])
        self.assertEqual(response.json()['new_status'], 'DECLINED')
        self.assert_unchanged_and_silent(connection, 'DECLINED', None)

    # --- changing an existing answer ---

    def _assert_refused(self, response):
        self.assertEqual(response.status_code, 409, response.content[:200])
        body = response.json()
        self.assertEqual(body['status'], 'error')
        # The dashboards display `error`; the handlers have always sent `message`.
        self.assertEqual(body['message'], body['error'])
        self.assertIn('already', body['message'].lower())

    def test_a_declined_introduction_cannot_be_accepted(self):
        connection = self._make('DECLINED')
        self._assert_refused(self._act(self.responder, connection, 'ACCEPTED'))
        self.assert_unchanged_and_silent(connection, 'DECLINED', None)
        self.assertFalse(self._workspace_open(self.initiator, connection))

    def test_an_accepted_introduction_cannot_be_declined(self):
        connection = self._make('ACCEPTED')
        self._assert_refused(self._act(self.responder, connection, 'DECLINED'))
        self.assert_unchanged_and_silent(connection, 'ACCEPTED', self.old)
        self.assertTrue(self._workspace_open(self.initiator, connection))

    def test_a_claimed_or_confirmed_outcome_cannot_be_changed_by_the_responder(self):
        for status in self.outcome_states:
            for action in ('ACCEPTED', 'DECLINED'):
                with self.subTest(status=status, action=action), self._case(status) as connection:
                    outcome_at = getattr(connection, self.outcome_field)
                    self._assert_refused(self._act(self.responder, connection, action))
                    self.assert_unchanged_and_silent(connection, status, self.old)
                    self.assertEqual(getattr(connection, self.outcome_field), outcome_at)

    # --- who may answer ---

    def test_anyone_but_the_responder_is_refused_in_every_state(self):
        states = AWAITING + ('ACCEPTED', 'DECLINED') + self.outcome_states
        for status in states:
            for user in (self.initiator, self.stranger):
                for action in ('ACCEPTED', 'DECLINED'):
                    with self.subTest(status=status, user=user.username, action=action), \
                            self._case(status) as connection:
                        expected_accepted_at = connection.accepted_at
                        response = self._act(user, connection, action)
                        self.assertEqual(response.status_code, 403, response.content[:200])
                        self.assert_unchanged_and_silent(connection, status, expected_accepted_at)


class FounderInvestorAnswerOnceTests(AnswerOnceMatrix, _Intros):
    url_name = 'matchmaking:connection_action'
    outcome_states = ('FUNDED_PENDING', 'FUNDED')
    outcome_field = 'funded_at'

    def setUp(self):
        super().setUp()
        # An investor-initiated introduction: the founder answers it.
        self.responder = self.founder_user
        self.initiator = self.investor_user

    def _make(self, status):
        answered = status not in AWAITING and status != 'DECLINED'
        return Connection.objects.create(
            founder=self.founder, investor=self.investor, status=status, initiated_by='INVESTOR',
            accepted_at=self.old if answered else None,
            funded_at=self.old if status == 'FUNDED' else None,
        )

    def _workspace_open(self, user, connection):
        connection.refresh_from_db()
        return can_view_deal_workspace(user, connection)


class SellerBuyerAnswerOnceTests(AnswerOnceMatrix, _Intros):
    url_name = 'matchmaking:acquisition_connection_action'
    outcome_states = ('CLOSED_PENDING', 'CLOSED')
    outcome_field = 'closed_at'

    def setUp(self):
        super().setUp()
        # A buyer-initiated introduction: the seller answers it.
        self.responder = self.seller_user
        self.initiator = self.buyer_user

    def _make(self, status):
        answered = status not in AWAITING and status != 'DECLINED'
        return AcquisitionConnection.objects.create(
            seller=self.seller, buyer=self.buyer, status=status, initiated_by='BUYER',
            accepted_at=self.old if answered else None,
            closed_at=self.old if status == 'CLOSED' else None,
        )

    def _workspace_open(self, user, connection):
        connection.refresh_from_db()
        return can_view_acquisition_deal_workspace(user, connection)
