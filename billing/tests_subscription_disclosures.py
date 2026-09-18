"""
A recurring charge is disclosed before payment, consented to on the record, and
cancellable here.

Federal law is ROSCA since the FTC's click-to-cancel rule was vacated in July
2025; the binding detail lives in state law, and California's amended ARL
(AB 2863, in force July 2025) is the strictest. This is built to the strictest
common denominator rather than branching per state, for a reason the timing
forces: the disclosure has to appear **before** payment details are collected,
and the authoritative billing address is only collected during checkout, at
Stripe. Profile location cannot stand in for it -- it is the company's location,
free text, and mostly blank.

So: every customer sees the strongest disclosure, and the jurisdiction is
recorded afterwards from Stripe's billing address, on the consent row, so each
subscription shows which state it was actually sold into.

What was missing before this module: the plan page never said a subscription
renews, nothing recorded what the customer agreed to, cancellation left the site
for Stripe's portal, and `billing/` sent no email at all.
"""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from matchmaking.models import Application
from matchmaking.tests import _mock_embedding_generation

from .models import Subscription, SubscriptionConsent
from .tests import FAKE_STRIPE_SETTINGS
from .tests_webhook_signed import SIGNING_SECRET, _payload, _signature_header

User = get_user_model()
PASSWORD = 'Disclose!2026xyz'


class PlanPageStatesTheRenewalTermsTests(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('sd_founder', password=PASSWORD)
        Application.objects.create(
            user=self.user, company_name='SDCo', founder_name='F', email='sd@t.test',
            description='d', sector='SaaS', stage='Seed',
        )
        self.client.force_login(self.user)

    def test_the_page_says_the_subscription_renews_until_cancelled(self):
        html = self.client.get(reverse('billing:billing_page')).content.decode()
        self.assertIn('Renews automatically', html)
        self.assertRegex(html, r'until you cancel')

    def test_the_page_says_how_to_cancel_before_you_pay(self):
        html = self.client.get(reverse('billing:billing_page')).content.decode()
        self.assertRegex(html, r'[Cc]ancel any time')


class ConsentIsRequiredAndRecordedTests(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('sd_investor', password=PASSWORD)
        Application.objects.create(
            user=self.user, company_name='SDCo2', founder_name='F', email='sd2@t.test',
            description='d', sector='SaaS', stage='Seed',
        )
        self.client.force_login(self.user)

    @mock.patch('billing.views.stripe.checkout.Session.create')
    def test_checkout_is_refused_without_consent(self, create):
        response = self.client.post(reverse('billing:create_checkout_session'), {})
        self.assertEqual(response.status_code, 302)
        create.assert_not_called()
        self.assertFalse(SubscriptionConsent.objects.exists())

    @mock.patch('billing.views.stripe.checkout.Session.create')
    def test_consent_is_stored_with_the_exact_text_shown(self, create):
        create.return_value = mock.Mock(url='https://stripe.test/session', id='cs_test_123')
        response = self.client.post(reverse('billing:create_checkout_session'), {'agree_to_renewal': 'on'})
        self.assertEqual(response.status_code, 302)
        consent = SubscriptionConsent.objects.get(user=self.user)
        self.assertIn('Renews automatically', consent.terms_text)
        self.assertIn('$', consent.terms_text)
        self.assertTrue(consent.plan)
        self.assertTrue(consent.agreed_at)
        # The checkout session is recorded too, so a consent row can be tied
        # back to the payment it authorised.
        self.assertEqual(consent.stripe_checkout_session_id, 'cs_test_123')

    @mock.patch('billing.views.stripe.checkout.Session.create')
    def test_the_billing_address_is_collected_so_the_jurisdiction_is_known(self, create):
        create.return_value = mock.Mock(url='https://stripe.test/session', id='cs_test_123')
        self.client.post(reverse('billing:create_checkout_session'), {'agree_to_renewal': 'on'})
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs.get('billing_address_collection'), 'required')


class CancellingEndsAtThePeriodEndTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('sd_cancel', email='cancel@example.test', password=PASSWORD)
        self.subscription = Subscription.objects.create(
            user=self.user, plan=Subscription.Plan.FOUNDER_PREMIUM,
            stripe_customer_id='cus_test', stripe_subscription_id='sub_test',
            status=Subscription.Status.ACTIVE,
            current_period_end=timezone.now() + datetime.timedelta(days=12),
        )
        self.client.force_login(self.user)

    @mock.patch('billing.views.stripe.Subscription.modify')
    def test_cancelling_asks_stripe_to_end_at_the_period_end(self, modify):
        response = self.client.post(reverse('billing:cancel_subscription'))
        self.assertEqual(response.status_code, 302)
        modify.assert_called_once()
        self.assertTrue(modify.call_args.kwargs.get('cancel_at_period_end'))

    @mock.patch('billing.views.stripe.Subscription.modify')
    def test_access_is_not_taken_away_immediately(self, modify):
        self.client.post(reverse('billing:cancel_subscription'))
        self.subscription.refresh_from_db()
        # Still active: they paid for this period and keep it.
        self.assertEqual(self.subscription.status, Subscription.Status.ACTIVE)
        self.assertTrue(self.subscription.cancel_at_period_end)

    @mock.patch('billing.views.stripe.Subscription.modify')
    def test_the_page_says_what_ends_and_when(self, modify):
        self.client.post(reverse('billing:cancel_subscription'))
        html = self.client.get(reverse('billing:billing_page')).content.decode()
        self.assertRegex(html, r'end|ends')
        self.assertIn(str(self.subscription.current_period_end.year), html)

    @mock.patch('billing.views.stripe.Subscription.modify')
    def test_cancelling_sends_a_written_confirmation(self, modify):
        mail.outbox.clear()
        self.client.post(reverse('billing:cancel_subscription'))
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertEqual(mail.outbox[0].to, ['cancel@example.test'])
        self.assertRegex(body, r'cancel')
        # It has to say when access actually stops.
        self.assertIn(str(self.subscription.current_period_end.year), body)

    @mock.patch('billing.views.stripe.Subscription.modify', side_effect=Exception('stripe down'))
    def test_a_stripe_failure_does_not_pretend_it_cancelled(self, modify):
        mail.outbox.clear()
        self.client.post(reverse('billing:cancel_subscription'))
        self.subscription.refresh_from_db()
        self.assertFalse(self.subscription.cancel_at_period_end)
        self.assertEqual(len(mail.outbox), 0)


class StartingASubscriptionIsAcknowledgedTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('sd_ack', email='ack@example.test', password=PASSWORD)

    def test_the_acknowledgement_names_the_amount_interval_and_how_to_cancel(self):
        from .emails import send_subscription_started_email
        subscription = Subscription.objects.create(
            user=self.user, plan=Subscription.Plan.INVESTOR_PREMIUM,
            stripe_customer_id='cus_a', stripe_subscription_id='sub_a',
            status=Subscription.Status.ACTIVE,
            current_period_end=timezone.now() + datetime.timedelta(days=30),
        )
        mail.outbox.clear()
        send_subscription_started_email(subscription)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn('250', body)          # the recurring amount
        self.assertRegex(body, r'month')    # the interval
        self.assertRegex(body, r'[Cc]ancel')  # how to get out


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    **{**FAKE_STRIPE_SETTINGS, 'STRIPE_WEBHOOK_SECRET': SIGNING_SECRET},
)
class TheWebhookRecordsJurisdictionAndAcknowledgesTests(TestCase):
    """
    The webhook is what actually fires in production, so the acknowledgement and
    the jurisdiction capture are tested on that path rather than on a helper.
    """

    def setUp(self):
        self.user = User.objects.create_user('sd_hook', email='hook@example.test', password=PASSWORD)
        self.consent = SubscriptionConsent.objects.create(
            user=self.user, plan='FOUNDER_PREMIUM', price_usd=99, interval='month',
            terms_text='Renews automatically at $99 per month until you cancel.',
        )

    def _completed_event(self):
        data_object = {
            'id': 'cs_hook',
            'customer': 'cus_hook',
            'subscription': 'sub_hook',
            'client_reference_id': str(self.user.id),
            'metadata': {
                'user_id': str(self.user.id),
                'plan': 'FOUNDER_PREMIUM',
                'consent_id': str(self.consent.id),
            },
            'customer_details': {'address': {'country': 'US', 'state': 'CA'}},
        }
        payload = _payload('checkout.session.completed', data_object)
        return self.client.post(
            reverse('billing:stripe_webhook'), data=payload, content_type='application/json',
            HTTP_STRIPE_SIGNATURE=_signature_header(payload),
        )

    def test_the_jurisdiction_is_recorded_from_the_billing_address(self):
        self.assertEqual(self._completed_event().status_code, 200)
        self.consent.refresh_from_db()
        self.assertEqual(self.consent.billing_country, 'US')
        self.assertEqual(self.consent.billing_state, 'CA')

    def test_the_customer_is_told_what_they_bought_and_how_to_stop_it(self):
        mail.outbox.clear()
        self._completed_event()
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn('99', body)
        self.assertRegex(body, r'renews automatically')
        self.assertRegex(body, r'[Cc]ancel')

    def test_a_replayed_event_does_not_email_twice(self):
        self._completed_event()
        mail.outbox.clear()
        self._completed_event()
        self.assertEqual(len(mail.outbox), 0)
