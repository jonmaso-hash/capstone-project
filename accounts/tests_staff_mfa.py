import hashlib
from unittest.mock import patch

import pyotp
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import StaffMFA
from .staff_mfa import SESSION_KEY, MAX_AGE, encrypt_secret, decrypt_secret


class PasswordOnlyClient(Client):
    auto_staff_mfa = False


class StaffMFATests(TestCase):
    client_class = PasswordOnlyClient

    def setUp(self):
        self.staff = get_user_model().objects.create_user('mfa_staff', password='StaffMFA!2026xyz', is_staff=True, is_superuser=True)
        self.member = get_user_model().objects.create_user('mfa_member')
        self.client.force_login(self.staff)
        self.setup_url = reverse('accounts:staff_mfa_setup')
        self.verify_url = reverse('accounts:staff_mfa_verify')
        self.admin = '/' + settings.ADMIN_URL_PATH
        self.clock = patch('accounts.staff_mfa.time.time', return_value=1800000000)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def enroll(self):
        self.client.get(self.setup_url)
        credential = StaffMFA.objects.get(user=self.staff)
        secret = decrypt_secret(credential.encrypted_secret)
        response = self.client.post(self.setup_url, {'code': pyotp.TOTP(secret).at(1800000000), 'password': 'StaffMFA!2026xyz'})
        self.assertEqual(response.status_code, 200)
        credential.refresh_from_db()
        return credential, secret, response.context['recovery_codes']

    def fresh_session(self):
        client = PasswordOnlyClient()
        client.force_login(self.staff)
        return client

    def test_password_login_alone_cannot_reach_admin_or_ops(self):
        self.client.logout()
        response = self.client.post(reverse('accounts:login'), {'username': self.staff.username, 'password': 'StaffMFA!2026xyz', 'next': self.admin})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(self.client.get(self.admin), self.setup_url + '?next=' + self.admin.replace('/', '%2F'), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('ops:dashboard')).status_code, 302)

    def test_old_authenticated_sessions_cannot_make_staff_writes(self):
        response = self.client.post(reverse('ops:start_impersonation', args=[self.member.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('impersonator_id', self.client.session)

    def test_enrollment_requires_password_reconfirmation_when_available(self):
        self.client.get(self.setup_url)
        credential = StaffMFA.objects.get(user=self.staff)
        code = pyotp.TOTP(decrypt_secret(credential.encrypted_secret)).at(1800000000)
        self.client.post(self.setup_url, {'code': code})
        credential.refresh_from_db()
        self.assertIsNone(credential.enabled_at)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_enrollment_encrypts_secret_and_shows_hashed_recovery_codes_once(self):
        credential, secret, codes = self.enroll()
        self.assertNotIn(secret, credential.encrypted_secret)
        self.assertEqual(len(codes), 10)
        self.assertEqual(credential.recovery_hashes, [hashlib.sha256(code.encode()).hexdigest() for code in codes])
        self.assertEqual(self.client.get(self.admin).status_code, 200)
        response = self.client.get(self.setup_url)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(codes[0], repr(dict(self.client.session)))

    def test_secret_pages_are_uncached_and_have_no_third_party_scripts(self):
        response = self.client.get(self.setup_url)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn("default-src 'none'", response['Content-Security-Policy'])
        self.assertNotContains(response, '<script')

    def test_fresh_totp_verifies_but_used_counter_cannot_be_replayed(self):
        credential, secret, _ = self.enroll()
        other = self.fresh_session()
        used = other.post(self.verify_url, {'code': pyotp.TOTP(secret).at(1800000000)})
        self.assertNotIn(SESSION_KEY, other.session)
        self.assertContains(used, 'already-used')
        with patch('accounts.staff_mfa.time.time', return_value=1800000030):
            response = other.post(self.verify_url, {'code': pyotp.TOTP(secret).at(1800000030)})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(other.get(self.admin).status_code, 200)
        third = self.fresh_session()
        with patch('accounts.staff_mfa.time.time', return_value=1800000030):
            third.post(self.verify_url, {'code': pyotp.TOTP(secret).at(1800000030)})
            self.assertNotIn(SESSION_KEY, third.session)

    def test_recovery_code_is_consumed_atomically_and_cannot_be_reused(self):
        credential, _, codes = self.enroll()
        other = self.fresh_session()
        self.assertEqual(other.post(self.verify_url, {'code': codes[0]}).status_code, 302)
        credential.refresh_from_db()
        self.assertEqual(len(credential.recovery_hashes), 9)
        third = self.fresh_session()
        third.post(self.verify_url, {'code': codes[0]})
        self.assertNotIn(SESSION_KEY, third.session)

    def test_failed_enrollment_attempts_are_rate_limited(self):
        self.client.get(self.setup_url)
        for _ in range(5):
            self.client.post(self.setup_url, {'code': 'invalid'})
        response = self.client.post(self.setup_url, {'code': 'invalid'})
        self.assertContains(response, 'Too many attempts')
        self.assertIsNone(StaffMFA.objects.get(user=self.staff).enabled_at)

    def test_failed_challenges_are_rate_limited_even_with_a_correct_recovery_code(self):
        _, _, codes = self.enroll()
        other = self.fresh_session()
        for _ in range(5):
            other.post(self.verify_url, {'code': 'invalid'})
        response = other.post(self.verify_url, {'code': codes[0]})
        self.assertContains(response, 'Too many attempts')
        self.assertNotIn(SESSION_KEY, other.session)

    def test_proof_expires_and_is_bound_to_the_credential(self):
        credential, _, _ = self.enroll()
        with patch('accounts.staff_mfa.time.time', return_value=1800000000 + MAX_AGE + 1):
            self.assertEqual(self.client.get(self.admin).status_code, 302)
        credential.encrypted_secret = encrypt_secret(pyotp.random_base32())
        credential.save(update_fields=['encrypted_secret'])
        self.assertEqual(self.client.get(self.admin).status_code, 302)

    def test_members_are_unaffected_and_cannot_enroll_staff_mfa(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse('pages:home')).status_code, 200)
        self.assertEqual(self.client.get(self.setup_url).status_code, 403)

    def test_redirects_cannot_escape_site(self):
        self.enroll()
        response = self.client.get(self.setup_url, {'next': 'https://attacker.example/'})
        self.assertEqual(response.url, self.admin)

    def test_csrf_is_required(self):
        client = PasswordOnlyClient(enforce_csrf_checks=True)
        client.force_login(self.staff)
        self.assertEqual(client.post(self.setup_url, {'code': '123456'}).status_code, 403)

    def test_staff_bearer_tokens_cannot_bypass_mfa(self):
        from rest_framework.authtoken.models import Token
        from matchmaking.models import APIKey
        token = Token.objects.create(user=self.staff)
        client = PasswordOnlyClient()
        response = client.get('/api/v1/zelda/documents/', HTTP_AUTHORIZATION='Token ' + token.key)
        self.assertEqual(response.status_code, 403)
        key = APIKey.objects.create(owner=self.staff, firm_name='Staff key')
        response = client.get('/api/v1/enterprise/stats/', HTTP_AUTHORIZATION='Api-Key ' + key.take_issued_key())
        self.assertEqual(response.status_code, 403)

    def test_nonstaff_enterprise_keys_continue_to_work(self):
        from matchmaking.models import APIKey
        key = APIKey.objects.create(owner=self.member, firm_name='Member key')
        response = PasswordOnlyClient().get('/api/v1/enterprise/stats/', HTTP_AUTHORIZATION='Api-Key ' + key.take_issued_key())
        self.assertEqual(response.status_code, 200)

    def test_alternate_authentication_backend_cannot_skip_mfa(self):
        self.client.force_login(self.staff, backend='allauth.account.auth_backends.AuthenticationBackend')
        self.assertEqual(self.client.get(self.admin).status_code, 302)

    def test_logout_discards_mfa_proof(self):
        self.enroll()
        self.client.post(reverse('accounts:logout'))
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.admin).status_code, 302)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_secret_key_rotation_can_use_explicit_fallback(self):
        encrypted = encrypt_secret('test-secret')
        with override_settings(SECRET_KEY='new-key', SECRET_KEY_FALLBACKS=[settings.SECRET_KEY]):
            self.assertEqual(decrypt_secret(encrypted), 'test-secret')

    def test_operator_reset_requires_confirmation_and_blocks_old_proof(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from io import StringIO
        self.enroll()
        with self.assertRaises(CommandError):
            call_command('reset_staff_mfa', self.staff.username, confirm_username='wrong', stdout=StringIO())
        self.assertTrue(StaffMFA.objects.filter(user=self.staff).exists())
        call_command('reset_staff_mfa', self.staff.username, confirm_username=self.staff.username, stdout=StringIO())
        self.assertFalse(StaffMFA.objects.filter(user=self.staff).exists())
        self.assertEqual(self.client.get(self.admin).status_code, 302)
