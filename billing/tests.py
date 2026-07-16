"""
Coverage for the Stripe subscription lifecycle: checkout session creation
picks the right price per role, and the webhook handler is the only thing
that flips is_premium (mirrors real Stripe behavior — entitlement changes
only on confirmed webhook events, never on the client-side redirect alone).
"""
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from matchmaking.models import Application, InvestorApplication, SellerApplication, BuyerApplication
from matchmaking.tests import _mock_embedding_generation
from .models import Subscription

User = get_user_model()

FAKE_STRIPE_SETTINGS = dict(
    STRIPE_SECRET_KEY='sk_test_fake',
    STRIPE_PUBLISHABLE_KEY='pk_test_fake',
    STRIPE_WEBHOOK_SECRET='whsec_fake',
    STRIPE_FOUNDER_PRICE_ID='price_founder_fake',
    STRIPE_INVESTOR_PRICE_ID='price_investor_fake',
    STRIPE_SELLER_PRICE_ID='price_seller_fake',
    STRIPE_BUYER_PRICE_ID='price_buyer_fake',
)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], **FAKE_STRIPE_SETTINGS)
class CheckoutSessionTests(TestCase):
    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('founder_billing', password='x')
        Application.objects.create(
            user=self.founder_user, founder_name='F', email='f@t.com',
            company_name='FCo', sector='SaaS', stage='Seed', description='test', is_private=False,
        )
        self.investor_user = User.objects.create_user('investor_billing', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', email='i@t.com',
            company_name='ICo', investment_focus='SaaS', investment_stage='Seed', is_private=False,
        )
        self.seller_user = User.objects.create_user('seller_billing', password='x')
        SellerApplication.objects.create(
            user=self.seller_user, seller_name='S', email='s@t.com',
            company_name='SCo', description='test business',
        )
        self.buyer_user = User.objects.create_user('buyer_billing', password='x')
        BuyerApplication.objects.create(
            user=self.buyer_user, full_name='B', email='b@t.com',
            company_name='BCo', acquisition_thesis='test thesis',
        )

    @mock.patch('billing.views.stripe.checkout.Session.create')
    def test_founder_checkout_uses_founder_price(self, mock_create):
        mock_create.return_value = mock.Mock(url='https://checkout.stripe.com/fake-founder')
        self.client.force_login(self.founder_user)

        response = self.client.post(reverse('billing:create_checkout_session'))

        self.assertRedirects(response, 'https://checkout.stripe.com/fake-founder', fetch_redirect_response=False)
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs['line_items'][0]['price'], 'price_founder_fake')
        self.assertEqual(kwargs['metadata']['plan'], Subscription.Plan.FOUNDER_PREMIUM)

    @mock.patch('billing.views.stripe.checkout.Session.create')
    def test_investor_checkout_uses_investor_price(self, mock_create):
        mock_create.return_value = mock.Mock(url='https://checkout.stripe.com/fake-investor')
        self.client.force_login(self.investor_user)

        response = self.client.post(reverse('billing:create_checkout_session'))

        self.assertRedirects(response, 'https://checkout.stripe.com/fake-investor', fetch_redirect_response=False)
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs['line_items'][0]['price'], 'price_investor_fake')
        self.assertEqual(kwargs['metadata']['plan'], Subscription.Plan.INVESTOR_PREMIUM)

    @mock.patch('billing.views.stripe.checkout.Session.create')
    def test_seller_checkout_uses_seller_price(self, mock_create):
        mock_create.return_value = mock.Mock(url='https://checkout.stripe.com/fake-seller')
        self.client.force_login(self.seller_user)

        response = self.client.post(reverse('billing:create_checkout_session'))

        self.assertRedirects(response, 'https://checkout.stripe.com/fake-seller', fetch_redirect_response=False)
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs['line_items'][0]['price'], 'price_seller_fake')
        self.assertEqual(kwargs['metadata']['plan'], Subscription.Plan.SELLER_PREMIUM)

    @mock.patch('billing.views.stripe.checkout.Session.create')
    def test_buyer_checkout_uses_buyer_price(self, mock_create):
        mock_create.return_value = mock.Mock(url='https://checkout.stripe.com/fake-buyer')
        self.client.force_login(self.buyer_user)

        response = self.client.post(reverse('billing:create_checkout_session'))

        self.assertRedirects(response, 'https://checkout.stripe.com/fake-buyer', fetch_redirect_response=False)
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs['line_items'][0]['price'], 'price_buyer_fake')
        self.assertEqual(kwargs['metadata']['plan'], Subscription.Plan.BUYER_PREMIUM)

    def test_checkout_blocked_without_a_role_profile(self):
        bare_user = User.objects.create_user('no_role_user', password='x')
        self.client.force_login(bare_user)

        response = self.client.post(reverse('billing:create_checkout_session'), follow=True)

        self.assertContains(response, "Complete your founder, investor, seller, or buyer profile")
        self.assertEqual(Subscription.objects.count(), 0)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], **FAKE_STRIPE_SETTINGS)
class WebhookLifecycleTests(TestCase):
    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('webhook_founder', password='x')
        self.founder_app = Application.objects.create(
            user=self.founder_user, founder_name='F', email='f@t.com',
            company_name='FCo', sector='SaaS', stage='Seed', description='test', is_private=False,
        )

    def _post_webhook(self, event_type, data_object):
        fake_event = {'type': event_type, 'data': {'object': data_object}}
        with mock.patch('billing.views.stripe.Webhook.construct_event', return_value=fake_event):
            return self.client.post(
                reverse('billing:stripe_webhook'),
                data=json.dumps(fake_event),
                content_type='application/json',
                HTTP_STRIPE_SIGNATURE='fake-signature',
            )

    def test_checkout_completed_activates_premium(self):
        self.assertFalse(self.founder_app.is_premium)

        response = self._post_webhook('checkout.session.completed', {
            'metadata': {'user_id': str(self.founder_user.id), 'plan': Subscription.Plan.FOUNDER_PREMIUM},
            'customer': 'cus_fake123',
            'subscription': 'sub_fake123',
        })

        self.assertEqual(response.status_code, 200)
        self.founder_app.refresh_from_db()
        self.assertTrue(self.founder_app.is_premium)

        sub = Subscription.objects.get(stripe_subscription_id='sub_fake123')
        self.assertEqual(sub.user, self.founder_user)
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)

    def test_subscription_deleted_deactivates_premium(self):
        self._post_webhook('checkout.session.completed', {
            'metadata': {'user_id': str(self.founder_user.id), 'plan': Subscription.Plan.FOUNDER_PREMIUM},
            'customer': 'cus_fake456',
            'subscription': 'sub_fake456',
        })
        self.founder_app.refresh_from_db()
        self.assertTrue(self.founder_app.is_premium)

        response = self._post_webhook('customer.subscription.deleted', {'id': 'sub_fake456'})

        self.assertEqual(response.status_code, 200)
        self.founder_app.refresh_from_db()
        self.assertFalse(self.founder_app.is_premium)
        sub = Subscription.objects.get(stripe_subscription_id='sub_fake456')
        self.assertEqual(sub.status, Subscription.Status.CANCELED)

    def test_invalid_signature_rejected(self):
        with mock.patch('billing.views.stripe.Webhook.construct_event', side_effect=ValueError('bad payload')):
            response = self.client.post(
                reverse('billing:stripe_webhook'),
                data=json.dumps({'type': 'checkout.session.completed'}),
                content_type='application/json',
                HTTP_STRIPE_SIGNATURE='garbage',
            )
        self.assertEqual(response.status_code, 400)
