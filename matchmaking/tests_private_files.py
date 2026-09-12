"""
A private document stays private whatever storage is behind it.

The production-readiness audit found two ways around authorization that had
already been checked at the view level:

- The seller profile linked `cim_document.url` directly. Any signed-in viewer
  saw "Download CIM", and with local storage that link was an unauthenticated,
  guessable /media/ path.
- `config/urls.py` served everything under MEDIA_ROOT, so an anonymous
  `GET /media/data_room/captable.csv` returned a cap table even though the data
  room view gates access correctly.

These tests pin the fix from both sides: who may download a CIM through the
gated view, that the product UI never renders a private storage URL, and that
development media serving refuses private prefixes however the path is written.
"""
import io
import os
import re
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from config.private_media import (
    PRIVATE_MEDIA_PREFIXES, is_private_media_path, media_urlpatterns, serve_public_media,
)

from .models import AcquisitionConnection, BuyerApplication, SellerApplication, can_download_cim
from .tests import _mock_embedding_generation

User = get_user_model()

CIM_BYTES = b'%PDF-1.4 confidential information memorandum'


def _body(response):
    """Read a FileResponse fully and release the file (Windows keeps it locked otherwise)."""
    try:
        return b''.join(response.streaming_content) if response.streaming else response.content
    finally:
        response.close()


class _TempMediaMixin:
    """Uploads go to a throwaway MEDIA_ROOT, never the repository's media/."""

    def setUp(self):
        super().setUp()
        self._media_root = tempfile.mkdtemp(prefix='kcv_private_files_')
        self._media_override = override_settings(MEDIA_ROOT=self._media_root)
        self._media_override.enable()

    def tearDown(self):
        self._media_override.disable()
        shutil.rmtree(self._media_root, ignore_errors=True)
        super().tearDown()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CimDownloadAuthorizationTests(_TempMediaMixin, TestCase):

    def setUp(self):
        super().setUp()
        _mock_embedding_generation(self)

        self.seller_user = User.objects.create_user('pf_seller', password='x')
        self.seller = SellerApplication.objects.create(
            user=self.seller_user, company_name='Harbour Facilities', seller_name='S',
            email='s@t.com', description='A facilities business.',
            industry='Facilities Services', asking_price=4200000,
            cim_document=SimpleUploadedFile('harbour_cim.pdf', CIM_BYTES,
                                            content_type='application/pdf'))

        self.accepted_buyer_user = User.objects.create_user('pf_buyer_ok', password='x')
        self.accepted_buyer = BuyerApplication.objects.create(
            user=self.accepted_buyer_user, full_name='B', company_name='Meridian',
            email='b@t.com', acquisition_thesis='Buying facilities businesses.')
        AcquisitionConnection.objects.create(
            seller=self.seller, buyer=self.accepted_buyer, status='ACCEPTED', initiated_by='BUYER')

        self.pending_buyer_user = User.objects.create_user('pf_buyer_pending', password='x')
        self.pending_buyer = BuyerApplication.objects.create(
            user=self.pending_buyer_user, full_name='P', company_name='Pending Capital',
            email='p@t.com', acquisition_thesis='Also buying.')
        AcquisitionConnection.objects.create(
            seller=self.seller, buyer=self.pending_buyer, status='pending', initiated_by='BUYER')

        self.unconnected_buyer_user = User.objects.create_user('pf_buyer_none', password='x')
        BuyerApplication.objects.create(
            user=self.unconnected_buyer_user, full_name='N', company_name='No Link LLC',
            email='n@t.com', acquisition_thesis='Browsing.')

        self.roleless = User.objects.create_user('pf_roleless', password='x')
        self.staff = User.objects.create_user('pf_staff', password='x', is_staff=True)

        self.url = reverse('matchmaking:cim_document_serve', args=[self.seller.id])

    # -- the rule ---------------------------------------------------------------

    def test_rule_allows_owner_staff_and_accepted_buyer_only(self):
        self.assertTrue(can_download_cim(self.seller_user, self.seller))
        self.assertTrue(can_download_cim(self.staff, self.seller))
        self.assertTrue(can_download_cim(self.accepted_buyer_user, self.seller))

        self.assertFalse(can_download_cim(self.pending_buyer_user, self.seller))
        self.assertFalse(can_download_cim(self.unconnected_buyer_user, self.seller))
        self.assertFalse(can_download_cim(self.roleless, self.seller))

    # -- through the real view --------------------------------------------------

    def test_anonymous_is_sent_to_login_and_gets_no_bytes(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_unrelated_signed_in_users_get_404(self):
        for user in (self.roleless, self.unconnected_buyer_user, self.pending_buyer_user):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 404)

    def test_authorized_parties_receive_the_file(self):
        for user in (self.seller_user, self.staff, self.accepted_buyer_user):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(_body(response), CIM_BYTES)

    def test_seller_without_a_cim_is_404_even_for_the_owner(self):
        self.seller.cim_document.delete(save=True)
        self.client.force_login(self.seller_user)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    # -- the product UI ---------------------------------------------------------

    def _profile_html(self, viewer):
        self.client.force_login(viewer)
        response = self.client.get(reverse('accounts:profile', args=[self.seller_user.username]))
        self.assertEqual(response.status_code, 200)
        return response.content.decode(errors='ignore')

    def test_unrelated_viewer_sees_no_download_and_no_storage_path(self):
        html = self._profile_html(self.roleless)
        self.assertIn('Harbour Facilities', html, 'positive control: the profile rendered')
        self.assertNotIn('Download CIM', html)
        self.assertNotIn(self.url, html)
        self.assertNotIn('/media/cim_documents/', html)
        self.assertIn('CIM available to buyers after an accepted introduction', html)

    def test_accepted_buyer_sees_the_gated_link_not_the_storage_path(self):
        html = self._profile_html(self.accepted_buyer_user)
        self.assertIn('Download CIM', html)
        self.assertIn('href="%s"' % self.url, html)
        self.assertNotIn('/media/cim_documents/', html)

    def test_owner_sees_the_gated_link(self):
        html = self._profile_html(self.seller_user)
        self.assertIn('href="%s"' % self.url, html)
        self.assertNotIn('/media/cim_documents/', html)


class ProductTemplatesNeverLinkPrivateStorageUrlsTests(SimpleTestCase):
    """
    The static half of the guarantee: no template renders the storage URL of a
    private upload. Rendered-page tests only cover pages someone thought to test;
    this covers every template.
    """

    PRIVATE_URL = re.compile(
        r'\{\{[^}]*\b(cim_document|resume_attachment|pitch_deck)\.url\b[^}]*\}\}'
        r'|\{\{[^}]*\bdocument\.file\.url\b[^}]*\}\}')

    def test_no_template_renders_a_private_file_url(self):
        offenders = []
        for root, _dirs, files in os.walk('templates'):
            for name in files:
                if not name.endswith('.html'):
                    continue
                path = os.path.join(root, name)
                for number, line in enumerate(io.open(path, encoding='utf-8'), 1):
                    if self.PRIVATE_URL.search(line):
                        offenders.append('%s:%d  %s' % (path, number, line.strip()[:90]))
        self.assertEqual(
            offenders, [],
            'These templates hand a private file\'s storage URL to the browser. '
            'Link the authorization-checked serve view instead:\n' + '\n'.join(offenders))


class DevelopmentMediaServingTests(SimpleTestCase):
    """
    Django's own media serving (DEBUG only) must refuse private prefixes. Tested
    directly against the view, since test runs have DEBUG off and the dev URL
    pattern is not installed.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='kcv_media_serve_')
        for rel in ('data_room/captable.csv', 'cim_documents/cim.pdf', 'decks/deck.pdf',
                    'resumes/cv.pdf', 'profile_pictures/me.png'):
            full = os.path.join(self.root, *rel.split('/'))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'wb') as handle:
                handle.write(b'secret' if not rel.startswith('profile_pictures') else b'png')
        self.factory = RequestFactory()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _serve(self, path):
        request = self.factory.get('/media/' + path)
        return serve_public_media(request, path, document_root=self.root)

    def test_every_private_prefix_is_refused(self):
        for path in ('data_room/captable.csv', 'cim_documents/cim.pdf',
                     'decks/deck.pdf', 'resumes/cv.pdf'):
            with self.subTest(path=path):
                with self.assertRaises(Http404):
                    self._serve(path)

    def test_the_check_cannot_be_dodged_by_how_the_path_is_written(self):
        for path in ('DATA_ROOM/captable.csv', 'Data_Room/captable.csv',
                     './data_room/captable.csv', '/data_room/captable.csv',
                     'data_room\\captable.csv', 'profile_pictures/../data_room/captable.csv'):
            with self.subTest(path=path):
                self.assertTrue(is_private_media_path(path))
                with self.assertRaises(Http404):
                    self._serve(path)

    def test_public_media_is_still_served(self):
        """Positive control: pitch videos and profile pictures are embedded directly."""
        response = self._serve('profile_pictures/me.png')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(_body(response), b'png')

    def test_every_documented_prefix_is_covered(self):
        self.assertEqual(set(PRIVATE_MEDIA_PREFIXES),
                         {'data_room/', 'cim_documents/', 'decks/', 'resumes/'})

    def test_media_is_only_served_by_django_in_development_with_local_storage(self):
        self.assertEqual(media_urlpatterns(False, '/media/', self.root), [])
        self.assertEqual(
            media_urlpatterns(True, 'https://bucket.s3.amazonaws.com/media/', self.root), [])
        patterns = media_urlpatterns(True, '/media/', self.root)
        self.assertEqual(len(patterns), 1)
        self.assertIs(patterns[0].callback, serve_public_media)

    def test_root_urlconf_no_longer_serves_media_with_static(self):
        source = io.open(os.path.join('config', 'urls.py'), encoding='utf-8').read()
        self.assertNotIn('static(settings.MEDIA_URL', source)
        self.assertIn('media_urlpatterns(', source)
