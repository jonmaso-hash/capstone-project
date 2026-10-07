from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

from .models import Notification

User = get_user_model()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class NotificationHistoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('notification_owner', password='x')
        self.other = User.objects.create_user('notification_other', password='x')
        self.client.force_login(self.user)

    def _notice(self, **kwargs):
        return Notification.objects.create(recipient=self.user, message='An update.', **kwargs)

    def _read(self, ids):
        return self.client.post(reverse('api-read'), {'ids': ids}, content_type='application/json')

    def test_history_includes_read_items_and_get_does_not_acknowledge(self):
        read = self._notice(is_read=True)
        unread = self._notice(target_url='/some/path/')
        data = self.client.get(reverse('api-list')).json()
        self.assertEqual([item['id'] for item in data], [unread.id, read.id])
        self.assertEqual(data[0]['message'], 'An update.')
        self.assertEqual(data[0]['target_url'], '/some/path/')
        self.assertFalse(data[0]['is_read'])
        self.assertTrue(data[0]['can_dismiss'])
        self.assertIn('created_at', data[0])
        unread.refresh_from_db()
        self.assertFalse(unread.is_read)
        self.assertEqual(self.client.get(reverse('api-unread-count')).json()['count'], 1)

    def test_acknowledging_does_not_remove_history(self):
        notice = self._notice()
        self.assertEqual(self._read([notice.id]).json(), {'updated': 1, 'count': 0})
        self.assertEqual(self._read([notice.id]).json(), {'updated': 0, 'count': 0})
        self.assertEqual(self.client.get(reverse('api-list')).json()[0]['id'], notice.id)
        self.assertTrue(self.client.get(reverse('api-list')).json()[0]['is_read'])

    def test_acknowledgement_keeps_new_arrivals_unread(self):
        displayed = self._notice()
        self.client.get(reverse('api-list'))
        arrived_later = self._notice()
        self.assertEqual(self._read([displayed.id]).json(), {'updated': 1, 'count': 1})
        arrived_later.refresh_from_db()
        self.assertFalse(arrived_later.is_read)

    def test_pagination_is_stable_when_a_new_notification_arrives(self):
        notices = [self._notice() for _ in range(51)]
        first = self.client.get(reverse('api-list')).json()
        self.assertEqual(len(first), 50)
        self._notice()
        second = self.client.get(reverse('api-list'), {'before': first[-1]['id']}).json()
        self.assertEqual([item['id'] for item in second], [notices[0].id])

    def test_invalid_history_cursor_is_rejected(self):
        for cursor in ('bad', '0', '-1'):
            with self.subTest(cursor=cursor):
                self.assertEqual(self.client.get(reverse('api-list'), {'before': cursor}).status_code, 400)

    def test_other_users_records_cannot_be_read_or_dismissed(self):
        other_notice = Notification.objects.create(recipient=self.other, message='Private update.')
        self.assertEqual(self.client.get(reverse('api-list')).json(), [])
        self.assertEqual(self._read([other_notice.id]).json(), {'updated': 0, 'count': 0})
        self.assertEqual(self.client.post(reverse('api-delete', args=[other_notice.id])).json(), {'dismissed': False})
        other_notice.refresh_from_db()
        self.assertFalse(other_notice.is_read)
        self.assertIsNone(other_notice.dismissed_at)

    def test_dismissal_keeps_record_but_removes_it_from_history_and_badge(self):
        notice = self._notice()
        self.assertEqual(self.client.post(reverse('api-delete', args=[notice.id])).json(), {'dismissed': True})
        notice.refresh_from_db()
        self.assertIsNotNone(notice.dismissed_at)
        self.assertTrue(notice.is_read)
        self.assertEqual(self.client.get(reverse('api-list')).json(), [])
        self.assertEqual(self.client.get(reverse('api-unread-count')).json(), {'count': 0})
        self.assertEqual(self.client.post(reverse('api-delete', args=[notice.id])).json(), {'dismissed': False})

    def test_dismissed_terminal_notification_still_prevents_duplicate_creation(self):
        notice = self._notice(notification_type='ZELDA_ANALYSIS_READY', target_url='/report/1/')
        self.client.post(reverse('api-delete', args=[notice.id]))
        repeated, created = Notification.objects.get_or_create(
            recipient=self.user, notification_type='ZELDA_ANALYSIS_READY', target_url='/report/1/',
            defaults={'message': 'Ready again.'},
        )
        self.assertFalse(created)
        self.assertEqual(repeated.id, notice.id)

    def test_protected_notices_cannot_be_dismissed(self):
        for kind in ('SYSTEM', 'PAYMENT', 'PROFILE_VISIBILITY_DEFAULTS', 'SECURITY_ALERT', 'AUDIT_EVENT',
                     'FUNDED_CONFIRMATION', 'CLOSED_CONFIRMATION', 'TRUTH_DELTA_DISPUTE', 'ELEVATOR_PITCH_REPORT'):
            with self.subTest(kind=kind):
                notice = self._notice(notification_type=kind)
                data = self.client.get(reverse('api-list')).json()
                self.assertFalse(next(item for item in data if item['id'] == notice.id)['can_dismiss'])
                self.assertEqual(self.client.post(reverse('api-delete', args=[notice.id])).status_code, 403)
                notice.refresh_from_db()
                self.assertIsNone(notice.dismissed_at)
                self.assertEqual(self._read([notice.id]).status_code, 200)

    def test_invalid_read_payload_cannot_mark_anything_read(self):
        notice = self._notice()
        for body in ('bad', '[]', '{}', '{"ids":"all"}', '{"ids":[true]}', '{"ids":[0]}',
                     '{"ids":["1"]}', '{"ids":[' + ','.join(['1'] * 51) + ']}'):
            with self.subTest(body=body):
                self.assertEqual(self.client.post(reverse('api-read'), body, content_type='application/json').status_code, 400)
        notice.refresh_from_db()
        self.assertFalse(notice.is_read)

    def test_write_endpoints_require_post_and_authentication(self):
        notice = self._notice()
        for url in (reverse('api-read'), reverse('api-delete', args=[notice.id])):
            self.assertEqual(self.client.get(url).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('api-list')).json(), [])
        self.assertEqual(self.client.get(reverse('api-unread-count')).json(), {'count': 0})
        self.assertEqual(self._read([notice.id]).status_code, 403)
        self.assertEqual(self.client.post(reverse('api-delete', args=[notice.id])).status_code, 403)

    def test_impersonation_cannot_acknowledge_or_dismiss(self):
        notice = self._notice()
        with patch('ops.impersonation.is_impersonating', return_value=True):
            self.assertEqual(self._read([notice.id]).status_code, 403)
            self.assertEqual(self.client.post(reverse('api-delete', args=[notice.id])).status_code, 403)
        notice.refresh_from_db()
        self.assertFalse(notice.is_read)
        self.assertIsNone(notice.dismissed_at)

    def test_write_endpoints_require_csrf_token(self):
        notice = self._notice()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('api-read'), {'ids': [notice.id]}, content_type='application/json').status_code, 403)
        self.assertEqual(client.post(reverse('api-delete', args=[notice.id])).status_code, 403)
        notice.refresh_from_db()
        self.assertFalse(notice.is_read)
        self.assertIsNone(notice.dismissed_at)
