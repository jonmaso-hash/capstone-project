from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class UnfinishedProfileTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('unfinished_profile')
        self.client.force_login(self.user)

    def test_selected_role_can_resume_after_leaving_form(self):
        for role in ('founder', 'investor', 'seller', 'buyer'):
            with self.subTest(role=role):
                self.client.post(reverse('accounts:choose_role'), {'role': role})
                page = self.client.get(reverse('accounts:profile_self'), follow=True)
                self.assertContains(page, 'Create a Profile')
                self.assertContains(page, reverse('jobs:create'))
                self.assertContains(page, '>Chat</a>')
                self.assertContains(page, '>Dashboard</a>')
                self.assertRedirects(
                    self.client.get(reverse('accounts:create_profile')),
                    reverse(f'usersettings:edit_{role}_profile'),
                    fetch_redirect_response=False,
                )

    def test_no_role_uses_existing_role_picker(self):
        self.assertRedirects(self.client.get(reverse('accounts:create_profile')),
                             reverse('accounts:choose_role'))
        self.assertRedirects(self.client.get(reverse('accounts:dashboard')),
                             reverse('accounts:profile_self'), fetch_redirect_response=False)

    def test_other_users_canvas_does_not_offer_profile_creation(self):
        other = get_user_model().objects.create_user('another_unfinished_profile')
        page = self.client.get(reverse('accounts:profile', args=[other.username]))
        self.assertNotContains(page, 'Create a Profile')

    def test_profile_creation_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('accounts:create_profile')).status_code, 302)
