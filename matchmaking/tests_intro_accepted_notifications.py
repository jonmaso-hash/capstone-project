"""
Accepting an introduction tells the person who asked for it.

Before this, both accept handlers saved ACCEPTED and opened the chat channel
but wrote no notification, so the requester only learned about it by checking
their dashboard. The funded/closed confirmations right beside them already
notified, which is the pattern followed here.

The recipient is the party who did not respond: the requester for a founder-,
investor-, seller- or buyer-initiated introduction, and the non-responding side
for a staff introduction. It is written only on the transition into ACCEPTED,
so posting ACCEPTED again cannot stack a second one.

Stream is mocked: ensure_deal_channel makes real API calls whenever Stream keys
are configured, and the channel is not what these tests are about.
"""
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve, reverse

from notifications.models import Notification
from .models import (
    AcquisitionConnection, Application, BuyerApplication, Connection, InvestorApplication,
    SellerApplication, can_view_acquisition_deal_workspace, can_view_deal_workspace,
)
from .tests import _mock_embedding_generation
from . import views

User = get_user_model()


class _StreamMocked(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        patcher = mock.patch('matchmaking.views.ensure_deal_channel', return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _post(self, url_name, user, connection, action):
        self.client.force_login(user)
        return self.client.post(
            reverse(url_name), data=json.dumps({'id': connection.id, 'action': action}),
            content_type='application/json',
        )


class FounderInvestorIntroductionAcceptedTests(_StreamMocked):

    def setUp(self):
        super().setUp()
        self.founder_user = User.objects.create_user('ia_founder', password='x')
        self.founder = Application.objects.create(
            user=self.founder_user, company_name='Northwind Grid', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.investor_user = User.objects.create_user('ia_investor', password='x')
        self.investor = InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', email='i@t.com', company_name='Harbor Capital',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.stranger = User.objects.create_user('ia_stranger', password='x')

    def _connection(self, initiated_by, status='PENDING'):
        return Connection.objects.create(
            founder=self.founder, investor=self.investor, status=status, initiated_by=initiated_by,
        )

    def _act(self, user, connection, action):
        return self._post('matchmaking:connection_action', user, connection, action)

    def test_founder_request_accepted_by_the_investor_notifies_the_founder(self):
        connection = self._connection('FOUNDER')

        response = self._act(self.investor_user, connection, 'ACCEPTED')

        self.assertEqual(response.json()['new_status'], 'ACCEPTED')
        note = Notification.objects.get(recipient=self.founder_user)
        self.assertEqual(note.notification_type, 'INTRO_ACCEPTED')
        self.assertEqual(note.sender, self.investor_user)
        self.assertEqual(note.message, 'Harbor Capital accepted your introduction request — your Deal Room is open.')
        self.assertFalse(Notification.objects.filter(recipient=self.investor_user).exists())

    def test_the_link_is_a_deal_room_the_requester_is_allowed_into(self):
        connection = self._connection('FOUNDER')
        self._act(self.investor_user, connection, 'ACCEPTED')

        note = Notification.objects.get(recipient=self.founder_user)
        match = resolve(note.target_url)
        self.assertEqual(match.func, views.deal_workspace_view)
        self.assertEqual(int(match.kwargs['connection_id']), connection.id)
        connection.refresh_from_db()
        self.assertTrue(can_view_deal_workspace(self.founder_user, connection))

    def test_investor_request_accepted_by_the_founder_notifies_the_investor(self):
        connection = self._connection('INVESTOR')

        self._act(self.founder_user, connection, 'ACCEPTED')

        note = Notification.objects.get(recipient=self.investor_user)
        self.assertEqual(note.message, 'Northwind Grid accepted your introduction request — your Deal Room is open.')
        self.assertFalse(Notification.objects.filter(recipient=self.founder_user).exists())

    def test_a_staff_introduction_notifies_the_party_who_did_not_respond(self):
        connection = self._connection('STAFF')

        self._act(self.founder_user, connection, 'ACCEPTED')

        note = Notification.objects.get(recipient=self.investor_user)
        self.assertEqual(note.message, 'Northwind Grid accepted the introduction — your Deal Room is open.')
        self.assertFalse(Notification.objects.filter(recipient=self.founder_user).exists())

    def test_posting_accepted_again_does_not_notify_twice(self):
        connection = self._connection('FOUNDER')

        self._act(self.investor_user, connection, 'ACCEPTED')
        self._act(self.investor_user, connection, 'ACCEPTED')

        self.assertEqual(Notification.objects.filter(recipient=self.founder_user).count(), 1)

    def test_declining_notifies_nobody(self):
        connection = self._connection('FOUNDER')

        self._act(self.investor_user, connection, 'DECLINED')

        self.assertEqual(Notification.objects.count(), 0)

    def test_someone_who_is_not_the_responder_cannot_accept_and_nobody_is_notified(self):
        connection = self._connection('FOUNDER')

        for user in (self.stranger, self.founder_user):
            self.assertEqual(self._act(user, connection, 'ACCEPTED').status_code, 403)

        connection.refresh_from_db()
        self.assertEqual(connection.status, 'PENDING')
        self.assertEqual(Notification.objects.count(), 0)

    def test_a_notification_failure_does_not_undo_the_acceptance(self):
        connection = self._connection('FOUNDER')

        with mock.patch.object(Notification.objects, 'create', side_effect=RuntimeError('db down')):
            response = self._act(self.investor_user, connection, 'ACCEPTED')

        self.assertEqual(response.status_code, 200)
        connection.refresh_from_db()
        self.assertEqual(connection.status, 'ACCEPTED')


class SellerBuyerIntroductionAcceptedTests(_StreamMocked):

    def setUp(self):
        super().setUp()
        self.seller_user = User.objects.create_user('ia_seller', password='x')
        self.seller = SellerApplication.objects.create(
            user=self.seller_user, company_name='Harbour Facilities', seller_name='Seller',
            email='s@t.com', description='A business.',
        )
        self.buyer_user = User.objects.create_user('ia_buyer', password='x')
        self.buyer = BuyerApplication.objects.create(
            user=self.buyer_user, full_name='Buyer', email='b@t.com', phone='555-0100',
            company_name='Keel Acquisitions', website='https://keel.example',
            acquisition_thesis='We acquire things.', budget_min=100, budget_max=200,
        )

    def _connection(self, initiated_by, status='PENDING'):
        return AcquisitionConnection.objects.create(
            seller=self.seller, buyer=self.buyer, status=status, initiated_by=initiated_by,
        )

    def _act(self, user, connection, action):
        return self._post('matchmaking:acquisition_connection_action', user, connection, action)

    def test_seller_request_accepted_by_the_buyer_notifies_the_seller_with_the_deal_room(self):
        connection = self._connection('SELLER')

        response = self._act(self.buyer_user, connection, 'ACCEPTED')

        self.assertEqual(response.json()['new_status'], 'ACCEPTED')
        note = Notification.objects.get(recipient=self.seller_user)
        self.assertEqual(note.notification_type, 'INTRO_ACCEPTED')
        self.assertEqual(note.message, 'Keel Acquisitions accepted your introduction request — your Deal Room is open.')
        match = resolve(note.target_url)
        self.assertEqual(match.func, views.acquisition_deal_workspace_view)
        connection.refresh_from_db()
        self.assertTrue(can_view_acquisition_deal_workspace(self.seller_user, connection))
        self.assertFalse(Notification.objects.filter(recipient=self.buyer_user).exists())

    def test_buyer_request_accepted_by_the_seller_notifies_the_buyer(self):
        connection = self._connection('BUYER')

        self._act(self.seller_user, connection, 'ACCEPTED')

        note = Notification.objects.get(recipient=self.buyer_user)
        self.assertEqual(note.message, 'Harbour Facilities accepted your introduction request — your Deal Room is open.')
        self.assertFalse(Notification.objects.filter(recipient=self.seller_user).exists())

    def test_a_staff_introduction_notifies_the_party_who_did_not_respond(self):
        connection = self._connection('STAFF')

        self._act(self.seller_user, connection, 'ACCEPTED')

        note = Notification.objects.get(recipient=self.buyer_user)
        self.assertEqual(note.message, 'Harbour Facilities accepted the introduction — your Deal Room is open.')

    def test_posting_accepted_again_does_not_notify_twice(self):
        connection = self._connection('SELLER')

        self._act(self.buyer_user, connection, 'ACCEPTED')
        self._act(self.buyer_user, connection, 'ACCEPTED')

        self.assertEqual(Notification.objects.filter(recipient=self.seller_user).count(), 1)

    def test_declining_notifies_nobody(self):
        connection = self._connection('SELLER')

        self._act(self.buyer_user, connection, 'DECLINED')

        self.assertEqual(Notification.objects.count(), 0)
