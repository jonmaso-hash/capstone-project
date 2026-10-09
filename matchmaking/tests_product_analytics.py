from unittest import mock

import requests
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from .product_analytics import deliver_mixpanel_event, track


@override_settings(MIXPANEL_TOKEN='test-token', MIXPANEL_ID_NAMESPACE='test',
                   MIXPANEL_TRACK_URL='https://api.mixpanel.com/track')
class ProductAnalyticsTests(TestCase):
    def test_no_delivery_for_rollback_and_no_delivery_before_commit(self):
        with mock.patch.object(deliver_mixpanel_event, 'apply_async') as queue:
            with self.captureOnCommitCallbacks(execute=True):
                try:
                    with transaction.atomic():
                        track('signup_completed', 7, 'user:7', method='password')
                        queue.assert_not_called()
                        raise RuntimeError('signup rolled back')
                except RuntimeError:
                    pass
            queue.assert_not_called()
            with self.captureOnCommitCallbacks(execute=True):
                track('signup_completed', 7, 'user:7', method='password')
                queue.assert_not_called()
            queue.assert_called_once()

    @override_settings(MIXPANEL_TOKEN='')
    def test_unconfigured_integration_does_not_queue(self):
        with mock.patch.object(deliver_mixpanel_event, 'apply_async') as queue:
            with self.captureOnCommitCallbacks(execute=True):
                track('signup_completed', 7, 'user:7')
            queue.assert_not_called()

    def test_sensitive_properties_are_rejected(self):
        with self.assertRaises(ValueError):
            track('signup_completed', 7, 'user:7', email='private@example.invalid')

    def test_queue_outage_does_not_break_completed_action(self):
        with mock.patch.object(deliver_mixpanel_event, 'apply_async', side_effect=RuntimeError('offline')):
            with self.captureOnCommitCallbacks(execute=True):
                track('signup_completed', 7, 'user:7')

    def test_duplicate_business_occurrences_use_identical_dedup_fields(self):
        occurred_at = timezone.now()
        with mock.patch.object(deliver_mixpanel_event, 'apply_async') as queue:
            with self.captureOnCommitCallbacks(execute=True):
                for _ in range(2):
                    track('purchase_completed', 7, 'invoice:one', occurred_at=occurred_at,
                          product='FOUNDER_PREMIUM', amount_minor=9900, currency='usd',
                          payment_kind='subscription')
            first, second = [call.kwargs['args'][0] for call in queue.call_args_list]
            self.assertEqual(first, second)
            self.assertEqual(first['properties']['distinct_id'], 'test:user:7')
            self.assertNotIn('token', first['properties'])

    def test_delivery_uses_original_event_and_disables_ip_enrichment(self):
        payload = {'event': 'signup_completed', 'properties': {
            'environment': 'test', 'distinct_id': 'test:user:7', 'time': 1700000000,
            '$insert_id': 'stable-id', 'method': 'password'}}
        with mock.patch('matchmaking.product_analytics.requests.post') as post:
            post.return_value.json.return_value = {'status': 1}
            deliver_mixpanel_event.run(payload)
        self.assertEqual(post.call_args.kwargs['params'], {'verbose': 1, 'ip': 0})
        sent = post.call_args.kwargs['json'][0]
        self.assertEqual(sent['properties']['time'], 1700000000)
        self.assertEqual(sent['properties']['token'], 'test-token')
        self.assertNotIn('token', payload['properties'])

    def test_network_failure_retries_without_leaking_exception_details(self):
        payload = {'event': 'signup_completed', 'properties': {'environment': 'test'}}
        with mock.patch('matchmaking.product_analytics.requests.post', side_effect=requests.Timeout('private')), \
                mock.patch.object(deliver_mixpanel_event, 'retry', side_effect=RuntimeError('retry')) as retry:
            with self.assertRaisesRegex(RuntimeError, '^retry$'):
                deliver_mixpanel_event.run(payload)
        retry.assert_called_once_with()

    def test_social_signup_uses_same_user_identity(self):
        from allauth.account.signals import user_signed_up
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user('analytics-signup')
        with mock.patch('matchmaking.product_analytics.track') as event:
            user_signed_up.send(sender=type(user), request=None, user=user)
        event.assert_called_once_with('signup_completed', user.pk, f'user:{user.pk}',
                                     occurred_at=user.date_joined, method='allauth')
