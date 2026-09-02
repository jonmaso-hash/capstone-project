import shutil
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Application, SellerApplication, ProfileVideo, ProfileVideoReport

User = get_user_model()
_MEDIA = tempfile.mkdtemp()


def _mock_embeddings(tc):
    p = mock.patch('matchmaking.signals.generate_profile_embedding', return_value=[])
    p.start()
    tc.addCleanup(p.stop)


def _video_file(name='pitch.mp4'):
    return SimpleUploadedFile(name, b'\x00\x00\x00\x18ftypmp42fake', content_type='video/mp4')


@override_settings(
    MEDIA_ROOT=_MEDIA,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class ExploreFeedTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA, ignore_errors=True)

    def setUp(self):
        _mock_embeddings(self)
        self.founder_user = User.objects.create_user('founder1', password='x')
        self.founder = Application.objects.create(
            user=self.founder_user, company_name='Acme AI', founder_name='Sarah',
            email='s@acme.test', description='We do things.', sector='SaaS', stage='Seed',
        )
        self.pv = ProfileVideo.objects.create(
            founder=self.founder, kind=ProfileVideo.KIND_ELEVATOR_PITCH,
            video=_video_file(), caption='AI estimating in 10 minutes.',
        )
        self.viewer = User.objects.create_user('viewer1', password='x')

    # ---- feed visibility --------------------------------------------------

    def test_anonymous_sees_published_pitch(self):
        resp = self.client.get(reverse('explore'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Acme AI')
        self.assertContains(resp, 'AI estimating in 10 minutes.')

    def test_private_owner_excluded(self):
        self.founder.is_private = True
        self.founder.save(update_fields=['is_private'])
        self.assertNotIn(self.pv, ProfileVideo.objects.visible_elevator_pitches())

    def test_archived_owner_excluded(self):
        from django.utils import timezone
        self.founder.archived_at = timezone.now()
        self.founder.save(update_fields=['archived_at'])
        self.assertNotIn(self.pv, ProfileVideo.objects.visible_elevator_pitches())

    def test_staff_hidden_owner_excluded(self):
        self.founder.is_hidden_by_staff = True
        self.founder.save(update_fields=['is_hidden_by_staff'])
        self.assertNotIn(self.pv, ProfileVideo.objects.visible_elevator_pitches())

    def test_quarantined_video_excluded(self):
        self.pv.quarantine()
        self.assertNotIn(self.pv, ProfileVideo.objects.visible_elevator_pitches())

    # ---- play counter ---------------------------------------------------

    def test_play_counts_once_per_session(self):
        url = reverse('matchmaking:elevator_pitch_play', args=[self.pv.id])
        self.client.post(url, data='{}', content_type='application/json')
        self.client.post(url, data='{}', content_type='application/json')
        self.pv.refresh_from_db()
        self.assertEqual(self.pv.view_count, 1)

    def test_play_completion_counted(self):
        url = reverse('matchmaking:elevator_pitch_play', args=[self.pv.id])
        self.client.post(url, data='{"completed": true}', content_type='application/json')
        self.pv.refresh_from_db()
        self.assertEqual(self.pv.completed_view_count, 1)

    # ---- reporting / moderation ---------------------------------------

    def test_report_requires_login(self):
        url = reverse('matchmaking:elevator_pitch_report', args=[self.pv.id])
        resp = self.client.post(url, {'reason': 'SCAM'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp['Location'])

    def test_first_report_quarantines_and_logs(self):
        self.client.force_login(self.viewer)
        url = reverse('matchmaking:elevator_pitch_report', args=[self.pv.id])
        resp = self.client.post(url, {'reason': 'MISLEADING', 'detail': 'nope'})
        self.assertEqual(resp.status_code, 200)
        self.pv.refresh_from_db()
        self.assertEqual(self.pv.status, ProfileVideo.STATUS_QUARANTINED)
        self.assertEqual(self.pv.report_count, 1)
        self.assertIsNotNone(self.pv.first_reported_at)
        self.assertEqual(ProfileVideoReport.objects.filter(video=self.pv).count(), 1)

    def test_duplicate_report_is_idempotent(self):
        self.client.force_login(self.viewer)
        url = reverse('matchmaking:elevator_pitch_report', args=[self.pv.id])
        self.client.post(url, {'reason': 'SCAM'})
        self.client.post(url, {'reason': 'SPAM'})
        self.pv.refresh_from_db()
        self.assertEqual(self.pv.report_count, 1)
        self.assertEqual(ProfileVideoReport.objects.filter(video=self.pv).count(), 1)

    def test_cannot_report_own_video(self):
        self.client.force_login(self.founder_user)
        url = reverse('matchmaking:elevator_pitch_report', args=[self.pv.id])
        resp = self.client.post(url, {'reason': 'SCAM'})
        self.assertEqual(resp.status_code, 400)
        self.pv.refresh_from_db()
        self.assertEqual(self.pv.status, ProfileVideo.STATUS_PUBLISHED)

    def test_staff_restore_returns_to_feed(self):
        staff = User.objects.create_user('mod', password='x', is_staff=True)
        self.pv.quarantine()
        self.pv.restore(staff)
        self.pv.refresh_from_db()
        self.assertEqual(self.pv.status, ProfileVideo.STATUS_PUBLISHED)
        self.assertEqual(self.pv.last_review_decision, 'RESTORED')
        self.assertIn(self.pv, ProfileVideo.objects.visible_elevator_pitches())

    def test_staff_remove_is_permanent(self):
        staff = User.objects.create_user('mod', password='x', is_staff=True)
        self.pv.remove_by_staff(staff)
        self.pv.refresh_from_db()
        self.assertEqual(self.pv.status, ProfileVideo.STATUS_REMOVED)
        self.assertNotIn(self.pv, ProfileVideo.objects.visible_elevator_pitches())

    # ---- interested toggle -------------------------------------------

    def test_interested_toggle(self):
        self.client.force_login(self.viewer)
        url = reverse('matchmaking:elevator_pitch_interested', args=[self.pv.id])
        r1 = self.client.post(url).json()
        self.assertTrue(r1['interested'])
        self.assertEqual(r1['interested_count'], 1)
        r2 = self.client.post(url).json()
        self.assertFalse(r2['interested'])
        self.assertEqual(r2['interested_count'], 0)

    # ---- owner upload flow ------------------------------------------

    def test_manage_rejects_overlong_clip(self):
        u = User.objects.create_user('founder2', password='x')
        Application.objects.create(
            user=u, company_name='Long Co', founder_name='L', email='l@x.test',
            description='x', sector='SaaS', stage='Seed',
        )
        self.client.force_login(u)
        resp = self.client.post(reverse('matchmaking:manage_elevator_pitch'), {
            'video': _video_file('long.mp4'),
            'duration_seconds': '95',
            'caption': 'too long',
        }, follow=True)
        self.assertFalse(
            ProfileVideo.objects.filter(founder__user=u).exists()
        )
        self.assertContains(resp, 'seconds or less')

    # ---- profile page funnel ---------------------------------------

    def test_published_pitch_shows_on_profile(self):
        self.client.force_login(self.viewer)
        resp = self.client.get(reverse('accounts:profile', args=[self.founder_user.username]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Elevator Pitch')
        self.assertContains(resp, self.pv.video.url)

    def test_quarantined_pitch_hidden_from_visitors_shown_to_owner(self):
        self.pv.quarantine()
        url = reverse('accounts:profile', args=[self.founder_user.username])

        self.client.force_login(self.viewer)  # logged-in non-owner
        resp = self.client.get(url)
        self.assertNotContains(resp, self.pv.video.url)

        self.client.force_login(self.founder_user)  # owner
        resp = self.client.get(url)
        self.assertContains(resp, self.pv.video.url)
        self.assertContains(resp, 'under review')

    def test_anonymous_view_profile_cta_points_to_signup(self):
        resp = self.client.get(reverse('explore'))
        self.assertContains(resp, '/accounts/signup/?next=')

    def test_only_one_elevator_pitch_per_founder(self):
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProfileVideo.objects.create(
                    founder=self.founder, kind=ProfileVideo.KIND_ELEVATOR_PITCH,
                    video=_video_file('dupe.mp4'),
                )
