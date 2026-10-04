"""
Phase 1 close-out PR 2: real slide/page provenance (Nike baseline L-014).

Extraction knows the true slide/page sequence; it now writes it into the
text as reserved marker lines, and the chunker splits on those instead of
guessing. Every downstream page number -- chunk, claim, retrieval source,
GroundedContext citation -- is inherited from the chunk, never recomputed.
Text with no markers is unpaginated (None), never numbered by position.
"""
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files import File
from django.test import SimpleTestCase, TestCase

from zelda_api.chunking import DocumentChunker
from zelda_api.utils import (
    extract_text_from_file, has_usable_text, page_marker, split_pages, strip_page_markers,
)

DECK = 'docs/baselines/nike-fy2026/nike_zelda_adversarial_test_deck.pptx'


def nike_text():
    with open(DECK, 'rb') as handle:
        return extract_text_from_file(File(handle, name='nike.pptx'))


def chunker():
    return DocumentChunker(chunk_size_tokens=400, overlap_tokens=50)


def pages_containing(chunks, needle):
    return {page for text, page, _ in chunks if needle in text}


class MarkerTests(SimpleTestCase):

    def test_split_pages_reads_real_numbers(self):
        text = f'{page_marker("slide", 1)}\nalpha\n{page_marker("slide", 2)}\nbeta\n'
        self.assertEqual([(n, s.strip()) for n, s in split_pages(text)], [(1, 'alpha'), (2, 'beta')])

    def test_text_before_the_first_marker_is_unknown(self):
        text = f'preamble\n{page_marker("page", 7)}\nbody\n'
        self.assertEqual([(n, s.strip()) for n, s in split_pages(text)], [(None, 'preamble'), (7, 'body')])

    def test_unmarked_text_is_one_unknown_segment(self):
        self.assertEqual(split_pages('just text'), [(None, 'just text')])

    def test_markers_alone_are_not_usable_text(self):
        self.assertFalse(has_usable_text(f'{page_marker("slide", 1)}\n{page_marker("slide", 2)}\n'))
        self.assertTrue(has_usable_text(f'{page_marker("slide", 1)}\nreal words\n'))

    def test_marker_lookalikes_in_content_are_not_markers(self):
        text = 'We cite [[zelda:slide 3]] inline here.'
        self.assertEqual(split_pages(text), [(None, text)])


class NikeDeckTests(SimpleTestCase):
    """The frozen baseline deck: 10 slides, facts on known slides (ANSWER_KEY.md)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.text, cls.pages = nike_text()
        cls.chunks = chunker().chunk(cls.text)

    def test_one_chunk_per_slide_numbered_one_to_ten(self):
        self.assertEqual(self.pages, 10)
        self.assertEqual([page for _, page, _ in self.chunks], list(range(1, 11)))

    def test_titles_are_the_slide_titles(self):
        titles = {page: title for _, page, title in self.chunks}
        self.assertEqual(titles[2], 'Company Snapshot')
        self.assertEqual(titles[10], 'Diligence Questions for Zelda')

    def test_answer_key_facts_sit_on_their_slides(self):
        expected = {
            'Delaware': {2, 6, 8},          # C04
            '81,500': {2, 6},               # C02
            '$52.8B': {2, 4},               # C01
            '$52.8 billion': {3},           # C01, thesis bullet
            '46.1%': {4},                   # C11
            '0000320187': {8},              # C07
            'NIKE Direct revenue declined 6%': {7},   # C19
            'Diligence Questions for Zelda': {10},    # N1
        }
        for needle, slides in expected.items():
            with self.subTest(fact=needle):
                self.assertEqual(pages_containing(self.chunks, needle), slides)

    def test_markers_never_reach_chunk_text(self):
        for text, _, _ in self.chunks:
            self.assertNotIn('[[zelda:', text)


class PdfPageTests(SimpleTestCase):

    def test_pdf_pages_carry_their_numbers(self):
        class FakePage:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class FakeReader:
            def __init__(self, _file):
                self.pages = [FakePage('First page about revenue and growth.'), FakePage(None),
                              FakePage('Third page about the founding team.')]

        with mock.patch('PyPDF2.PdfReader', FakeReader):
            text, pages = extract_text_from_file(File(open(DECK, 'rb'), name='deck.pdf'))
        chunks = chunker().chunk(text)
        self.assertEqual(pages, 3)
        self.assertEqual([(page, t) for t, page, _ in chunks],
                         [(1, 'First page about revenue and growth.'), (3, 'Third page about the founding team.')])


class ChunkingRuleTests(SimpleTestCase):

    def test_a_long_page_keeps_one_number_across_its_chunks(self):
        body = '\n'.join(f'Line {i} with several words of content about the business.' for i in range(120))
        text = f'{page_marker("page", 5)}\n{body}\n{page_marker("page", 6)}\nShort closing page text here.\n'
        chunks = DocumentChunker(chunk_size_tokens=100, overlap_tokens=10).chunk(text)
        pages = [page for _, page, _ in chunks]
        self.assertGreater(pages.count(5), 1)
        self.assertEqual(set(pages), {5, 6})
        self.assertEqual(pages[-1], 6)

    def test_unmarked_text_is_unpaginated(self):
        text = 'Overview\nWe build tools for teams.\nMarket\nA large and growing market for this.\nTeam\nTwo founders with experience.\n'
        chunks = chunker().chunk(text)
        self.assertTrue(chunks)
        self.assertEqual({page for _, page, _ in chunks}, {None})


class DownstreamInheritanceTests(TestCase):
    """Chunks, claims and retrieval all carry the extracted slide number unchanged."""

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        from zelda_api.vector_models import DocumentSource
        _mock_embedding_generation(self)
        self.user = get_user_model().objects.create_user('prov_owner', password='x')
        self.doc = DocumentSource.objects.create(
            filename='nike.pptx', source_entity='NIKE, Inc.', uploaded_by=self.user,
            document_type='pitch_deck', status='analyzing')

    def test_nike_claims_cite_their_answer_key_slides(self):
        from zelda_api import truth_delta_tasks
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        from zelda_api.truth_delta_models import ClaimedDatapoint
        from zelda_api.vector_models import DocumentChunk

        text, _ = nike_text()
        pipeline = ZeldaIntelligencePipelineV2()
        pipeline._chunk_document(self.doc, text)
        self.assertEqual(list(DocumentChunk.objects.filter(document=self.doc).order_by('chunk_index')
                              .values_list('page_number', flat=True)), list(range(1, 11)))
        pipeline.used_chunks = set()
        pipeline._analyze_document(self.doc, text)
        with mock.patch.object(truth_delta_tasks.verify_document_truth_delta, 'delay'):
            truth_delta_tasks.extract_claims_from_insights(self.doc.id)
        pages = dict(ClaimedDatapoint.objects.filter(document=self.doc).values_list('category', 'page_number'))
        # Baseline: employees cited page 9 and revenue page 1, neither a real slide for the claim.
        self.assertEqual(pages.get('employees'), 6)     # "employs approximately 81,500 people worldwide"
        self.assertEqual(pages.get('revenue'), 3)       # "$52.8 billion, supported by wholesale growth"

    def test_rag_sources_report_the_chunk_page(self):
        from django.urls import reverse
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2

        text, _ = nike_text()
        ZeldaIntelligencePipelineV2()._chunk_document(self.doc, text)
        self.client.force_login(self.user)
        response = self.client.post(reverse('zelda_api:document_rag', args=[self.doc.pk]),
                                    data=json.dumps({'query': 'state incorporation Delaware'}),
                                    content_type='application/json').json()
        self.assertTrue(response['sources'])
        self.assertTrue({s['page'] for s in response['sources']} <= {2, 6, 8, 10})

    def test_stored_preview_and_word_count_exclude_markers(self):
        from django.urls import reverse
        from zelda_api.vector_models import DocumentSource

        self.client.force_login(self.user)
        with open(DECK, 'rb') as handle, \
                mock.patch('zelda_api.pipeline_views.process_document_pipeline.delay'):
            response = self.client.post(reverse('zelda_api:document_ingest'),
                                        {'file': handle, 'source_entity': 'NIKE, Inc.', 'document_type': 'pitch_deck'})
        doc = DocumentSource.objects.get(pk=response.json()['document_id'])
        self.assertNotIn('[[zelda:', doc.raw_text_preview)
        self.assertIn('[[zelda:slide 1]]', doc.raw_text_full)     # kept for reprocessing
        self.assertEqual(doc.total_word_count, len(strip_page_markers(doc.raw_text_full).split()))
