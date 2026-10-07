from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import APIKey


class EnterpriseAPIAuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('enterprise_auth_owner')
        cls.key = APIKey.objects.create(owner=cls.owner, firm_name='Test Firm')

    def request(self, value=None):
        headers = {} if value is None else {'HTTP_AUTHORIZATION': 'Api-Key ' + value}
        return self.client.get(reverse('enterprise_platform_stats'), **headers)

    def test_active_owner_and_key_can_access(self):
        response = self.request(self.key.key)
        self.assertEqual(response.status_code, 200)
        self.assertIn('founder_count', response.json())

    def test_missing_and_invalid_keys_are_refused(self):
        self.assertEqual(self.request().status_code, 403)
        self.assertEqual(self.request('invalid-key').status_code, 403)

    def test_revoked_key_is_refused(self):
        self.key.is_active = False
        self.key.save(update_fields=['is_active'])
        self.assertEqual(self.request(self.key.key).status_code, 403)

    def test_suspension_blocks_existing_key_without_marking_it_used(self):
        self.assertEqual(self.request(self.key.key).status_code, 200)
        self.key.refresh_from_db()
        last_used = self.key.last_used_at
        self.owner.is_active = False
        self.owner.save(update_fields=['is_active'])
        self.assertEqual(self.request(self.key.key).status_code, 403)
        self.key.refresh_from_db()
        self.assertTrue(self.key.is_active)
        self.assertEqual(self.key.last_used_at, last_used)

    def test_reactivating_owner_restores_nonrevoked_key(self):
        self.owner.is_active = False
        self.owner.save(update_fields=['is_active'])
        self.assertEqual(self.request(self.key.key).status_code, 403)
        self.owner.is_active = True
        self.owner.save(update_fields=['is_active'])
        self.assertEqual(self.request(self.key.key).status_code, 200)
