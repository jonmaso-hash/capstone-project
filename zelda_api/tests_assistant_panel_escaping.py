"""
The assistant panel must show API text as text, never as markup.

templates/includes/zelda_ai_assistant_enhanced.html builds the Memo and
Intelligence tabs by interpolating /api/v1/zelda/documents/<id>/memo/ values
into innerHTML. Before this change none of them were escaped:
- document_name (DocumentSource.source_entity, taken as typed at upload);
- every memo section;
- insight category and text;
- the disclaimer;
- the API error message;
- error text that can quote a response body.

Each now goes through the panel's own zeldaEscape helper.

Two layers:
- AssistantPanelRenderTests runs the real renderer functions (extracted from
  the template by zelda_api/js_tests/assistant_panel_escaping.js) in Node with
  a stubbed DOM and fetch. Payloads carry only inert markup (<b>, <i>), and the
  assertions check it arrives as escaped text in every view. It skips when Node
  is not installed.
- AssistantPanelSinkInventoryTests needs no Node. It lists every ${...} in
  those renderers and fails on any that is neither escaped nor a known
  constant, so a new raw interpolation cannot slip in.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

TEMPLATE = Path(settings.BASE_DIR) / 'templates' / 'includes' / 'zelda_ai_assistant_enhanced.html'
HARNESS = Path(settings.BASE_DIR) / 'zelda_api' / 'js_tests' / 'assistant_panel_escaping.js'
NODE = shutil.which('node')

RAW_MARKERS = ('<b>bold-marker</b>', '<i>q-marker</i>', '<b>cat-marker</b>')
ESCAPED = '&lt;b&gt;bold-marker&lt;/b&gt;'
VIEWS = ('memo', 'intelligence')


@unittest.skipUnless(NODE, 'node is not installed')
class AssistantPanelRenderTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        out = subprocess.run([NODE, str(HARNESS), str(TEMPLATE)], capture_output=True, text=True,
                             encoding='utf-8', timeout=60)
        if out.returncode:
            raise AssertionError(out.stderr)
        cls.results = json.loads(out.stdout)

    def html(self, key):
        return self.results[key]['html']

    def test_every_view_and_state_ran(self):
        self.assertEqual(set(self.results), {f'{view}:{state}' for view in VIEWS
                                             for state in ('full', 'lite', 'locked', 'failed', 'bad_json')})

    def test_api_text_never_becomes_markup(self):
        for key, out in self.results.items():
            with self.subTest(key=key):
                for marker in RAW_MARKERS:
                    self.assertNotIn(marker, out['html'])
                    self.assertNotIn(marker, out['log'])

    def test_full_view_escapes_name_sections_insights_and_disclaimer(self):
        for view in VIEWS:
            with self.subTest(view=view):
                html = self.html(f'{view}:full')
                self.assertIn(f'Name {ESCAPED} &amp; Co', html)
                # Citations, the ampersand and the newline (shown by pre-line) survive.
                self.assertIn(f'Line one [S1]\n{ESCAPED} &amp; more [S2]', html)
                self.assertIn('- First question [S3]\n- &lt;i&gt;q-marker&lt;/i&gt; second [C1]', html)
                self.assertIn('white-space: pre-line;', html)
                self.assertIn(f'Disclaimer {ESCAPED}', html)
        memo = self.html('memo:full')
        self.assertIn('Executive Summary', memo)
        self.assertIn('<strong>&lt;b&gt;cat-marker&lt;/b&gt;</strong>: Insight ' + ESCAPED + ' [S4]', memo)
        # Upper-cased first, then escaped: the entities stay lower case.
        self.assertIn('LITTLE EVIDENCE &lt;B&gt;BOLD-MARKER&lt;/B&gt;', memo)
        self.assertIn(f'3 {ESCAPED}', memo)

    def test_lite_view_escapes_and_keeps_the_redaction(self):
        for view in VIEWS:
            with self.subTest(view=view):
                html = self.html(f'{view}:lite')
                self.assertIn('Zelda Lite', html)
                self.assertIn('Supported Points', html)
                self.assertIn(f'- {ESCAPED} point [S1]\n- second point [S2]', html)
                self.assertIn(f'Name {ESCAPED} &amp; Co', html)
                self.assertNotIn('FULL-ONLY-SECTION-MARKER', html)
                self.assertNotIn('Executive Summary', html)

    def test_locked_view_escapes_the_name_and_shows_no_sections(self):
        for view in VIEWS:
            with self.subTest(view=view):
                html = self.html(f'{view}:locked')
                self.assertIn(f"Name {ESCAPED} &amp; Co hasn't unlocked", html)
                self.assertNotIn('Supported Points', html)
                self.assertNotIn('pre-line', html)

    def test_error_text_from_the_api_or_a_response_body_is_escaped(self):
        for view in VIEWS:
            with self.subTest(view=view):
                self.assertIn(f'Failed {ESCAPED}', self.html(f'{view}:failed'))
        self.assertIn(ESCAPED, self.html('intelligence:bad_json'))
        self.assertIn(ESCAPED, self.results['memo:bad_json']['log'])


def _function_source(text, name):
    start = re.search(rf'\n    (?:async )?function {name}\(', text)
    end = re.compile(r'\n    (?:(?:async )?function \w+\(|// ──)')
    stop = end.search(text, start.end())
    return text[start.start():stop.start() if stop else len(text)]


# Interpolations that are safe without escaping: constants, numbers, escaped
# fragments built just above, and messages handed to addLogEntry (which escapes).
ALLOWED = {
    'addLogEntry': {'timestamp', 'zeldaEscape(message)', 'type'},
    'renderLockedMemoCard': {"isOwner ? 'Unlock Your Intelligence Memo' : 'Premium Feature'", 'message', 'cta'},
    'renderLiteMemo': {'s.label'},
    'renderMemoFailed': set(),
    'renderDisclaimerFooter': set(),
    'loadMemo': {'docId', "data.lite_sections ? ' (showing Zelda Lite)' : ''", 'section.label', 'err.message'},
    'loadIntelligenceBrief': {'s.label', 'founderId', 'err.message'},   # err.message: addLogEntry only
    # RA-114 document answers: page and section escaped inside their own fragments; the rest of this span is the
    # Ask handler, whose interpolations go to addLogEntry (asked.name, question, err.message) or fetch (ZELDA_API).
    'renderDocumentEvidence': {"item.page != null ? `Page ${zeldaEscape(item.page)}` : 'Page not recorded'",
                               "item.section ? ` · ${zeldaEscape(item.section)}` : ''",
                               'asked.name', 'question', 'ZELDA_API', 'response.status', 'err.message'},
    'renderLibraryAskButton': {'Number(documentId)'},
}


class AssistantPanelSinkInventoryTests(SimpleTestCase):

    def test_every_interpolation_is_escaped_or_a_known_constant(self):
        text = TEMPLATE.read_text(encoding='utf-8').replace('\r\n', '\n')
        for name, allowed in ALLOWED.items():
            with self.subTest(function=name):
                source = _function_source(text, name)
                found = re.findall(r'\$\{((?:[^{}]|\{[^{}]*\})*)\}', source)
                self.assertTrue(found or name in ('renderMemoFailed',), name)
                unexpected = {expr for expr in found
                              if not expr.startswith('zeldaEscape(') and expr not in allowed}
                self.assertEqual(unexpected, set(), f'{name} interpolates unescaped: {unexpected}')

    def test_log_messages_are_escaped_where_they_become_markup(self):
        source = _function_source(TEMPLATE.read_text(encoding='utf-8').replace('\r\n', '\n'), 'addLogEntry')
        self.assertIn('${zeldaEscape(message)}', source)
