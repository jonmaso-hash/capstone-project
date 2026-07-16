from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Notification

User = get_user_model()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class NotificationListApiTests(TestCase):
    """
    notification_list_api is what the Zelda icon's Notifications tab calls —
    it both returns the unread notifications' content (message/target_url,
    so the user can see what they were notified about) and marks them read
    as a side effect of being fetched, which is what makes the badge
    actually clear instead of persisting forever.
    """

    def setUp(self):
        self.user = User.objects.create_user('notif_api_user', password='x')
        self.client.force_login(self.user)

    def test_returns_message_and_target_url_for_unread_notifications(self):
        Notification.objects.create(
            recipient=self.user, message='Someone requested an intro with you.', target_url='/some/path/',
        )
        response = self.client.get(reverse('api-list'))
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['message'], 'Someone requested an intro with you.')
        self.assertEqual(data[0]['target_url'], '/some/path/')

    def test_fetching_the_list_marks_notifications_read(self):
        notif = Notification.objects.create(recipient=self.user, message='Test notification.')
        self.assertFalse(notif.is_read)

        self.client.get(reverse('api-list'))

        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_already_read_notifications_are_excluded(self):
        Notification.objects.create(recipient=self.user, message='Old, already read.', is_read=True)
        response = self.client.get(reverse('api-list'))
        self.assertEqual(response.json(), [])

    def test_second_fetch_returns_empty_since_first_fetch_already_marked_read(self):
        Notification.objects.create(recipient=self.user, message='Only shows up once.')

        first = self.client.get(reverse('api-list'))
        second = self.client.get(reverse('api-list'))

        self.assertEqual(len(first.json()), 1)
        self.assertEqual(second.json(), [])

    def test_anonymous_user_gets_empty_list(self):
        self.client.logout()
        response = self.client.get(reverse('api-list'))
        self.assertEqual(response.json(), [])

    def test_unread_count_api_reflects_actual_count(self):
        Notification.objects.create(recipient=self.user, message='One.')
        Notification.objects.create(recipient=self.user, message='Two.')
        Notification.objects.create(recipient=self.user, message='Already read.', is_read=True)

        response = self.client.get(reverse('api-unread-count'))

        self.assertEqual(response.json()['count'], 2)

    def test_unread_count_drops_after_list_api_marks_read(self):
        Notification.objects.create(recipient=self.user, message='One.')

        self.client.get(reverse('api-list'))
        response = self.client.get(reverse('api-unread-count'))

        self.assertEqual(response.json()['count'], 0)

    def test_list_response_includes_id_for_delete_targeting(self):
        notif = Notification.objects.create(recipient=self.user, message='Has an id.')

        response = self.client.get(reverse('api-list'))

        self.assertEqual(response.json()[0]['id'], notif.id)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class NotificationDeleteApiTests(TestCase):
    """
    The Zelda widget's Notifications tab shows a small "X" so a user can
    dismiss a notification they've already read and don't want to keep
    seeing in the list — this is what that button calls.
    """

    def setUp(self):
        self.user = User.objects.create_user('notif_delete_user', password='x')
        self.other_user = User.objects.create_user('notif_delete_other', password='x')
        self.client.force_login(self.user)

    def test_delete_removes_the_notification(self):
        notif = Notification.objects.create(recipient=self.user, message='Delete me.')

        response = self.client.post(reverse('api-delete', args=[notif.id]))

        self.assertEqual(response.json(), {'deleted': True})
        self.assertFalse(Notification.objects.filter(id=notif.id).exists())

    def test_cannot_delete_another_users_notification(self):
        notif = Notification.objects.create(recipient=self.other_user, message='Not yours.')

        response = self.client.post(reverse('api-delete', args=[notif.id]))

        self.assertEqual(response.json(), {'deleted': False})
        self.assertTrue(Notification.objects.filter(id=notif.id).exists())

    def test_delete_nonexistent_id_reports_not_deleted(self):
        response = self.client.post(reverse('api-delete', args=[999999]))

        self.assertEqual(response.json(), {'deleted': False})

    def test_get_request_not_allowed(self):
        notif = Notification.objects.create(recipient=self.user, message='Still here.')

        response = self.client.get(reverse('api-delete', args=[notif.id]))

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Notification.objects.filter(id=notif.id).exists())

    def test_anonymous_user_forbidden(self):
        self.client.logout()
        notif = Notification.objects.create(recipient=self.user, message='Protected.')

        response = self.client.post(reverse('api-delete', args=[notif.id]))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Notification.objects.filter(id=notif.id).exists())
