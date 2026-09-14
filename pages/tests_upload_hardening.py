"""
Upload hardening (2026-09-14).

Several upload paths accepted any file of any size:

  - profile pictures were saved with no check at all, so an SVG or a renamed
    script became a "picture" served from media storage
  - job-application resumes had no extension or size limit
  - blog images had no size limit
  - the pitch-analysis API read an upload of any size

and documents/analyze/, a legacy endpoint no page calls, could overwrite the
caller's founder profile.

Limits: profile picture 5 MB, JPG/PNG/WebP, and a real image; blog image 5 MB;
resume 10 MB, PDF/DOC/DOCX; pitch analysis 25 MB, the deck limit used elsewhere.
A request whose Content-Length is already over the limit is refused before
anything parses its body (shared_utils/upload_limits.py).
Normal uploads keep working -- each group has a control that must pass before
and after.
"""
import io
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from PIL import Image

from blog.models import Article
from jobs.models import JobApplication, JobListing
from usersettings.models import UserSettings

User = get_user_model()

MB = 1024 * 1024


def _png(padding=0, name='picture.png'):
    """A real PNG; `padding` bytes after its end make it large while it stays a valid image."""
    buffer = io.BytesIO()
    Image.new('RGB', (8, 8), (40, 90, 160)).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue() + b'\0' * padding, content_type='image/png')


def _messages(response):
    return ' '.join(str(m) for m in response.context['messages']).lower()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ProfilePictureUploadTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('upload_member', password='x')
        self.client.force_login(self.user)
        self.url = reverse('usersettings:update_profile_picture')

    def _stored(self):
        return UserSettings.objects.get_or_create(user=self.user)[0].profile_picture

    def _upload(self, picture):
        return self.client.post(self.url, {'profile_picture': picture}, follow=True)

    def test_a_small_png_is_saved(self):
        self._upload(_png())
        self.assertTrue(self._stored())

    def test_a_picture_of_exactly_5_mb_is_saved(self):
        self._upload(_png(padding=5 * MB - len(_png().read())))
        self.assertEqual(self._stored().size, 5 * MB)

    def test_an_svg_is_refused(self):
        svg = SimpleUploadedFile(
            'me.svg', b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            content_type='image/svg+xml')
        response = self._upload(svg)
        self.assertFalse(self._stored())
        self.assertNotIn('updated', _messages(response))

    def test_a_file_that_is_not_really_an_image_is_refused(self):
        response = self._upload(SimpleUploadedFile('me.png', b'#!/bin/sh\necho hello', content_type='image/png'))
        self.assertFalse(self._stored())
        self.assertNotIn('updated', _messages(response))

    def test_a_gif_renamed_to_png_is_refused(self):
        buffer = io.BytesIO()
        Image.new('RGB', (8, 8)).save(buffer, format='GIF')
        response = self._upload(SimpleUploadedFile('me.png', buffer.getvalue(), content_type='image/png'))
        self.assertFalse(self._stored())
        self.assertNotIn('updated', _messages(response))

    def test_a_picture_over_5_mb_is_refused(self):
        response = self._upload(_png(padding=5 * MB))
        self.assertFalse(self._stored())
        self.assertNotIn('updated', _messages(response))

    def test_a_refused_upload_keeps_the_current_picture(self):
        self._upload(_png(name='first.png'))
        before = self._stored().name
        self._upload(_png(padding=5 * MB, name='second.png'))
        self.assertEqual(self._stored().name, before)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ResumeUploadTests(TestCase):

    def setUp(self):
        poster = User.objects.create_user('upload_poster', password='x')
        self.job = JobListing.objects.create(poster=poster, company_name='Co', title='Engineer', description='desc')
        self.applicant = User.objects.create_user('upload_applicant', password='x')
        self.client.force_login(self.applicant)
        self.url = reverse('jobs:apply', args=[self.job.pk])

    def _apply(self, resume=None):
        data = {'cover_letter': 'Hello.'}
        if resume is not None:
            data['resume_attachment'] = resume
        return self.client.post(self.url, data, follow=True)

    def _application(self):
        return JobApplication.objects.filter(job=self.job, applicant=self.applicant).first()

    def test_a_pdf_resume_is_accepted(self):
        self._apply(SimpleUploadedFile('cv.pdf', b'%PDF-1.4 resume', content_type='application/pdf'))
        self.assertTrue(self._application().resume_attachment)

    def test_a_docx_resume_is_accepted(self):
        docx = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        self._apply(SimpleUploadedFile('cv.docx', b'PK\x03\x04 resume', content_type=docx))
        self.assertTrue(self._application().resume_attachment)

    def test_a_resume_of_exactly_10_mb_beside_a_long_cover_letter_is_accepted(self):
        resume = SimpleUploadedFile('cv.pdf', b'%PDF-' + b'x' * (10 * MB - 5), content_type='application/pdf')
        self.client.post(self.url, {'cover_letter': 'Hello. ' * 20000, 'resume_attachment': resume}, follow=True)
        self.assertEqual(self._application().resume_attachment.size, 10 * MB)

    def test_applying_without_a_resume_still_works(self):
        self._apply()
        self.assertIsNotNone(self._application())

    def test_an_executable_is_refused(self):
        response = self._apply(SimpleUploadedFile('cv.exe', b'MZ', content_type='application/octet-stream'))
        self.assertIsNone(self._application())
        self.assertIn('resume', _messages(response))

    def test_a_file_named_pdf_that_is_not_a_pdf_is_refused(self):
        response = self._apply(SimpleUploadedFile('cv.pdf', b'MZ\x90\x00 an executable', content_type='application/pdf'))
        self.assertIsNone(self._application())
        self.assertIn('resume', _messages(response))

    def test_a_resume_over_10_mb_is_refused(self):
        response = self._apply(SimpleUploadedFile('cv.pdf', b'x' * (10 * MB + 1), content_type='application/pdf'))
        self.assertIsNone(self._application())
        self.assertIn('resume', _messages(response))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class BlogImageUploadTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('upload_author', password='x')
        self.client.force_login(self.user)

    def _post(self, image):
        return self.client.post(reverse('blog:blog_view'), {
            'company_name': 'Co', 'title': 'A post', 'body': 'Body.', 'image': image,
        })

    def test_a_small_image_is_published(self):
        self._post(_png())
        self.assertTrue(Article.objects.filter(author=self.user).exists())

    def test_an_image_over_5_mb_is_refused(self):
        self._post(_png(padding=5 * MB))
        self.assertFalse(Article.objects.filter(author=self.user).exists())


class PitchAnalysisUploadTests(TestCase):

    def setUp(self):
        self.client.force_login(User.objects.create_user('upload_analyst', password='x'))
        self.url = reverse('zelda_api:pitch_analysis')

    def test_a_file_over_25_mb_is_refused_before_it_is_read(self):
        big = SimpleUploadedFile('deck.pdf', b'x' * (25 * MB + 1), content_type='application/pdf')
        # A plain MagicMock result would reach DRF's JSON renderer if the guard
        # is missing, and serializing it grows without bound (1.6 GB+, crashed
        # the machine). A real error dict makes a missing guard a clean 422.
        with mock.patch('zelda_api.views.scan_pitch_deck', return_value={'error': 'unreadable'}) as scan:
            response = self.client.post(self.url, {'pitch_deck': big})
        self.assertEqual(response.status_code, 400)
        scan.assert_not_called()

    def test_a_deck_of_exactly_25_mb_reaches_the_scanner(self):
        deck = SimpleUploadedFile('deck.pdf', b'%PDF-' + b'x' * (25 * MB - 5), content_type='application/pdf')
        with mock.patch('zelda_api.views.scan_pitch_deck', return_value={'error': 'unreadable'}) as scan:
            response = self.client.post(self.url, {'pitch_deck': deck})
        scan.assert_called_once()
        self.assertEqual(response.status_code, 422)

    def test_a_normal_deck_still_reaches_the_scanner(self):
        deck = SimpleUploadedFile('deck.pdf', b'%PDF-1.4 deck', content_type='application/pdf')
        with mock.patch('zelda_api.views.scan_pitch_deck', return_value={'error': 'unreadable'}) as scan:
            response = self.client.post(self.url, {'pitch_deck': deck})
        scan.assert_called_once()
        self.assertEqual(response.status_code, 422)


class LegacyDocumentIntakeEndpointTests(TestCase):

    def test_documents_analyze_is_gone(self):
        with self.assertRaises(NoReverseMatch):
            reverse('zelda_api:document_intake')
        self.client.force_login(User.objects.create_user('upload_legacy', password='x'))
        self.assertEqual(self.client.post('/api/v1/zelda/documents/analyze/', {}).status_code, 404)


class UploadGateHeaderTests(SimpleTestCase):
    """
    The gate acts only on a Content-Length it can read. Absent, blank or not a
    number, the request goes through and the view's exact per-file check decides.
    (Django itself reads no body at all without a Content-Length.)
    """

    def setUp(self):
        from shared_utils.upload_limits import UploadSizeLimitMiddleware
        self.gate = UploadSizeLimitMiddleware(lambda request: HttpResponse('view'))
        self.url = reverse('zelda_api:pitch_analysis')

    def _request(self, content_length, method='post', path=None):
        request = getattr(RequestFactory(), method)(path or self.url)
        request.META.pop('CONTENT_LENGTH', None)
        if content_length is not None:
            request.META['CONTENT_LENGTH'] = content_length
        return request

    def test_a_request_without_a_readable_content_length_reaches_the_view(self):
        for value in (None, '', 'chunked', '-5'):
            with self.subTest(content_length=value):
                self.assertEqual(self.gate(self._request(value)).content, b'view')

    def test_the_ceiling_is_the_file_limit_plus_the_multipart_allowance(self):
        from shared_utils.upload_limits import MULTIPART_ALLOWANCE_BYTES, PITCH_ANALYSIS_MAX_MB
        ceiling = PITCH_ANALYSIS_MAX_MB * MB + MULTIPART_ALLOWANCE_BYTES
        self.assertEqual(self.gate(self._request(str(ceiling))).content, b'view')
        self.assertEqual(self.gate(self._request(str(ceiling + 1))).status_code, 413)

    def test_other_urls_and_other_methods_are_never_checked(self):
        huge = str(500 * MB)
        self.assertEqual(self.gate(self._request(huge, path=reverse('blog:favorites_list'))).content, b'view')
        self.assertEqual(self.gate(self._request(huge, method='get')).content, b'view')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class OversizedUploadsAreRefusedBeforeParsingTests(TestCase):
    """
    The Content-Length header alone decides. Django's CSRF check and DRF's session
    authentication both parse the body before a view runs, so this client enforces
    CSRF, and each request fails the test if anything parses the multipart body.
    """

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(User.objects.create_user('upload_gate', password='x'))

    def _post_claiming(self, url, field, claimed_bytes, **extra):
        tiny = SimpleUploadedFile('file.bin', b'tiny', content_type='application/octet-stream')
        with mock.patch('django.http.multipartparser.MultiPartParser.parse') as parse:
            response = self.client.post(url, {field: tiny}, CONTENT_LENGTH=str(claimed_bytes), **extra)
        parse.assert_not_called()
        return response

    def test_an_oversized_pitch_deck_gets_413_without_being_parsed_or_scanned(self):
        with mock.patch('zelda_api.views.scan_pitch_deck', return_value={'error': 'unreadable'}) as scan:
            response = self._post_claiming(reverse('zelda_api:pitch_analysis'), 'pitch_deck', 26 * MB)
        self.assertEqual(response.status_code, 413)
        scan.assert_not_called()

    def test_oversized_form_uploads_go_back_to_the_page_without_being_parsed(self):
        poster = User.objects.create_user('upload_gate_poster', password='x')
        job = JobListing.objects.create(poster=poster, company_name='Co', title='Engineer', description='desc')
        page = 'http://testserver/settings/'
        for url, field, limit_mb in (
            (reverse('usersettings:update_profile_picture'), 'profile_picture', 5),
            (reverse('blog:blog_view'), 'image', 5),
            (reverse('jobs:apply', args=[job.pk]), 'resume_attachment', 10),
        ):
            with self.subTest(url=url):
                response = self._post_claiming(url, field, (limit_mb + 1) * MB, HTTP_REFERER=page)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response['Location'], page)
        self.assertFalse(Article.objects.exists())
        self.assertFalse(JobApplication.objects.exists())
