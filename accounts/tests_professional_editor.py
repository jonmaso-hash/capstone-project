from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import PersonProfile


class ProfessionalEditorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="editor_user", password="test-pass")
        self.url = reverse("accounts:edit_professional_profile")

    def test_login_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_get_does_not_create_profile(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertFalse(PersonProfile.objects.filter(user=self.user).exists())

    def test_post_creates_and_updates_only_own_profile(self):
        self.client.force_login(self.user)
        payload = {"display_name": "Test Founder", "headline": "Founder", "biography": "Hello",
                   "location": "San Diego", "website": "", "linkedin_url": ""}
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        self.assertEqual(PersonProfile.objects.get(user=self.user).headline, "Founder")
        payload["headline"] = "CEO"
        self.client.post(self.url, payload)
        self.assertEqual(PersonProfile.objects.filter(user=self.user).count(), 1)
        self.assertEqual(PersonProfile.objects.get(user=self.user).headline, "CEO")

    def test_invalid_url_does_not_save(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"display_name": "Test", "website": "not-a-url"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PersonProfile.objects.filter(user=self.user).exists())
