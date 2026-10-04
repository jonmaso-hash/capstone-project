"""
Phase 1 close-out PR 3, part 3: extraction failures are failures (Nike L-001).

A missing parser used to return "PPTX parsing requires python-pptx..." as the
document's text -- chunked, embedded and analyzed as if it were the deck --
and any other failure returned "", indistinguishable from an image-only deck.
Now each raises ExtractionError with a reason, and the upload paths refuse
with a message that says which, before any document exists.
"""
import inspect
import sys
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from zelda_api import utils
from zelda_api.utils import EXTRACTION_FAILURE_MESSAGES, ExtractionError, extract_text_from_file

DECK = 'docs/baselines/nike-fy2026/nike_zelda_adversarial_test_deck.pptx'


def upload(name, content):
    return SimpleUploadedFile(name, content)


class ExtractorTests(SimpleTestCase):

    def assertReason(self, reason, uploaded):
        with self.assertRaises(ExtractionError) as caught:
            extract_text_from_file(uploaded)
        self.assertEqual(caught.exception.reason, reason)

    def test_missing_pptx_parser_is_a_failure_not_text(self):
        with open(DECK, 'rb') as handle, mock.patch.dict(sys.modules, {'pptx': None}):
            self.assertReason('dependency_missing', upload('deck.pptx', handle.read()))

    def test_missing_pdf_parser_is_a_failure_not_text(self):
        with mock.patch.dict(sys.modules, {'PyPDF2': None}):
            self.assertReason('dependency_missing', upload('deck.pdf', b'%PDF-1.4'))

    def test_a_damaged_file_is_unreadable(self):
        self.assertReason('unreadable_file', upload('deck.pptx', b'this is not a presentation'))
        self.assertReason('unreadable_file', upload('deck.pdf', b'not a pdf at all'))

    def test_an_unsupported_type_says_so(self):
        self.assertReason('unsupported_format', upload('deck.docx', b'PK...'))

    def test_a_readable_deck_still_reads(self):
        with open(DECK, 'rb') as handle:
            text, pages = extract_text_from_file(upload('deck.pptx', handle.read()))
        self.assertEqual(pages, 10)
        self.assertIn('Company Snapshot', text)

    def test_no_extractor_can_return_an_error_sentence_as_text(self):
        for function in (utils._extract_pdf_text, utils._extract_pptx_text, utils.extract_text_from_file):
            source = inspect.getsource(function)
            with self.subTest(function=function.__name__):
                self.assertNotIn('pip install', source)
                self.assertNotIn('return "", 0', source)

    def test_every_reason_has_a_message(self):
        self.assertEqual(set(EXTRACTION_FAILURE_MESSAGES), set(ExtractionError.REASONS))
        with self.assertRaises(AssertionError):
            ExtractionError('made_up_reason')


class UploadRefusalTests(TestCase):

    def setUp(self):
        from matchmaking.models import Application
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        self.user = get_user_model().objects.create_user('extract_owner', password='x')
        Application.objects.create(user=self.user, company_name='Extract Co', founder_name='F',
                                   email='e@t.test', description='d', sector='SaaS', stage='Seed')
        self.client.force_login(self.user)

    def post(self, uploaded):
        from zelda_api.vector_models import DocumentSource
        before = DocumentSource.objects.count()
        with mock.patch('zelda_api.pipeline_views.process_document_pipeline.delay') as queued:
            response = self.client.post(reverse('zelda_api:document_ingest'),
                                        {'file': uploaded, 'source_entity': 'Extract Co', 'document_type': 'pitch_deck'})
        self.assertEqual(DocumentSource.objects.count(), before, 'a failed extraction must create no document')
        queued.assert_not_called()
        return response

    def test_missing_parser_is_a_503_and_creates_nothing(self):
        with open(DECK, 'rb') as handle, mock.patch.dict(sys.modules, {'pptx': None}):
            response = self.post(upload('deck.pptx', handle.read()))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['code'], 'dependency_missing')
        self.assertNotIn('pip install', response.content.decode())

    def test_damaged_and_unsupported_files_are_400s_that_say_which(self):
        for uploaded, code in ((upload('deck.pptx', b'garbage'), 'unreadable_file'),
                               (upload('deck.docx', b'PK...'), 'unsupported_format')):
            with self.subTest(code=code):
                response = self.post(uploaded)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json(), {'error': EXTRACTION_FAILURE_MESSAGES[code], 'code': code})
