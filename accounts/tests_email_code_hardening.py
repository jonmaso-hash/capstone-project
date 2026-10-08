from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from matchmaking.models import Application, BusinessEmailVerification
from matchmaking.tests import _mock_embedding_generation


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EmailCodeHardeningTests(TestCase):
    def setUp(self):
        _mock_embedding_generation(self)
        self.user = get_user_model().objects.create_user('harden_email')
        Application.objects.create(user=self.user, company_name='Testco',
                                   founder_name='Test', email='test@testco.com',
                                   description='Test', sector='SaaS', stage='Seed')
        self.client.force_login(self.user)

    def issue(self):
        self.client.post(reverse('accounts:business_verification_request'),
                         {'business_email': 'test@testco.com'})
        row = BusinessEmailVerification.objects.filter(user=self.user).latest('pk')
        return row, mail.outbox[-1].body.split('is: ', 1)[1].splitlines()[0]

    def confirm(self, code):
        return self.client.post(reverse('accounts:business_verification_confirm'), {'code': code})

    def test_only_salted_hash_is_stored_and_admin_hides_it(self):
        row, code = self.issue()
        self.assertNotIn(code, row.code_hash)
        self.assertTrue(row.matches_code(code))
        self.assertIsNone(row.take_issued_code())
        staff = get_user_model().objects.create_superuser('email_admin', password='x')
        self.client.force_login(staff)
        page = self.client.get(reverse('admin:matchmaking_businessemailverification_change', args=[row.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, code)
        self.assertNotContains(page, row.code_hash)

    @override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.PBKDF2PasswordHasher'])
    def test_production_hasher_uses_salted_pbkdf2_and_accepts_correct_code(self):
        from django.contrib.auth.hashers import make_password
        row, code = self.issue()
        self.assertTrue(row.code_hash.startswith('pbkdf2_sha256$'))
        self.assertNotEqual(row.code_hash, make_password(code))
        self.assertTrue(row.matches_code(code))
        self.confirm(code)
        row.refresh_from_db()
        self.assertEqual(row.status, 'VERIFIED')

    def test_database_cooldown_survives_cache_clear(self):
        self.issue()
        cache.clear()
        self.client.post(reverse('accounts:business_verification_request'),
                         {'business_email': 'test@testco.com'})
        self.assertEqual(BusinessEmailVerification.objects.filter(user=self.user).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_invalidates_old_code_and_lockout_cannot_fall_back(self):
        old, old_code = self.issue()
        BusinessEmailVerification.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(seconds=61))
        new, new_code = self.issue()
        old.refresh_from_db()
        self.assertEqual(old.status, 'EXPIRED')
        self.assertEqual(old.code_hash, '')
        wrong = '000000' if new_code != '000000' else '111111'
        for _ in range(BusinessEmailVerification.MAX_ATTEMPTS):
            self.confirm(wrong)
        new.refresh_from_db()
        self.assertEqual(new.status, 'LOCKED')
        self.assertEqual(new.code_hash, '')
        self.confirm(old_code)
        self.assertFalse(BusinessEmailVerification.objects.filter(user=self.user, status='VERIFIED').exists())

    def test_new_code_still_verifies_after_resend(self):
        old, _ = self.issue()
        BusinessEmailVerification.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(seconds=61))
        new, code = self.issue()
        self.confirm(code)
        new.refresh_from_db()
        self.assertEqual(new.status, 'VERIFIED')
        self.assertEqual(new.code_hash, '')
        verified_at = new.verified_at
        self.confirm(code)
        new.refresh_from_db()
        self.assertEqual(new.verified_at, verified_at)

    def test_expired_code_is_erased_and_rejected(self):
        row, code = self.issue()
        BusinessEmailVerification.objects.filter(pk=row.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.confirm(code)
        row.refresh_from_db()
        self.assertEqual(row.status, 'EXPIRED')
        self.assertEqual(row.code_hash, '')

    def test_database_rejects_multiple_pending_codes_for_one_user(self):
        self.issue()
        with self.assertRaises(IntegrityError), transaction.atomic():
            BusinessEmailVerification.objects.create(user=self.user, business_email='other@testco.com')

    def test_another_user_cannot_use_the_code(self):
        row, code = self.issue()
        other = get_user_model().objects.create_user('other_email_user')
        self.client.force_login(other)
        self.confirm(code)
        row.refresh_from_db()
        self.assertEqual(row.status, 'PENDING')
        self.assertEqual(row.attempts, 0)
