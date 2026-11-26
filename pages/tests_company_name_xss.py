"""
A company name is text everywhere it reaches another user's browser.

Reproduced at 7ba055c (isolated local server, harmless flag payloads): a
founder's company_name ran script in an investor's browser.

- `Quote Co');window.x=1;('` broke out of the JavaScript string in the
  "Analyze with Zelda" onclick: Django's HTML escaping turns ' into &#x27;,
  and the browser decodes that back before running the handler. The profile
  Share button had the same shape.
- `Quartz<img src=x onerror=...>` ran from the confirm modal, which wrote the
  name (and the match reasons) with innerHTML.
- The chat sidebar wrote the channel name -- the founder's or seller's
  company name -- with innerHTML.

The site CSP only reports inline handlers, so it did not stop either.
Values inside a JavaScript string in an on* attribute now go through
|escapejs (as blog, jobs and pitch-video Share buttons already did), the modal
escapes with zeldaEscape, and the chat sidebar uses textContent.
"""
import re
from html.parser import HTMLParser
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from matchmaking.models import Application, Connection, InvestorApplication
from matchmaking.tests import _mock_embedding_generation

User = get_user_model()
ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'templates'

ON_ATTR = re.compile(r'\son[a-z]+="([^"]*)"', re.S)
QUOTED = re.compile(r"'(\{\{.*?\}\}|\{%\s*firstof.*?%\})'", re.S)
# Values that cannot carry a quote or markup: numeric ids, Django usernames
# (letters, digits and @.+-_), and the validated request host/scheme.
SAFE_NAME = re.compile(r'(\.(id|pk)|_id|\.username|^request\.(scheme|get_host))$')


def _safe(expr):
    var, *filters = [part.strip() for part in expr.split('|')]
    return any(f.startswith('escapejs') for f in filters) or bool(SAFE_NAME.search(var))


def unescaped_js_string_values(text):
    """Template values inside a JavaScript string in an on* attribute, without |escapejs."""
    found = []
    for attr in ON_ATTR.finditer(text):
        for quoted in QUOTED.finditer(attr.group(1)):
            tag = quoted.group(1)
            if tag.startswith('{%'):
                parts = [p for p in tag.strip('{%} ').split()[1:] if p != 'as']
                bad = [p for p in parts if not _safe(p)]
            else:
                bad = [] if _safe(tag.strip('{} ')) else [tag]
            if bad:
                found.append((text.count('\n', 0, attr.start()) + 1, tag[:80]))
    return found


class TemplateLintTests(SimpleTestCase):
    def test_the_lint_catches_the_shape_that_was_exploited(self):
        # Positive controls: the exact markup that ran script, and its fixed form.
        bad = """<button onclick="analyzeFounderWithZelda(this, '{{ u.username }}', '{{ application.company_name|default:u.username }}')">"""
        share = """<a onclick="openContentShare('P', {{ u.id }}, '{% firstof a.company_name u.username %}')">"""
        self.assertEqual(len(unescaped_js_string_values(bad)), 1)
        self.assertEqual(len(unescaped_js_string_values(share)), 1)
        self.assertEqual(unescaped_js_string_values(bad.replace('u.username }}\')', 'u.username|escapejs }}\')')), [])

    def test_no_template_puts_an_unescaped_value_in_a_handler_string(self):
        offenders = {}
        for path in sorted(TEMPLATES.rglob('*.html')):
            found = unescaped_js_string_values(path.read_text(encoding='utf-8', errors='ignore'))
            if found:
                offenders[str(path.relative_to(ROOT))] = found
        self.assertEqual(offenders, {}, 'use |escapejs for any value inside a JavaScript string in an on* attribute')


class _Onclicks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.handlers = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name.startswith('on') and value:
                self.handlers.append(value)  # entity-decoded, exactly as the browser runs it


class ProfileHandlerEscapingTests(TestCase):
    PAYLOAD = "Quote Co');window.__xss=1;('<img src=x onerror=1>"

    def setUp(self):
        _mock_embedding_generation(self)
        founder = User.objects.create_user('xss_founder', password='x')
        self.founder = Application.objects.create(user=founder, company_name=self.PAYLOAD, founder_name='F',
                                                  email='f@x.invalid', description='d', sector='SaaS', stage='Seed')
        investor = User.objects.create_user('xss_investor', password='x')
        inv = InvestorApplication.objects.create(user=investor, full_name='I', email='i@x.invalid', company_name='Cap',
                                                 investment_focus='SaaS', investment_stage='Seed')
        Connection.objects.create(investor=inv, founder=self.founder, status='ACCEPTED')
        self.client.force_login(investor)

    def test_the_company_name_stays_inside_its_javascript_string(self):
        response = self.client.get('/accounts/profile/xss_founder/')
        self.assertEqual(response.status_code, 200)
        parser = _Onclicks()
        parser.feed(response.content.decode())
        relevant = [h for h in parser.handlers if 'analyzeFounderWithZelda' in h or 'openContentShare' in h]
        self.assertGreaterEqual(len(relevant), 2, 'positive control: both the Analyze and Share buttons render')
        for handler in relevant:
            with self.subTest(handler=handler[:40]):
                self.assertNotIn("Quote Co');", handler)
                self.assertNotIn('<img', handler)
                self.assertIn('Quote Co\\u0027)', handler)  # escapejs encodes the quote (and ; < > =)


class ClientSideSinkTests(SimpleTestCase):
    def test_confirm_modal_escapes_the_company_name_and_reasons(self):
        source = (TEMPLATES / 'includes' / 'zelda_ai_assistant_enhanced.html').read_text(encoding='utf-8')
        modal = source.split('function showZeldaConfirmGenerateModal', 1)[1].split('async function confirmGenerateZeldaAnalysis', 1)[0]
        self.assertNotIn('${companyName}', modal)
        self.assertNotIn('${r}', modal)
        self.assertGreaterEqual(modal.count('${zeldaEscape(companyName)}'), 3)
        self.assertIn('${zeldaEscape(r)}', modal)

    def test_chat_sidebar_writes_the_channel_name_as_text(self):
        source = (TEMPLATES / 'matchmaking' / 'chat.html').read_text(encoding='utf-8')
        self.assertNotIn('${ch.data.name', source)
        self.assertIn("label.textContent = ch.data.name || 'Chat';", source)
