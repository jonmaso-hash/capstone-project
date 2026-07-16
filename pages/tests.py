from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from matchmaking.models import Application

User = get_user_model()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ThankYouPageTests(TestCase):
    """
    thank_you.html now extends base.html (brings in the persistent Zelda
    widget) and only celebrates when the founder's profile is 100% complete
    per Application.completion_percentage.
    """

    def setUp(self):
        patcher = mock.patch('matchmaking.signals.generate_profile_embedding', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_extends_base_and_includes_zelda_widget(self):
        user = User.objects.create_user('thank_you_base_user', password='x')
        self.client.force_login(user)

        response = self.client.get(reverse('pages:thank_you'))

        self.assertContains(response, 'ai-agent-toggle')

    def test_what_happens_next_section_removed(self):
        user = User.objects.create_user('thank_you_copy_user', password='x')
        self.client.force_login(user)

        response = self.client.get(reverse('pages:thank_you'))

        self.assertNotContains(response, 'What happens next')
        self.assertContains(response, 'Thank you for applying')
        self.assertContains(response, 'can now be seen on your user profile')

    def test_celebration_fires_for_fully_complete_profile(self):
        user = User.objects.create_user('thank_you_complete_user', password='x')
        Application.objects.create(
            user=user, company_name='FullCo', company_website='https://full.co', founder_name='F',
            email='full@t.com', phone_number='555-1234', description='desc', sector='SaaS', stage='Seed',
            raising_amount=500000, current_revenue=1000, pitch_deck='decks/x.pdf',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('pages:thank_you'))

        self.assertContains(response, 'zelda-complete-toast')

    def test_no_celebration_for_partial_profile(self):
        user = User.objects.create_user('thank_you_partial_user', password='x')
        Application.objects.create(
            user=user, company_name='PartialCo', founder_name='F2', email='partial@t.com',
            description='desc', sector='SaaS', stage='Seed', raising_amount=500000,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('pages:thank_you'))

        self.assertNotContains(response, 'zelda-complete-toast')

    def test_no_celebration_when_no_application_exists(self):
        user = User.objects.create_user('thank_you_no_app_user', password='x')
        self.client.force_login(user)

        response = self.client.get(reverse('pages:thank_you'))

        self.assertNotContains(response, 'zelda-complete-toast')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ZeldaStageChangeToastTests(TestCase):
    """
    The globally-included Zelda widget shows a fading toast explaining why
    the icon's color changed, sourced from journey-status's headline text
    and only fired when the color actually differs from the last one the
    user saw (tracked in localStorage), not on every page load.
    """

    def setUp(self):
        self.user = User.objects.create_user('stage_toast_user', password='x')
        self.client.force_login(self.user)

    def test_toast_element_and_wiring_present_for_authenticated_user(self):
        response = self.client.get(reverse('pages:thank_you'))

        self.assertContains(response, 'zelda-stage-toast')
        self.assertContains(response, 'showStageChangeToast')
        self.assertContains(response, 'zeldaLastSeenStageColor')

    def test_toast_only_fires_on_color_change_not_every_load(self):
        response = self.client.get(reverse('pages:thank_you'))

        self.assertContains(response, 'data.stage_color !== lastSeenColor')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ZeldaNotificationDeleteButtonTests(TestCase):
    """
    Each notification card in the Zelda widget's Notifications tab renders a
    small "X" (zelda-notif-delete) so the user can dismiss one they've
    already read. Click handling is delegated on #notifications-list so it
    keeps working after loadNotifications() re-renders the list's innerHTML.
    """

    def setUp(self):
        self.user = User.objects.create_user('notif_delete_button_user', password='x')
        self.client.force_login(self.user)

    def test_delete_button_wiring_present_for_authenticated_user(self):
        response = self.client.get(reverse('pages:thank_you'))

        self.assertContains(response, 'zelda-notif-delete')
        self.assertContains(response, "/notifications/api/${delBtn.dataset.id}/delete/")
        self.assertContains(response, "notifications-list').addEventListener('click'")
