import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Subscription, ZeldaOrder
from .zelda_views import handle_product_event
from zelda_api.vector_models import DocumentSource, IntelligenceMemo


class ConfirmedProductEventTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('analytics-customer')
        self.document = DocumentSource.objects.create(uploaded_by=self.user, filename='private.pdf')
        self.order = ZeldaOrder.objects.create(user=self.user, source_document=self.document,
            product='ic_memo', reports=['ic_memo'], amount=499, stripe_session_id='cs_analytics')
        self.session = {'id': 'cs_analytics', 'mode': 'payment', 'currency': 'usd',
            'amount_total': 499, 'payment_status': 'paid', 'metadata': {
                'purpose': 'zelda_product', 'order_id': str(self.order.pk), 'user_id': str(self.user.pk)}}

    def test_unpaid_and_duplicate_callbacks_do_not_count_as_new_purchases(self):
        with mock.patch('matchmaking.product_analytics.track') as track, \
                mock.patch('billing.tasks.fulfill_zelda_order.delay'):
            handle_product_event('checkout.session.completed', {**self.session, 'payment_status': 'unpaid'})
            track.assert_not_called()
            handle_product_event('checkout.session.completed', self.session)
            handle_product_event('checkout.session.completed', self.session)
        track.assert_called_once()
        self.assertEqual(track.call_args.args[0], 'purchase_completed')
        self.assertEqual(track.call_args.kwargs['amount_minor'], 499)

    def test_order_ready_is_counted_once_after_reports_exist(self):
        from .fulfillment import reconcile_order
        self.document.status = 'analyzed'
        self.document.save(update_fields=['status'])
        IntelligenceMemo.objects.create(document=self.document)
        self.order.analysis_document = self.document
        self.order.status = 'processing'
        self.order.paid_at = timezone.now()
        self.order.save()
        with mock.patch('matchmaking.product_analytics.track') as track, \
                mock.patch('billing.fulfillment.notify'), mock.patch('billing.fulfillment.archive_ready_order'):
            reconcile_order(self.order)
            reconcile_order(self.order)
        track.assert_called_once()
        self.assertEqual(track.call_args.args[0], 'zelda_reports_ready')

    @override_settings(STRIPE_WEBHOOK_SECRET='test-secret')
    def test_paid_invoice_replays_have_same_occurrence_time_and_key(self):
        Subscription.objects.create(user=self.user, plan='FOUNDER_PREMIUM',
            stripe_subscription_id='sub_analytics', stripe_customer_id='cus_analytics', status='active')
        event = {'type': 'invoice.paid', 'data': {'object': {
            'id': 'in_analytics', 'created': 1700000000, 'amount_paid': 9900,
            'currency': 'usd', 'subscription': 'sub_analytics'}}}
        with mock.patch('stripe.Webhook.construct_event', return_value=event), \
                mock.patch('matchmaking.product_analytics.track') as track:
            for _ in range(2):
                response = self.client.post(reverse('billing:stripe_webhook'), json.dumps(event),
                    content_type='application/json', HTTP_STRIPE_SIGNATURE='test')
                self.assertEqual(response.status_code, 200)
        self.assertEqual(track.call_count, 2)
        self.assertEqual(track.call_args_list[0], track.call_args_list[1])
