"""
Webhook events through the real Stripe signature boundary.

billing/tests.py patches stripe.Webhook.construct_event to return a plain
dict. A dict has .get(); the stripe.Event the real construct_event returns
does not -- since stripe-python 15, StripeObject is no longer a dict subclass.
That mock hid a production failure: checkout.session.completed raised
AttributeError, the webhook answered 500, and a customer was charged without
ever being granted Premium. Every branch of the handler read its event the
same way, so cancellations and failed renewals were equally broken.

These tests sign payloads exactly as Stripe does --
Stripe-Signature: t=<timestamp>,v1=HMAC-SHA256(secret, "<timestamp>.<payload>")
-- and post them through the unpatched view, so the handler receives the same
object type it receives in production.
"""
import hashlib
import hmac
import json
import time

import stripe
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from matchmaking.models import Application
from matchmaking.tests import _mock_embedding_generation
from notifications.models import Notification
from .models import Subscription
from .tests import FAKE_STRIPE_SETTINGS

User = get_user_model()

SIGNING_SECRET = 'whsec_regression_signing_secret'


def _payload(event_type, data_object):
    return json.dumps({
        'id': 'evt_regression',
        'object': 'event',
        'api_version': '2026-06-24.dahlia',
        'type': event_type,
        'data': {'object': data_object},
    })


def _signature_header(payload, secret=SIGNING_SECRET):
    timestamp = int(time.time())
    signature = hmac.new(
        secret.encode('utf-8'), f'{timestamp}.{payload}'.encode('utf-8'), hashlib.sha256,
    ).hexdigest()
    return f't={timestamp},v1={signature}'


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    **{**FAKE_STRIPE_SETTINGS, 'STRIPE_WEBHOOK_SECRET': SIGNING_SECRET},
)
class SignedWebhookTests(TestCase):
    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('signed_webhook_founder', password='x')
        self.founder_app = Application.objects.create(
            user=self.founder_user, founder_name='F', email='f@t.com',
            company_name='FCo', sector='SaaS', stage='Seed', description='test', is_private=False,
        )

    def _post_signed(self, event_type, data_object, secret=SIGNING_SECRET):
        payload = _payload(event_type, data_object)
        return self.client.post(
            reverse('billing:stripe_webhook'),
            data=payload,
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE=_signature_header(payload, secret),
        )

    def _checkout_completed(self, subscription_id='sub_signed_1', customer_id='cus_signed_1'):
        return self._post_signed('checkout.session.completed', {
            'id': 'cs_test_signed',
            'object': 'checkout.session',
            'mode': 'subscription',
            'client_reference_id': str(self.founder_user.id),
            'customer': customer_id,
            'subscription': subscription_id,
            'metadata': {'user_id': str(self.founder_user.id), 'plan': Subscription.Plan.FOUNDER_PREMIUM},
        })

    def _active_subscription(self, subscription_id, customer_id='cus_signed'):
        """
        Seeds the state checkout would leave, without posting checkout, so each
        lifecycle test reaches its own branch of the handler rather than
        failing -- or passing -- on the checkout branch first.
        """
        Subscription.objects.create(
            user=self.founder_user, plan=Subscription.Plan.FOUNDER_PREMIUM,
            stripe_customer_id=customer_id, stripe_subscription_id=subscription_id,
            status=Subscription.Status.ACTIVE,
        )
        self.founder_app.is_premium = True
        self.founder_app.save(update_fields=['is_premium'])

    def test_a_verified_event_is_a_stripe_object_without_dict_get(self):
        """
        The boundary the mocked tests never crossed. If a future stripe-python
        makes StripeObject a dict again this fails, and the conversion in the
        view can be reconsidered deliberately rather than by accident.
        """
        payload = _payload('checkout.session.completed', {'object': 'checkout.session', 'metadata': {'user_id': '1'}})
        event = stripe.Webhook.construct_event(payload, _signature_header(payload), SIGNING_SECRET)

        self.assertIsInstance(event, stripe.StripeObject)
        self.assertNotIsInstance(event['data']['object'], dict)
        with self.assertRaises(AttributeError):
            event['data']['object'].get('metadata')

    def test_signed_checkout_completed_activates_premium(self):
        self.assertFalse(self.founder_app.is_premium)

        response = self._checkout_completed()

        self.assertEqual(response.status_code, 200)
        self.founder_app.refresh_from_db()
        self.assertTrue(self.founder_app.is_premium)
        sub = Subscription.objects.get(stripe_subscription_id='sub_signed_1')
        self.assertEqual(sub.user, self.founder_user)
        self.assertEqual(sub.plan, Subscription.Plan.FOUNDER_PREMIUM)
        self.assertEqual(sub.stripe_customer_id, 'cus_signed_1')
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)
        self.assertTrue(Notification.objects.filter(
            recipient=self.founder_user, notification_type='PAYMENT',
            message='Your premium subscription is now active.',
        ).exists())

    def test_signed_subscription_updated_to_past_due_removes_premium(self):
        self._active_subscription('sub_signed_2')

        # Shaped like the account's API version, which carries no top-level
        # current_period_end on the subscription object.
        response = self._post_signed('customer.subscription.updated', {
            'id': 'sub_signed_2', 'object': 'subscription', 'status': 'past_due',
        })

        self.assertEqual(response.status_code, 200)
        self.founder_app.refresh_from_db()
        self.assertFalse(self.founder_app.is_premium)
        self.assertEqual(
            Subscription.objects.get(stripe_subscription_id='sub_signed_2').status,
            Subscription.Status.PAST_DUE,
        )

    def test_signed_subscription_deleted_removes_premium(self):
        self._active_subscription('sub_signed_3')

        response = self._post_signed('customer.subscription.deleted', {
            'id': 'sub_signed_3', 'object': 'subscription', 'status': 'canceled',
        })

        self.assertEqual(response.status_code, 200)
        self.founder_app.refresh_from_db()
        self.assertFalse(self.founder_app.is_premium)
        self.assertEqual(
            Subscription.objects.get(stripe_subscription_id='sub_signed_3').status,
            Subscription.Status.CANCELED,
        )
        self.assertTrue(Notification.objects.filter(
            recipient=self.founder_user, message='Your premium subscription has ended.',
        ).exists())

    def test_signed_invoice_payment_failed_marks_past_due(self):
        self._active_subscription('sub_signed_4', customer_id='cus_signed_4')

        response = self._post_signed('invoice.payment_failed', {
            'id': 'in_signed_4', 'object': 'invoice', 'customer': 'cus_signed_4',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Subscription.objects.get(stripe_subscription_id='sub_signed_4').status,
            Subscription.Status.PAST_DUE,
        )
        self.assertTrue(Notification.objects.filter(
            recipient=self.founder_user, notification_type='PAYMENT',
            message__startswith='Your last payment failed',
        ).exists())

    def test_payload_signed_with_another_secret_is_rejected(self):
        response = self._post_signed('checkout.session.completed', {
            'object': 'checkout.session',
            'metadata': {'user_id': str(self.founder_user.id), 'plan': Subscription.Plan.FOUNDER_PREMIUM},
            'subscription': 'sub_forged', 'customer': 'cus_forged',
        }, secret='whsec_not_the_configured_secret')

        self.assertEqual(response.status_code, 400)
        self.founder_app.refresh_from_db()
        self.assertFalse(self.founder_app.is_premium)
        self.assertFalse(Subscription.objects.filter(stripe_subscription_id='sub_forged').exists())
