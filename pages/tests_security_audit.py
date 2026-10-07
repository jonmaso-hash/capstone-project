from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate

from matchmaking.models import APIKey, Application
from zelda_api.views import InvestmentMemoGeneratorAPIView


User = get_user_model()


class SecurityAuditRegressionTests(TestCase):
    def setUp(self):
        self.embedding_patch = mock.patch(
            'matchmaking.signals.generate_profile_embedding',
            return_value=[],
        )
        self.embedding_patch.start()
        self.addCleanup(self.embedding_patch.stop)

    def _founder(self, username, *, sector='SaaS', is_private=False):
        user = User.objects.create_user(username, password='secure-test-pass')
        app = Application.objects.create(
            user=user,
            founder_name='Founder',
            email=f'{username}@example.com',
            company_name=f'{username} Co',
            description='Private founder description',
            sector=sector,
            stage='Seed',
            is_private=is_private,
        )
        return user, app

    def test_staff_metrics_json_script_escapes_script_breakout_from_sector(self):
        payload = 'SaaS</script><script>window.__interlink_xss = true</script>'
        self._founder('xss_founder', sector=payload)
        staff = User.objects.create_user(
            'security_staff',
            password='secure-test-pass',
            is_staff=True,
        )
        self.client.force_login(staff)

        response = self.client.get(reverse('matchmaking:platform_metrics'))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertNotIn(payload, body)
        self.assertIn(r'\u003C/script\u003E\u003Cscript\u003E', body)
        self.assertIn('id="sector-labels-data"', body)

    def test_enterprise_api_key_is_hashed_at_rest_and_authenticates(self):
        owner = User.objects.create_user('enterprise_key_owner', password='secure-test-pass')
        api_key, raw_key = APIKey.issue(owner=owner, firm_name='Secure Firm')

        api_key.refresh_from_db()
        self.assertNotEqual(api_key.key_hash, raw_key)
        self.assertEqual(api_key.key_hash, APIKey.digest(raw_key))
        self.assertEqual(api_key.key_prefix, raw_key[:12])
        self.assertFalse(hasattr(api_key, 'key'))

        response = self.client.get(
            '/api/v1/enterprise/stats/',
            HTTP_AUTHORIZATION=f'Api-Key {raw_key}',
        )
        self.assertEqual(response.status_code, 200)

        bad = self.client.get(
            '/api/v1/enterprise/stats/',
            HTTP_AUTHORIZATION='Api-Key definitely-not-the-key',
        )
        self.assertEqual(bad.status_code, 403)

    def test_dormant_memo_generator_hides_private_founder_from_stranger(self):
        owner, founder = self._founder('hidden_memo_owner', is_private=True)
        stranger = User.objects.create_user('hidden_memo_stranger', password='secure-test-pass')

        factory = APIRequestFactory()
        request = factory.post(
            '/unused-security-test/',
            {'founder_id': founder.id, 'tone': 'professional'},
            format='json',
        )
        force_authenticate(request, user=stranger)

        response = InvestmentMemoGeneratorAPIView.as_view()(request)

        self.assertEqual(response.status_code, 404)

    def test_dormant_memo_generator_still_allows_owner(self):
        owner, founder = self._founder('memo_owner', is_private=True)

        factory = APIRequestFactory()
        request = factory.post(
            '/unused-security-test/',
            {'founder_id': founder.id, 'tone': 'professional'},
            format='json',
        )
        force_authenticate(request, user=owner)

        response = InvestmentMemoGeneratorAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['target_founder_id'], founder.id)
