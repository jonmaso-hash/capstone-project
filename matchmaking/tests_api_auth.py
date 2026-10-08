from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import APIKey
from .api_auth import APIKeyRateThrottle
from types import SimpleNamespace
import re


class EnterpriseAPIAuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('enterprise_auth_owner')
        cls.key = APIKey.objects.create(owner=cls.owner, firm_name='Test Firm')
        cls.raw_key = cls.key.take_issued_key()

    def request(self, value=None):
        headers = {} if value is None else {'HTTP_AUTHORIZATION': 'Api-Key ' + value}
        return self.client.get(reverse('enterprise_platform_stats'), **headers)

    def test_active_owner_and_key_can_access(self):
        response = self.request(self.raw_key)
        self.assertEqual(response.status_code, 200)
        self.assertIn('founder_count', response.json())

    def test_missing_and_invalid_keys_are_refused(self):
        self.assertEqual(self.request().status_code, 403)
        self.assertEqual(self.request('invalid-key').status_code, 403)

    def test_revoked_key_is_refused(self):
        self.key.is_active = False
        self.key.save(update_fields=['is_active'])
        self.assertEqual(self.request(self.raw_key).status_code, 403)

    def test_suspension_blocks_existing_key_without_marking_it_used(self):
        self.assertEqual(self.request(self.raw_key).status_code, 200)
        self.key.refresh_from_db()
        last_used = self.key.last_used_at
        self.owner.is_active = False
        self.owner.save(update_fields=['is_active'])
        self.assertEqual(self.request(self.raw_key).status_code, 403)
        self.key.refresh_from_db()
        self.assertTrue(self.key.is_active)
        self.assertEqual(self.key.last_used_at, last_used)

    def test_reactivating_owner_restores_nonrevoked_key(self):
        self.owner.is_active = False
        self.owner.save(update_fields=['is_active'])
        self.assertEqual(self.request(self.raw_key).status_code, 403)
        self.owner.is_active = True
        self.owner.save(update_fields=['is_active'])
        self.assertEqual(self.request(self.raw_key).status_code, 200)

    def test_database_digest_is_not_a_usable_credential(self):
        stored = APIKey.objects.get(pk=self.key.pk)
        self.assertEqual(stored.key_hash, APIKey.digest(self.raw_key))
        self.assertNotEqual(stored.key_hash, self.raw_key)
        self.assertEqual(stored.key_suffix, self.raw_key[-4:])
        self.assertIsNone(stored.take_issued_key())
        self.assertEqual(self.request(stored.key_hash).status_code, 403)

    def test_issuing_key_returns_plaintext_once_and_edits_preserve_it(self):
        key = APIKey.objects.create(owner=self.owner, firm_name='One-time Firm')
        raw = key.take_issued_key()
        self.assertRegex(raw, r'^[0-9a-f]{64}$')
        self.assertIsNone(key.take_issued_key())
        digest = key.key_hash
        key.firm_name = 'Updated Firm'
        key.save()
        self.assertEqual(key.key_hash, digest)
        self.assertIsNone(key.take_issued_key())
        self.assertEqual(self.request(raw).status_code, 200)

    def test_throttle_identifier_contains_only_database_id(self):
        throttle = APIKeyRateThrottle()
        cache_key = throttle.get_cache_key(SimpleNamespace(auth=self.key), None)
        self.assertEqual(cache_key, throttle.cache_format % {
            'scope': 'enterprise_api', 'ident': self.key.pk,
        })
        self.assertNotIn(self.raw_key, cache_key)
        self.assertNotIn(self.key.key_hash, cache_key)


class EnterpriseAPIKeyAdminTests(TestCase):
    def test_creation_displays_key_once_without_persisting_it_in_session(self):
        staff = get_user_model().objects.create_superuser('key_admin', password='x')
        owner = get_user_model().objects.create_user('key_customer')
        self.client.force_login(staff)
        response = self.client.post(reverse('admin:matchmaking_apikey_add'), {
            'owner': owner.pk, 'firm_name': 'Issued Firm', 'is_active': 'on', '_save': 'Save',
        })
        self.assertEqual(response.status_code, 200)
        raw = re.search(r'<code id="issued-api-key">([0-9a-f]{64})</code>',
                        response.content.decode()).group(1)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        self.assertNotIn(raw, repr(dict(self.client.session)))
        key = APIKey.objects.get(firm_name='Issued Firm')
        self.assertEqual(key.key_hash, APIKey.digest(raw))
        details = self.client.get(reverse('admin:matchmaking_apikey_change', args=[key.pk]))
        self.assertEqual(details.status_code, 200)
        self.assertNotContains(details, raw)
        self.assertNotContains(details, key.key_hash)
        self.assertContains(details, key.key_suffix)
