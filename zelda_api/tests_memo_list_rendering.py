"""
RA-002 / RA-107 / BW-004: list-valued memo sections render as bullets.

Ben & Jerry's memo 90 stores questions_for_management as the model's JSON list
text; ManyChat's memo 91 stores three sections as Python list reprs (what a
TextField saves for a list). Both reached the IC memo page, its Markdown
export and the memo API as raw list syntax. The fixtures below are those two
stored formats, built from items copied out of the saved rows.
"""
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils.html import escape

from .memo_lists import MAX_LITERAL_CHARS, memo_list_items, memo_text
from .vector_models import DocumentSource, IntelligenceMemo

User = get_user_model()

# Memo 90, questions_for_management (JSON text): apostrophes, em dashes, [S2].
BJ_ITEMS = [
    "What are Ben & Jerry's audited standalone revenues, gross margins, and operating income, fully "
    "separated from Unilever consolidated or ice cream division reporting? [S2]",
    "What is the precise ownership and governance structure governing Ben & Jerry's, and what decisions "
    "— product, pricing, distribution, social mission — does the brand board control independently "
    "of Unilever?",
]
BJ_STORED = json.dumps(BJ_ITEMS, ensure_ascii=False)

# Memo 91 (Python repr of a list): the second item contains apostrophes, so
# repr() double-quotes it -- the mixed quoting the saved rows really have.
MC_ITEMS = [
    'What is the current annual recurring revenue (ARR) or monthly recurring revenue (MRR), and what '
    'has the growth rate been over the past 12 months?',
    "How are '140,000+ bots' and '500M messages' defined — do they represent active bots, cumulative "
    "bots ever created, paid accounts only, or a broader count including free-tier users?",
    'The two primary scale metrics — 140,000+ bots and 500M messages — are entirely self-reported '
    '[S1, S2] and were checked without locating external confirmation [C2, C3].',
]
MC_STORED = str(MC_ITEMS)

PROSE = ("The single most important missing piece of evidence is audited financials [S1]. "
         "Without them [S2, S3] the platform metrics cannot be tied to revenue.")
BULLET_PROSE = ("• The company states it frames its business around 'linked prosperity' [S4].\n"
                "• It is unknown whether Ben & Jerry's generates attributable revenue [S2].")


class MemoListParsingTests(SimpleTestCase):

    def test_both_stored_formats_and_native_lists_keep_order_wording_and_citations(self):
        self.assertEqual(memo_list_items(BJ_STORED), BJ_ITEMS)
        self.assertEqual(memo_list_items(MC_STORED), MC_ITEMS)
        self.assertEqual(memo_list_items(MC_ITEMS), MC_ITEMS)
        self.assertEqual(memo_list_items(tuple(BJ_ITEMS)), BJ_ITEMS)
        self.assertEqual(memo_text(MC_STORED), '\n'.join('- ' + item for item in MC_ITEMS))

    def test_ordinary_prose_with_citations_is_not_a_list(self):
        for text in (PROSE, BULLET_PROSE, '[S1] The deck states revenue grew [S2]',
                     '[S1]', '[S1, S2]', 'Not assessed.', ''):
            with self.subTest(text=text):
                self.assertIsNone(memo_list_items(text))
                self.assertEqual(memo_text(text), text)

    def test_empty_malformed_and_unsupported_values_are_kept_not_dropped(self):
        self.assertEqual(memo_list_items('[]'), [])
        self.assertEqual(memo_text('[]'), '')
        self.assertEqual(memo_text(None), '')
        truncated = MC_STORED[:-30]                           # a cut-off repr
        for text in (truncated, '[1, 2]', "['a', 3]", '[["nested"]]', '{"gap": "x [S1]"}'):
            with self.subTest(text=text):
                self.assertIsNone(memo_list_items(text))
                self.assertEqual(memo_text(text), text)
        self.assertIsNone(memo_list_items([{'gap': 'Revenue period not disclosed [S2]'}]))
        self.assertIn('Revenue period not disclosed [S2]', memo_text([{'gap': 'Revenue period not disclosed [S2]'}]))
        self.assertEqual(memo_list_items(['a', '  ', 'b']), ['a', 'b'])

    def test_parsing_never_evaluates_code(self):
        hostile = "[__import__('os').system('echo pwned')]"
        with mock.patch('builtins.eval', side_effect=AssertionError('eval called')), \
             mock.patch('os.system', side_effect=AssertionError('code ran')):
            self.assertIsNone(memo_list_items(hostile))
            self.assertEqual(memo_text(hostile), hostile)
        huge = str(['x' * 100] * (MAX_LITERAL_CHARS // 100))
        self.assertIsNone(memo_list_items(huge))            # over the literal cap: shown as stored

    def test_bullet_lines_written_for_new_memos_read_back_as_the_same_items(self):
        self.assertEqual(memo_list_items(memo_text(BJ_ITEMS)), BJ_ITEMS)
        self.assertIsNone(memo_list_items('- one point\nand a prose line'))


class MemoListSurfaceTests(TestCase):
    """The IC memo HTML, its Markdown export and the memo API, from stored rows."""

    HOSTILE = ["<script>alert('x')</script> & <b>bold</b> [S1]", "Plain item [S2]"]

    def setUp(self):
        from matchmaking.models import Application
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        self.owner = User.objects.create_user('ml_owner', password='x')
        Application.objects.create(user=self.owner, company_name='ListCo', founder_name='F',
                                   email='ml@t.test', description='d', sector='Consumer', stage='Public')
        self.staff = User.objects.create_user('ml_staff', password='x', is_staff=True)
        self.doc = DocumentSource.objects.create(uploaded_by=self.owner, filename='deck.pdf', source_entity='ListCo',
                                                 document_type='pitch_deck', status='analyzed')
        self.memo = IntelligenceMemo.objects.create(
            document=self.doc, executive_summary='ListCo summary [S1].',
            questions_for_management=BJ_STORED, supported_points=MC_STORED,
            open_concerns=str(self.HOSTILE), what_would_change_the_picture=PROSE,
            information_readiness=BULLET_PROSE, upside_scenario='[]',
            evidence_level='LITTLE_EVIDENCE', completeness_score=0.5, citations_count=3)
        self.stored = IntelligenceMemo.objects.values().get(pk=self.memo.pk)
        self.client.force_login(self.staff)

    def test_html_renders_escaped_bullets_and_leaves_prose_alone(self):
        html = self.client.get(reverse('zelda_api:ic_memo', args=[self.doc.id])).content.decode()
        for item in BJ_ITEMS + MC_ITEMS:
            self.assertIn(f'<li class="mb-1">{escape(item)}</li>', html)
        self.assertIn(f'<li class="mb-1">{escape(self.HOSTILE[0])}</li>', html)
        self.assertNotIn("<script>alert('x')</script>", html)
        self.assertNotIn('<b>bold</b>', html)
        self.assertNotIn('[&quot;What are', html)            # no JSON list text
        self.assertNotIn('[&#x27;What is', html)              # no Python repr
        self.assertIn(escape(PROSE), html)
        self.assertIn(escape(BULLET_PROSE), html)
        self.assertNotIn('pb-2 mb-2">Upside Scenario</h5>', html)   # '[]' is an empty section
        self.assertIn('pb-2 mb-2">Questions for Management</h5>', html)
        # Order is preserved within a section.
        self.assertLess(html.index(escape(MC_ITEMS[0])), html.index(escape(MC_ITEMS[1])))

    def test_markdown_export_writes_bullets(self):
        response = self.client.get(reverse('zelda_api:ic_memo_download', args=[self.doc.id]))
        markdown = response.content.decode()
        for item in BJ_ITEMS + MC_ITEMS:
            self.assertIn(f'\n- {item}\n', markdown)
        self.assertNotIn('["What are', markdown)
        self.assertNotIn("['What is", markdown)
        self.assertIn(PROSE, markdown)
        self.assertIn(BULLET_PROSE, markdown)

    def test_memo_api_sends_bullet_text(self):
        data = self.client.get(reverse('zelda_api:document_memo', args=[self.doc.id]),
                               HTTP_ACCEPT='application/json').json()
        sections = data['sections']
        self.assertEqual(sections['questions_for_management'], '\n'.join('- ' + i for i in BJ_ITEMS))
        self.assertEqual(sections['supported_points'], '\n'.join('- ' + i for i in MC_ITEMS))
        self.assertEqual(sections['what_would_change_the_picture'], PROSE)

    def test_saved_rows_are_read_never_rewritten(self):
        self.client.get(reverse('zelda_api:ic_memo', args=[self.doc.id]))
        self.client.get(reverse('zelda_api:ic_memo_download', args=[self.doc.id]))
        self.client.get(reverse('zelda_api:document_memo', args=[self.doc.id]))
        self.assertEqual(IntelligenceMemo.objects.values().get(pk=self.memo.pk), self.stored)


class MemoListWriterTests(TestCase):
    """New memos are stored as "- item" text, never a Python repr."""

    def test_list_and_json_list_sections_are_stored_as_bullet_lines(self):
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from zelda_api.tests import grounded_context_for
        owner = User.objects.create_user('ml_writer', password='x')
        doc = DocumentSource.objects.create(filename='deck.txt', source_entity='WriterCo', uploaded_by=owner,
                                            document_type='pitch_deck', raw_text_full='Revenue of $1M.')
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value={
                'executive_summary': PROSE, 'questions_for_management': MC_ITEMS,
                'supported_points': BJ_STORED, 'open_concerns': BULLET_PROSE,
                'evidence_level': 'LITTLE_EVIDENCE'}), \
             mock.patch.object(pipeline, '_build_structured_context', return_value=''):
            result = pipeline._generate_memo(grounded_context_for(doc))
        self.assertNotIn('error', result, result.get('error'))
        memo = IntelligenceMemo.objects.get(document=doc)
        self.assertEqual(memo.questions_for_management, '\n'.join('- ' + i for i in MC_ITEMS))
        self.assertEqual(memo.supported_points, '\n'.join('- ' + i for i in BJ_ITEMS))
        self.assertEqual(memo.executive_summary, PROSE)
        self.assertEqual(memo.open_concerns, BULLET_PROSE)
        self.assertEqual(memo.evidence_level, 'LITTLE_EVIDENCE')
