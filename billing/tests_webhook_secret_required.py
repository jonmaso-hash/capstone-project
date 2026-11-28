"""
The Stripe webhook refuses every event while its signing secret is empty.

stripe-python 15.3 accepts a signature computed with an empty key, so with
STRIPE_WEBHOOK_SECRET unset anyone could post a "signed" checkout.session.
completed and be granted a subscription. Production has the secret set
(checked read-only, value not printed); this keeps a missing environment
variable from ever turning into free premium.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from matchmaking.models import Application
from matchmaking.tests import _mock_embedding_generation
from notifications.models import Notification
from .models import Subscription
from .tests import FAKE_STRIPE_SETTINGS
from .tests_webhook_signed import SIGNING_SECRET, _payload, _signature_header

User = get_user_model()


class WebhookSecretRequiredTests(TestCase):
    def setUp(self):
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('forge_target', password='x')
        Application.objects.create(user=self.user, founder_name='F', email='f@t.com', company_name='FCo',
                                   sector='SaaS', stage='Seed', description='test')

    def post_checkout(self, secret):
        payload = _payload('checkout.session.completed', {
            'id': 'cs_forged', 'object': 'checkout.session', 'mode': 'subscription',
            'customer': 'cus_forged', 'subscription': 'sub_forged',
            'metadata': {'user_id': str(self.user.id), 'plan': Subscription.Plan.FOUNDER_PREMIUM},
        })
        return self.client.post(reverse('billing:stripe_webhook'), data=payload, content_type='application/json',
                                HTTP_STRIPE_SIGNATURE=_signature_header(payload, secret))

    @override_settings(**{**FAKE_STRIPE_SETTINGS, 'STRIPE_WEBHOOK_SECRET': ''})
    def test_an_event_signed_with_an_empty_key_grants_nothing(self):
        response = self.post_checkout(secret='')
        self.assertEqual(response.status_code, 503)
        self.assertFalse(Subscription.objects.exists())
        self.assertFalse(Notification.objects.filter(recipient=self.user).exists())

    @override_settings(**{**FAKE_STRIPE_SETTINGS, 'STRIPE_WEBHOOK_SECRET': SIGNING_SECRET})
    def test_positive_control_a_correctly_signed_event_still_activates(self):
        response = self.post_checkout(secret=SIGNING_SECRET)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Subscription.objects.filter(user=self.user, stripe_subscription_id='sub_forged').exists())
