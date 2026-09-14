"""
The Zelda panel's tab sections must sit inside its scrolling body.

templates/includes/zelda_ai_assistant_enhanced.html once closed
.offcanvas-body straight after the tab buttons (a stray </div>) and opened
the execution log twice (a duplicated <div id="agent-response-log">), which
cancelled out. Browsers then rendered every tab section and the log as
siblings of the body instead of inside it. This parses the rendered page and
checks the nesting.
"""
from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.tests import _mock_embedding_generation

User = get_user_model()

PANEL_SECTIONS = [
    'tab-notifications', 'tab-search', 'tab-library', 'tab-upload',
    'tab-memo', 'tab-intelligence', 'tab-truth-delta', 'tab-progress',
    'agent-response-log',
]


class _DivNesting(HTMLParser):
    """Records each id'd div's ancestor divs. Only divs are tracked, so other
    tags left unclosed elsewhere on the page can't skew the result; script
    bodies are not parsed as markup."""

    def __init__(self):
        super().__init__()
        self.stack = []
        self.ancestors = {}
        self.id_counts = {}

    def handle_starttag(self, tag, attrs):
        if tag != 'div':
            return
        attrs = dict(attrs)
        div_id = attrs.get('id')
        if div_id:
            self.id_counts[div_id] = self.id_counts.get(div_id, 0) + 1
            self.ancestors.setdefault(div_id, list(self.stack))
        self.stack.append((div_id, (attrs.get('class') or '').split()))

    def handle_endtag(self, tag):
        if tag == 'div' and self.stack:
            self.stack.pop()


class ZeldaPanelMarkupTests(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.client.force_login(User.objects.create_user('panel_markup', password='x'))
        parser = _DivNesting()
        parser.feed(self.client.get(reverse('billing:billing_page')).content.decode())
        self.nesting = parser

    def test_every_tab_section_and_the_log_are_inside_the_panel_body(self):
        for section in PANEL_SECTIONS:
            with self.subTest(section=section):
                self.assertIn(section, self.nesting.ancestors, f'{section} not rendered')
                ancestor_ids = [div_id for div_id, _ in self.nesting.ancestors[section]]
                ancestor_classes = [classes for _, classes in self.nesting.ancestors[section]]
                self.assertIn('aiAgentSidebar', ancestor_ids)
                self.assertTrue(any('offcanvas-body' in c for c in ancestor_classes),
                                f'{section} renders outside .offcanvas-body')

    def test_the_execution_log_is_rendered_once(self):
        self.assertEqual(self.nesting.id_counts.get('agent-response-log'), 1)
