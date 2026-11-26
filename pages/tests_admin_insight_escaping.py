"""
Three staff-admin display methods built their HTML as a plain string and
passed it to format_html() with no arguments:

- DocumentSourceAdmin.intelligence_display
- IntelligenceInsightAdmin.source_chunks_display
- IntelligenceMemoAdmin.insights_used_display

On the deployed Django 6.0 that raises TypeError ("args or kwargs must be
provided"), so those admin change pages returned 500 for any record that
reached them. On earlier Django the same call marked the string safe without
escaping, and insights_used_display includes insight_text -- a sentence the
pipeline takes from an uploaded document -- so it was a stored XSS against
staff waiting for a downgrade or a copy of the pattern. Each method now uses
format_html / format_html_join with placeholders, so every value is escaped.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.tests import _mock_embedding_generation
from zelda_api.admin_intelligence import IntelligenceMemoAdmin
from zelda_api.vector_models import DocumentSource, IntelligenceInsight, IntelligenceMemo

User = get_user_model()
PAYLOAD = '<img src=x onerror=alert(1)>ARR $5M'


class AdminInsightEscapingTests(TestCase):
    def setUp(self):
        _mock_embedding_generation(self)
        owner = User.objects.create_user('uploader', password='x')
        document = DocumentSource.objects.create(uploaded_by=owner, filename='deck.pdf', source_entity='Co',
                                                 document_type='pitch_deck', status='analyzed')
        self.insight = IntelligenceInsight.objects.create(document=document, category='revenue', insight_text=PAYLOAD)
        self.memo = IntelligenceMemo.objects.create(document=document, executive_summary='s')
        self.memo.insights_used.add(self.insight)

    def test_insight_text_is_escaped(self):
        html = str(IntelligenceMemoAdmin.insights_used_display(None, self.memo))
        self.assertNotIn('<img', html)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', html)
        self.assertIn('• revenue: ', html, 'positive control: the insight is still listed')

    def test_several_insights_are_joined_with_real_line_breaks(self):
        other = IntelligenceInsight.objects.create(document=self.memo.document, category='team', insight_text='"><script>x</script>')
        self.memo.insights_used.add(other)
        html = str(IntelligenceMemoAdmin.insights_used_display(None, self.memo))
        self.assertEqual(html.count('<br>'), 1)
        self.assertNotIn('<script>', html)

    def test_no_insights(self):
        self.memo.insights_used.clear()
        self.assertEqual(str(IntelligenceMemoAdmin.insights_used_display(None, self.memo)), 'No insights linked')

    @mock.patch('accounts.staff_mfa.is_verified', return_value=True)
    def test_document_and_insight_admin_pages_render(self, _verified):
        from zelda_api.vector_models import DocumentChunk
        chunk = DocumentChunk.objects.create(document=self.memo.document, chunk_index=3, raw_text='chunk text', token_count=2)
        self.insight.source_chunks.add(chunk)
        staff = User.objects.create_user('staff_pages', password='x', is_staff=True, is_superuser=True)
        self.client.force_login(staff)
        for name, pk in (('admin:zelda_api_documentsource_change', self.memo.document.pk),
                         ('admin:zelda_api_intelligenceinsight_change', self.insight.pk)):
            with self.subTest(name=name):
                response = self.client.get(reverse(name, args=[pk]))
                self.assertEqual(response.status_code, 200)
        self.assertContains(self.client.get(reverse('admin:zelda_api_intelligenceinsight_change', args=[self.insight.pk])), 'Chunk #3</a>')

    @mock.patch('accounts.staff_mfa.is_verified', return_value=True)
    def test_the_admin_change_page_renders_the_insight_as_text(self, _verified):
        staff = User.objects.create_user('staffer', password='x', is_staff=True, is_superuser=True)
        self.client.force_login(staff)
        response = self.client.get(reverse('admin:zelda_api_intelligencememo_change', args=[self.memo.pk]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', content)
        self.assertNotIn(PAYLOAD, content)
