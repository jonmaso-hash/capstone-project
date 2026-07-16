from unittest import mock
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from matchmaking.models import Application

User = get_user_model()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FounderLockBannerTests(TestCase):
    """
    edit_founder_profile.html's lock-related banner only appears once the
    profile's VECTOR_FIELDS are all filled in — see
    Application.vector_fields_complete. An incomplete profile shows neither
    the "will lock" nor "is locked" banner, regardless of how old
    vector_fields_updated_at is.
    """

    def setUp(self):
        patcher = mock.patch('matchmaking.signals.generate_profile_embedding', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = User.objects.create_user('lock_banner_founder', password='x')
        self.client.force_login(self.user)

    def test_no_banner_for_incomplete_profile(self):
        Application.objects.create(
            user=self.user, company_name='FCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
            # extra_info/reason_for_capital/geography left blank — incomplete.
            vector_fields_updated_at=timezone.now() - timedelta(days=100),
        )
        response = self.client.get(reverse('usersettings:edit_founder_profile'))
        self.assertNotContains(response, 'Match-vector fields are locked')
        self.assertNotContains(response, 'these fields lock for 30 days')

    def test_will_lock_banner_shows_for_complete_unlocked_profile(self):
        Application.objects.create(
            user=self.user, company_name='FCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed', extra_info='extra',
            reason_for_capital='reason', geography='Remote',
            vector_fields_updated_at=timezone.now(),
        )
        response = self.client.get(reverse('usersettings:edit_founder_profile'))
        self.assertContains(response, 'these fields lock for 30 days')
        self.assertNotContains(response, 'Match-vector fields are locked')

    def test_locked_banner_shows_for_complete_locked_profile(self):
        Application.objects.create(
            user=self.user, company_name='FCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed', extra_info='extra',
            reason_for_capital='reason', geography='Remote',
            vector_fields_updated_at=timezone.now() - timedelta(hours=25),
        )
        response = self.client.get(reverse('usersettings:edit_founder_profile'))
        self.assertContains(response, 'Match-vector fields are locked')
