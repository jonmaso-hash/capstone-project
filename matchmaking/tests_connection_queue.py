"""
Accept must never appear on a connection the current user initiated.

Walking the seller journey surfaced this: a seller who requested an intro saw
their own outbound request come back under "Pending Inbound Interest" with
Accept and Decline buttons. The server was right -- both action views compute
`responder_user` as the counterparty and return 403 -- but the page showed no
error at all, the item stayed in the queue, and the only trace was a 403 in the
browser console. A control that looks actionable, does nothing, and says
nothing: the same shape as the investor onboarding blocker.

The invariant these tests pin is the one the action views already enforce:

    a pending connection belongs in your inbound queue only if you are the
    party who may respond to it.

That also means STAFF manual intros stay visible to the founder and the seller,
because `responder_user` falls through to them for anything not initiated by
the counterparty -- which is why the fix excludes your own role rather than
filtering to the counterparty's.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    AcquisitionConnection, Application, BuyerApplication, Connection,
    InvestorApplication, SellerApplication,
)
from .tests import _mock_embedding_generation

User = get_user_model()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SellerInboundQueueTests(TestCase):
    """The journey the defect was found on."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.seller_user = User.objects.create_user('cq_seller', password='x')
        self.seller = SellerApplication.objects.create(
            user=self.seller_user, company_name='Harbour Facilities', seller_name='S',
            email='s@t.com', description='A facilities business.',
            industry='Facilities Services', asking_price=4200000)

        buyer_user = User.objects.create_user('cq_buyer', password='x')
        self.buyer = BuyerApplication.objects.create(
            user=buyer_user, full_name='B', company_name='Meridian Acquisitions',
            email='b@t.com', acquisition_thesis='Buying facilities businesses.',
            budget_min=1000000, budget_max=9000000)

        self.client.force_login(self.seller_user)

    def _queue(self):
        response = self.client.get('/matchmaking/dashboard/seller/')
        self.assertEqual(response.status_code, 200)
        return list(response.context['pending_requests'])

    def test_a_sellers_own_outbound_request_is_not_inbound_interest(self):
        AcquisitionConnection.objects.create(
            seller=self.seller, buyer=self.buyer, status='pending', initiated_by='SELLER')
        self.assertEqual(
            self._queue(), [],
            'the seller initiated this one; Accept on it can only ever 403')

    def test_a_buyer_initiated_request_is_inbound_interest(self):
        conn = AcquisitionConnection.objects.create(
            seller=self.seller, buyer=self.buyer, status='pending', initiated_by='BUYER')
        self.assertEqual([c.id for c in self._queue()], [conn.id])

    def test_a_staff_manual_intro_stays_visible_to_the_seller(self):
        """
        acquisition_connection_action_view makes the seller the responder for
        anything not initiated by the buyer, STAFF included. Filtering to
        initiated_by='BUYER' would have hidden these.
        """
        conn = AcquisitionConnection.objects.create(
            seller=self.seller, buyer=self.buyer, status='pending', initiated_by='STAFF')
        self.assertEqual([c.id for c in self._queue()], [conn.id])

    def test_accepting_your_own_request_is_still_refused_by_the_server(self):
        """Belt and braces: the UI no longer offers it, and the server still says no."""
        conn = AcquisitionConnection.objects.create(
            seller=self.seller, buyer=self.buyer, status='pending', initiated_by='SELLER')
        response = self.client.post(
            reverse('matchmaking:acquisition_connection_action'),
            data={'id': conn.id, 'action': 'ACCEPTED'},
            content_type='application/json')
        self.assertEqual(response.status_code, 403)
        conn.refresh_from_db()
        self.assertEqual(conn.status, 'pending')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FounderInboundQueueTests(TestCase):
    """The same defect on the venture side, found by reading rather than walking."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('cq_founder', password='x')
        self.founder = Application.objects.create(
            user=self.founder_user, company_name='Northwind Grid', founder_name='F',
            email='f@t.com', description='A climate company.',
            sector='Climate Tech', stage='Seed')

        investor_user = User.objects.create_user('cq_investor', password='x')
        self.investor = InvestorApplication.objects.create(
            user=investor_user, full_name='I', company_name='Fund', email='i@t.com',
            investment_focus='Climate Tech', investment_stage='Seed')

        self.client.force_login(self.founder_user)

    def _queue(self):
        response = self.client.get('/matchmaking/dashboard/founder/')
        self.assertEqual(response.status_code, 200)
        return list(response.context['pending_requests'])

    def test_a_founders_own_outbound_request_is_not_inbound_interest(self):
        Connection.objects.create(
            founder=self.founder, investor=self.investor,
            status='pending', initiated_by='FOUNDER')
        self.assertEqual(self._queue(), [])

    def test_an_investor_initiated_request_is_inbound_interest(self):
        conn = Connection.objects.create(
            founder=self.founder, investor=self.investor,
            status='pending', initiated_by='INVESTOR')
        self.assertEqual([c.id for c in self._queue()], [conn.id])

    def test_a_staff_manual_intro_stays_visible_to_the_founder(self):
        conn = Connection.objects.create(
            founder=self.founder, investor=self.investor,
            status='pending', initiated_by='STAFF')
        self.assertEqual([c.id for c in self._queue()], [conn.id])


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CounterpartyQueuesUnchangedTests(TestCase):
    """
    The investor and buyer dashboards already filtered correctly. These pin that,
    so the two sides cannot drift apart again.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.investor_user = User.objects.create_user('cq_inv2', password='x')
        self.investor = InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='Fund2', email='i2@t.com',
            investment_focus='Climate Tech', investment_stage='Seed')
        founder_user = User.objects.create_user('cq_fnd2', password='x')
        self.founder = Application.objects.create(
            user=founder_user, company_name='Gridworks', founder_name='F',
            email='f2@t.com', description='A climate company.',
            sector='Climate Tech', stage='Seed')

    def test_investor_sees_founder_initiated_and_not_their_own(self):
        mine = Connection.objects.create(
            founder=self.founder, investor=self.investor,
            status='pending', initiated_by='INVESTOR')
        theirs = Connection.objects.create(
            founder=Application.objects.create(
                user=User.objects.create_user('cq_fnd3', password='x'),
                company_name='Other', founder_name='O', email='o@t.com',
                description='Another.', sector='Climate Tech', stage='Seed'),
            investor=self.investor, status='pending', initiated_by='FOUNDER')

        self.client.force_login(self.investor_user)
        response = self.client.get('/matchmaking/dashboard/investor/')
        ids = [c.id for c in response.context['pending_requests']]

        self.assertIn(theirs.id, ids)
        self.assertNotIn(mine.id, ids)
