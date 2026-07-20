import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import JobApplication, JobListing

User = get_user_model()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class JobListingClickCountTests(TestCase):
    """
    click_count feeds the Job Postings section of Profile Analysis — it
    should only count genuine outside interest, not the poster checking
    their own listing, mirroring the self-view skip used for pitch deck
    and pitch video telemetry.
    """

    def setUp(self):
        self.poster = User.objects.create_user('job_poster', password='x')
        self.viewer = User.objects.create_user('job_viewer', password='x')
        self.job = JobListing.objects.create(
            poster=self.poster, company_name='Co', title='Engineer', description='desc',
        )

    def test_click_count_increments_for_non_poster_viewer(self):
        self.client.force_login(self.viewer)
        self.client.get(reverse('jobs:detail', args=[self.job.pk]))
        self.job.refresh_from_db()
        self.assertEqual(self.job.click_count, 1)

    def test_click_count_does_not_increment_for_poster_self_view(self):
        self.client.force_login(self.poster)
        self.client.get(reverse('jobs:detail', args=[self.job.pk]))
        self.job.refresh_from_db()
        self.assertEqual(self.job.click_count, 0)

    def test_click_count_increments_for_anonymous_viewer(self):
        self.client.get(reverse('jobs:detail', args=[self.job.pk]))
        self.job.refresh_from_db()
        self.assertEqual(self.job.click_count, 1)

    def test_click_count_accumulates_across_multiple_viewers(self):
        other_viewer = User.objects.create_user('job_viewer_2', password='x')
        self.client.force_login(self.viewer)
        self.client.get(reverse('jobs:detail', args=[self.job.pk]))
        self.client.force_login(other_viewer)
        self.client.get(reverse('jobs:detail', args=[self.job.pk]))
        self.job.refresh_from_db()
        self.assertEqual(self.job.click_count, 2)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class JobHighlightSortTests(TestCase):
    """
    Founder Premium's monthly highlight (matchmaking.models.Application.
    is_highlighted) sorts a highlighted poster's job above the model's
    default -is_featured/-created_at ordering — see JobListView.get_queryset's
    poster_is_highlighted annotate.
    """

    def _founder_user(self, username, **kwargs):
        from unittest import mock
        from matchmaking.models import Application
        with mock.patch('matchmaking.signals.generate_profile_embedding', return_value=[]):
            u = User.objects.create_user(username, password='x')
            defaults = dict(
                company_name=f'{username}Co', founder_name='F', email=f'{username}@t.com',
                description='test', sector='SaaS', stage='Seed',
            )
            defaults.update(kwargs)
            Application.objects.create(user=u, **defaults)
        return u

    def test_highlighted_posters_job_ranks_above_featured(self):
        from django.utils import timezone
        featured_poster = self._founder_user('jobhlfeatured')
        highlighted_poster = self._founder_user(
            'jobhlhighlighted', is_premium=True, last_highlight_at=timezone.now(),
        )
        JobListing.objects.create(poster=featured_poster, company_name='FeaturedCo', title='Featured Job', description='d', is_featured=True)
        JobListing.objects.create(poster=highlighted_poster, company_name='HighlightedCo', title='Highlighted Job', description='d')

        response = self.client.get(reverse('jobs:index'))
        titles = [j.title for j in response.context['jobs']]
        self.assertEqual(titles[0], 'Highlighted Job')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ResumeAttachmentStorageCleanupTests(TestCase):
    """
    jobs/signals.py::delete_resume_attachment_from_storage — same orphaned-
    file-on-delete gap found and fixed for DataRoomDocument also existed
    for JobApplication.resume_attachment; this is the mirrored fix for the
    jobs app.
    """

    def test_deleting_job_application_removes_resume_from_storage(self):
        poster = User.objects.create_user('resume_cleanup_poster', password='x')
        applicant = User.objects.create_user('resume_cleanup_applicant', password='x')
        job = JobListing.objects.create(
            poster=poster, company_name='Co', title='Engineer', description='desc',
        )
        application = JobApplication.objects.create(
            job=job, applicant=applicant,
            resume_attachment=SimpleUploadedFile('resume.pdf', b'x' * 10, content_type='application/pdf'),
        )
        storage, path = application.resume_attachment.storage, application.resume_attachment.name
        self.assertTrue(storage.exists(path))

        application.delete()

        self.assertFalse(storage.exists(path))
