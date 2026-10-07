import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from matchmaking.models import Application, BuyerApplication, InvestorApplication
from zelda_api.vector_models import DocumentSource

from .models import (
    TruthDeltaCreditPurchase,
    TruthDeltaCreditRedemption,
    TruthDeltaCreditWallet,
    ZeldaOrder,
)
from .zelda_catalog import role_catalog
from .zelda_views import handle_truth_delta_credit_event


User = get_user_model()


class TruthDeltaCreditCatalogTests(TestCase):
    def test_founder_keeps_owner_truth_delta_price_and_no_credit_pack(self):
        user = User.objects.create_user('credit_founder', password='x')
        Application.objects.create(
            user=user,
            company_name='Founder Co',
            founder_name='Founder',
            email='founder@example.com',
            description='Test',
            sector='SaaS',
            stage='Seed',
        )

        products = {p['key']: p for p in role_catalog(user)}

        self.assertEqual(products['truth_delta']['amount'], 1999)
        self.assertNotIn('truth_delta_diligence', products)
        self.assertNotIn('truth_delta_credit_pack', products)

    def test_investor_and_buyer_get_only_diligence_truth_delta_products(self):
        investor = User.objects.create_user('credit_investor_catalog', password='x')
        InvestorApplication.objects.create(
            user=investor,
            full_name='Investor',
            company_name='Fund',
            email='investor@example.com',
            investment_focus='SaaS',
            investment_stage='Seed',
        )
        buyer = User.objects.create_user('credit_buyer_catalog', password='x')
        BuyerApplication.objects.create(
            user=buyer,
            full_name='Buyer',
            company_name='Acquirer',
            email='buyer@example.com',
        )

        for user in (investor, buyer):
            with self.subTest(user=user.username):
                products = {p['key']: p for p in role_catalog(user)}
                self.assertEqual(set(products), {'truth_delta_diligence', 'truth_delta_credit_pack'})
                self.assertEqual(products['truth_delta_diligence']['amount'], 1000)
                self.assertEqual(products['truth_delta_credit_pack']['amount'], 2500)


class TruthDeltaCreditFlowTests(TestCase):
    def setUp(self):
        self.investor_user = User.objects.create_user(
            'credit_investor',
            email='investor@example.com',
            password='x',
        )
        InvestorApplication.objects.create(
            user=self.investor_user,
            full_name='Investor',
            company_name='Fund',
            email='investor@example.com',
            investment_focus='SaaS',
            investment_stage='Seed',
        )
        self.founder_user = User.objects.create_user('credit_owner_founder', password='x')
        Application.objects.create(
            user=self.founder_user,
            company_name='Founder Co',
            founder_name='Founder',
            email='founder2@example.com',
            description='Test',
            sector='SaaS',
            stage='Seed',
        )
        self.source = DocumentSource.objects.create(
            uploaded_by=self.investor_user,
            source_entity='Target Co',
            filename='target.txt',
            raw_text_full='Target company evidence. ' * 30,
            raw_text_preview='Target company evidence.',
            is_external_subject=True,
            is_product_input=True,
            document_type='research_report',
            status='uploaded',
        )

    def _credit_session(self, purchase, **overrides):
        session = {
            'id': purchase.stripe_session_id,
            'mode': 'payment',
            'currency': 'usd',
            'amount_total': purchase.amount,
            'payment_status': 'paid',
            'status': 'complete',
            'metadata': {
                'purpose': 'truth_delta_credit_pack',
                'credit_purchase_id': str(purchase.pk),
                'user_id': str(purchase.user_id),
            },
        }
        session.update(overrides)
        return session

    @mock.patch('billing.zelda_views.stripe_price', return_value='price_credit_pack')
    @mock.patch('billing.zelda_views.stripe.checkout.Session.create')
    def test_credit_pack_checkout_does_not_require_company_evidence(self, create, price):
        create.return_value = {'id': 'cs_credit_pack', 'url': 'https://checkout.stripe.com/c/credits'}
        self.client.force_login(self.investor_user)

        response = self.client.post(
            reverse('billing:truth_delta_credit_pack_checkout'),
            data=json.dumps({}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['checkout_url'], 'https://checkout.stripe.com/c/credits')
        purchase = TruthDeltaCreditPurchase.objects.get()
        self.assertEqual(purchase.amount, 2500)
        self.assertEqual(purchase.credits, 3)
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs['line_items'], [{'price': 'price_credit_pack', 'quantity': 1}])
        self.assertEqual(kwargs['metadata']['purpose'], 'truth_delta_credit_pack')
        self.assertNotIn('document_id', kwargs['metadata'])

    def test_duplicate_paid_events_grant_exactly_three_credits_once(self):
        purchase = TruthDeltaCreditPurchase.objects.create(
            user=self.investor_user,
            stripe_session_id='cs_credit_paid',
        )
        session = self._credit_session(purchase)

        handle_truth_delta_credit_event('checkout.session.completed', session)
        handle_truth_delta_credit_event('checkout.session.completed', session)

        purchase.refresh_from_db()
        wallet = TruthDeltaCreditWallet.objects.get(user=self.investor_user)
        self.assertEqual(purchase.status, 'paid')
        self.assertIsNotNone(purchase.paid_at)
        self.assertEqual(wallet.balance, 3)

    @mock.patch('billing.tasks.fulfill_zelda_order.delay')
    def test_redeem_consumes_one_credit_and_duplicate_same_evidence_does_not_spend_again(self, fulfill):
        wallet = TruthDeltaCreditWallet.objects.create(user=self.investor_user, balance=3)
        self.client.force_login(self.investor_user)

        with self.captureOnCommitCallbacks(execute=True):
            first = self.client.post(
                reverse('billing:truth_delta_credit_redeem'),
                data=json.dumps({'document_id': self.source.id}),
                content_type='application/json',
            )

        self.assertEqual(first.status_code, 200)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 2)
        order = ZeldaOrder.objects.get(user=self.investor_user)
        self.assertEqual(order.product, 'truth_delta_diligence')
        self.assertEqual(order.reports, ['truth_delta'])
        self.assertEqual(order.amount, 0)
        self.assertEqual(order.status, 'paid')
        self.assertTrue(TruthDeltaCreditRedemption.objects.filter(wallet=wallet, order=order).exists())
        fulfill.assert_called_once_with(str(order.id))

        second = self.client.post(
            reverse('billing:truth_delta_credit_redeem'),
            data=json.dumps({'document_id': self.source.id}),
            content_type='application/json',
        )
        self.assertEqual(second.status_code, 200)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 2)
        self.assertEqual(TruthDeltaCreditRedemption.objects.count(), 1)

    def test_redeem_without_credit_is_refused(self):
        self.client.force_login(self.investor_user)
        response = self.client.post(
            reverse('billing:truth_delta_credit_redeem'),
            data=json.dumps({'document_id': self.source.id}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 409)
        self.assertFalse(ZeldaOrder.objects.exists())

    def test_founder_cannot_buy_or_redeem_diligence_credits(self):
        self.client.force_login(self.founder_user)
        checkout = self.client.post(
            reverse('billing:truth_delta_credit_pack_checkout'),
            data=json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(checkout.status_code, 403)

        redeem = self.client.post(
            reverse('billing:truth_delta_credit_redeem'),
            data=json.dumps({'document_id': self.source.id}),
            content_type='application/json',
        )
        self.assertEqual(redeem.status_code, 403)

    @mock.patch('billing.zelda_views.stripe_price', return_value='price_truth_10')
    @mock.patch('billing.zelda_views.stripe.checkout.Session.create')
    def test_investor_single_truth_delta_is_ten_dollars(self, create, price):
        create.return_value = {'id': 'cs_truth_10', 'url': 'https://checkout.stripe.com/c/truth10'}
        self.client.force_login(self.investor_user)

        response = self.client.post(
            reverse('billing:zelda_checkout'),
            data=json.dumps({
                'product': 'truth_delta_diligence',
                'document_id': self.source.id,
                'reports': [],
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        order = ZeldaOrder.objects.get(user=self.investor_user)
        self.assertEqual(order.amount, 1000)
        self.assertEqual(order.reports, ['truth_delta'])
        self.assertEqual(create.call_args.kwargs['line_items'], [{'price': 'price_truth_10', 'quantity': 1}])

    def test_investor_cannot_use_founder_truth_delta_sku(self):
        self.client.force_login(self.investor_user)
        response = self.client.post(
            reverse('billing:zelda_checkout'),
            data=json.dumps({
                'product': 'truth_delta',
                'document_id': self.source.id,
                'reports': [],
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ZeldaOrder.objects.exists())
