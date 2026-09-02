import tempfile
from unittest import mock
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
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


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], MEDIA_ROOT=tempfile.mkdtemp())
class FounderProfilePersistenceRegressionTests(TestCase):
    """
    Traced regression check for a reported bug: "pitch video/pitch deck/
    company size/prior amount raised didn't save to profile." Rather than
    grep for the fields (a field existing in the model proves nothing
    about whether the actual submission path persists it), this posts a
    real multipart request through the real edit_founder_profile view
    (accounts.forms.ApplicationForm) and reads the result back from both
    the database and the rendered profile page — form -> view -> model ->
    save -> render, end to end.

    One finding surfaced while tracing this: Application has TWO similarly
    named fields — company_size (matchmaking/models.py, comment: "Alias to
    fix FieldError") and team_size. ApplicationForm.Meta.fields only lists
    team_size; company_size is never written by any reachable code path
    (only by an unrouted/never-called API view in zelda_api/views.py) and
    never read by profile.html or the live intelligence_pipeline.py (which
    reads team_size). So "company size" — meaning whatever field the
    profile UI and current Zelda pipeline actually use — is team_size, and
    it does persist correctly; company_size is inert legacy cruft, not a
    live bug, and out of scope for this regression check.
    """

    def setUp(self):
        patcher = mock.patch('matchmaking.signals.generate_profile_embedding', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = User.objects.create_user('persist_founder', password='x')
        self.client.force_login(self.user)

    def _valid_payload(self, **overrides):
        payload = {
            'company_name': 'PersistCo',
            'founder_name': 'Founder Person',
            'email': 'persist@t.com',
            'description': 'A real description of what this company does, well past any minimum word count.',
            'sector': 'SaaS',
            'stage': 'Seed',
            'raising_amount': '500000',
            'team_size': '12',
            'prior_amount_raised': '250,000',
        }
        payload.update(overrides)
        return payload

    def test_new_submission_persists_team_size_and_prior_amount_raised(self):
        response = self.client.post(reverse('usersettings:edit_founder_profile'), self._valid_payload())
        self.assertRedirects(response, reverse('pages:thank_you'))

        app = Application.objects.get(user=self.user)
        self.assertEqual(app.team_size, 12)
        self.assertEqual(app.prior_amount_raised, 250000)

    def test_new_submission_persists_pitch_deck_and_pitch_video_and_they_render_on_profile(self):
        payload = self._valid_payload(
            pitch_deck=SimpleUploadedFile('deck.pdf', b'%PDF-1.4 fake deck', content_type='application/pdf'),
            pitch_video=SimpleUploadedFile('pitch.mp4', b'fake video bytes', content_type='video/mp4'),
        )
        response = self.client.post(reverse('usersettings:edit_founder_profile'), payload)
        self.assertRedirects(response, reverse('pages:thank_you'))

        app = Application.objects.get(user=self.user)
        self.assertTrue(app.pitch_deck.name.endswith('deck.pdf'))
        self.assertTrue(app.pitch_video.name.endswith('pitch.mp4'))

        profile_response = self.client.get(reverse('accounts:profile', args=[self.user.username]))
        self.assertContains(profile_response, app.pitch_video.url)
        self.assertContains(profile_response, reverse('matchmaking:view_pitch_deck', args=[app.id]))

    def test_editing_an_existing_profile_persists_updated_team_size_and_prior_amount_raised(self):
        """Same fields, but through the edit (not new-submission) branch of
        the same view — the two share one form/one save path, so a fix for
        one covers the other, but this proves it rather than assuming it."""
        self.client.post(reverse('usersettings:edit_founder_profile'), self._valid_payload())
        app = Application.objects.get(user=self.user)
        self.assertEqual(app.team_size, 12)

        response = self.client.post(reverse('usersettings:edit_founder_profile'), self._valid_payload(
            team_size='40', prior_amount_raised='1,200,000',
        ))
        self.assertRedirects(response, reverse('accounts:profile', args=[self.user.username]))

        app.refresh_from_db()
        self.assertEqual(app.team_size, 40)
        self.assertEqual(app.prior_amount_raised, 1200000)

        profile_response = self.client.get(reverse('accounts:profile', args=[self.user.username]))
        self.assertContains(profile_response, '40')
        self.assertContains(profile_response, '1,200,000')

    def test_team_size_renders_on_profile_page(self):
        self.client.post(reverse('usersettings:edit_founder_profile'), self._valid_payload(team_size='7'))
        profile_response = self.client.get(reverse('accounts:profile', args=[self.user.username]))
        self.assertContains(profile_response, '>7<')

    def test_company_size_field_is_inert_legacy_cruft_not_a_live_persistence_path(self):
        """Documents the actual finding: submitting the form never touches
        company_size at all (it isn't one of ApplicationForm's fields), and
        nothing reachable reads it — so a founder could never have observed
        it "saving," and its being empty isn't the reported bug."""
        self.client.post(reverse('usersettings:edit_founder_profile'), self._valid_payload(team_size='12'))
        app = Application.objects.get(user=self.user)
        self.assertIsNone(app.company_size)
        self.assertEqual(app.team_size, 12)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ArchiveDeleteProfileTests(TestCase):
    """
    Archive/Delete — Settings UI + views. Archive hides from discovery
    (see ApplicationQuerySet.discoverable) while keeping the row and every
    related document/report; Delete actually removes it.
    """

    def setUp(self):
        patcher = mock.patch('matchmaking.signals.generate_profile_embedding', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = User.objects.create_user('archive_founder', password='x')
        self.application = Application.objects.create(
            user=self.user, company_name='ArchiveCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.client.force_login(self.user)

    def test_settings_page_shows_archive_and_delete_actions(self):
        response = self.client.get(reverse('usersettings:home'))
        self.assertContains(response, 'Archive or Delete Your Founder Profile')
        self.assertContains(response, 'Archive')
        self.assertContains(response, 'Delete Permanently')

    def test_archive_hides_from_discovery_and_keeps_the_row(self):
        self.client.post(reverse('usersettings:archive_profile'))
        self.application.refresh_from_db()
        self.assertTrue(self.application.is_archived)
        self.assertNotIn(self.application, Application.objects.discoverable())
        # The row (and everything hanging off it) still exists.
        self.assertTrue(Application.objects.filter(pk=self.application.pk).exists())

    def test_settings_page_shows_reactivate_once_archived(self):
        self.application.archive()
        response = self.client.get(reverse('usersettings:home'))
        self.assertContains(response, 'currently')
        self.assertContains(response, 'Reactivate')
        self.assertNotContains(response, 'Delete Permanently')

    def test_unarchive_restores_discoverability(self):
        self.application.archive()
        self.client.post(reverse('usersettings:unarchive_profile'))
        self.application.refresh_from_db()
        self.assertFalse(self.application.is_archived)
        self.assertIn(self.application, Application.objects.discoverable())

    def test_delete_confirm_get_shows_confirmation_page_without_deleting(self):
        response = self.client.get(reverse('usersettings:delete_profile_confirm'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ArchiveCo')
        self.assertTrue(Application.objects.filter(pk=self.application.pk).exists())

    def test_delete_confirm_post_actually_deletes_and_redirects_to_choose_role(self):
        response = self.client.post(reverse('usersettings:delete_profile_confirm'))
        self.assertRedirects(response, reverse('accounts:choose_role'))
        self.assertFalse(Application.objects.filter(pk=self.application.pk).exists())
        # The user account itself survives.
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
