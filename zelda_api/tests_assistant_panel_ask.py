"""
RA-114: the panel's Ask tab shows only the answer to the question still being asked.

Review of 8d08fe5, finding 3: ask about Deck A, choose Deck B before A answers, and A's excerpts rendered under "Asking
about Deck B". Every Ask now takes the next request number, and choosing or clearing a document moves it on, so an
answer to anything but the newest request -- an older question, or one asked under another context -- is not shown.

zelda_api/js_tests/assistant_panel_ask.js runs the template's own Ask functions in Node with a stubbed DOM and a fetch
whose answers each scenario releases in its own order. Skips when Node is not installed.
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

TEMPLATE = Path(settings.BASE_DIR) / 'templates' / 'includes' / 'zelda_ai_assistant_enhanced.html'
HARNESS = Path(settings.BASE_DIR) / 'zelda_api' / 'js_tests' / 'assistant_panel_ask.js'
NODE = shutil.which('node')
STALE = 'An earlier question was answered after you moved on; its answer is not shown.'


@unittest.skipUnless(NODE, 'node is not installed')
class AskTabTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        out = subprocess.run([NODE, str(HARNESS), str(TEMPLATE)], capture_output=True, text=True,
                             encoding='utf-8', timeout=60)
        if out.returncode:
            raise AssertionError(out.stderr)
        cls.screens = json.loads(out.stdout)

    def test_the_current_answer_renders(self):
        screen = self.screens['current_answer']
        self.assertEqual((screen['context'], screen['card']), ('Deck A', 'block'))
        self.assertIn('DECK-A-EXCERPT', screen['list'])
        self.assertEqual(screen['bodies'], [{'q': 'How much has A raised?', 'document_id': 1}])

    def test_an_answer_never_renders_under_another_document(self):
        screen = self.screens['switched_document']
        self.assertEqual(screen['context'], 'Deck B')
        self.assertNotIn('DECK-A-EXCERPT', screen['list'])
        self.assertNotEqual(screen['card'], 'block')
        self.assertFalse(any('1 passage' in entry for entry in screen['log']))   # nor its response line
        self.assertEqual(screen['log'][-1], STALE)

    def test_an_older_question_never_replaces_a_newer_answer(self):
        screen = self.screens['newer_question_wins']
        self.assertIn('DECK-B-NEWER-EXCERPT', screen['list'])
        self.assertNotIn('DECK-B-OLDER-EXCERPT', screen['list'])

    def test_an_answer_never_renders_after_returning_to_the_marketplace(self):
        screen = self.screens['cleared_while_pending']
        self.assertEqual(screen['context'], '')
        self.assertNotIn('DECK-B-OLDER-EXCERPT', screen['list'])
        self.assertNotEqual(screen['card'], 'block')

    def test_a_stale_refusal_or_failure_says_nothing(self):
        log = '\n'.join(self.screens['stale_error']['log'])
        self.assertNotIn('STALE-REFUSAL', log)
        self.assertNotIn('STALE-NETWORK-FAILURE', log)

    def test_the_marketplace_still_sends_q_alone_and_shows_its_cards(self):
        screen = self.screens['marketplace']
        self.assertEqual(screen['bodies'], [{'q': 'seed founders'}])
        self.assertIn('MARKET-CARD', screen['list'])
        self.assertEqual(screen['card'], 'block')

    def test_an_older_marketplace_answer_never_replaces_a_newer_one(self):
        screen = self.screens['marketplace_newer_wins']
        self.assertEqual(screen['bodies'], [{'q': 'older search'}, {'q': 'newer search'}])
        self.assertIn('MARKET-CARD', screen['list'])
