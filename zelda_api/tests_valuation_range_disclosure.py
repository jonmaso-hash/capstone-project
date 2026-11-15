"""Before paying for a business valuation, the buyer is told it may come without a numeric range.

The report withholds a range unless the evidence supports one (valuation_gate.py).
Every surface that takes payment for a valuation -- the standalone product, the
Complete Bundle, the 3-Report Pack, and the paid unlock of a Lite preview --
states that first, in the same words, and no pre-payment copy promises a range.
"""
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse

from billing.zelda_catalog import PRODUCTS
from .disclaimers import NO_RANGE_PREVIEW, VALUATION_RANGE_DISCLOSURE
from .vector_models import BusinessValuationReport, DocumentSource

User = get_user_model()

SELLS_A_VALUATION = {'valuation', 'complete_bundle', 'three_pack'}
TEMPLATES = Path(settings.BASE_DIR) / 'templates'


def _panels(user):
    request = RequestFactory().get('/')
    request.user = user
    html = render_to_string('includes/zelda_product_panels.html', {'user': user, 'csp_nonce': ''}, request=request)
    panels = {}
    for chunk in html.split('id="tab-product-')[1:]:
        key = chunk.split('"', 1)[0]
        panels[key] = chunk
    return panels


class PrePaymentCopyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('range_disclosure_buyer', password='x')

    def test_every_product_that_sells_a_valuation_discloses_it_before_the_checkout_button(self):
        panels = _panels(self.user)
        self.assertTrue(SELLS_A_VALUATION <= set(panels), panels.keys())
        for key in SELLS_A_VALUATION:
            with self.subTest(product=key):
                panel = panels[key]
                self.assertIn(VALUATION_RANGE_DISCLOSURE, panel)
                self.assertLess(panel.index(VALUATION_RANGE_DISCLOSURE), panel.index('zelda-product-checkout'))

    def test_products_without_a_valuation_carry_no_valuation_disclosure(self):
        panels = _panels(self.user)
        others = set(panels) - SELLS_A_VALUATION
        self.assertTrue(others)  # positive control: other products rendered
        for key in others:
            with self.subTest(product=key):
                self.assertNotIn(VALUATION_RANGE_DISCLOSURE, panels[key])

    def test_valuation_description_does_not_promise_a_range(self):
        description = PRODUCTS['valuation'][2]
        self.assertIn('numeric valuation range only when the documents support one', description)
        self.assertIn('Verified financials', description)

    def test_upload_page_states_the_condition(self):
        self.client.force_login(self.user)
        page = self.client.get(reverse('zelda_api:valuation_request')).content.decode()
        self.assertIn(VALUATION_RANGE_DISCLOSURE, page)
        self.assertNotIn('an estimated valuation range grounded entirely in what you submit', page)
        self.assertNotIn('Unlock the full valuation number', page)

    def test_teasers_do_not_promise_a_range(self):
        for template, old in (('pages/home.html', 'Explore an estimated value range'),
                              ('matchmaking/seller_dashboard.html', 'get an evidence-grounded valuation range before'),
                              ('matchmaking/seller_dashboard.html', 'Unlock it to see the valuation range.')):
            with self.subTest(template=template):
                self.assertNotIn(old, (TEMPLATES / template).read_text(encoding='utf-8'))


class PaidUnlockPreviewTests(TestCase):
    """The Lite preview sells the unlock; it must say whether this report has a range."""

    def preview(self, low, high):
        from matchmaking.models import Application
        user = User.objects.create_user(f'range_preview_{low}', password='x')
        Application.objects.create(user=user, company_name='Test Co')
        doc = DocumentSource.objects.create(
            filename='filing.pdf', source_entity='Test Co', document_type='business_valuation',
            uploaded_by=user, status='analyzed', total_pages=12, valuation_tier='preview')
        BusinessValuationReport.objects.create(
            document=doc, confidence_score=0.7, business_overview='We build tools.',
            financial_summary='Verified.', risk_report='Risk one.', valuation_summary='Summary.',
            valuation_low=low, valuation_high=high)
        self.client.force_login(user)
        return self.client.get(reverse('zelda_api:document_valuation', args=[doc.id])).json()

    def test_report_without_a_range_says_so_before_the_unlock(self):
        data = self.preview(None, None)
        self.assertEqual(data['valuation_tier'], 'preview')
        self.assertFalse(data['range_available'])
        self.assertEqual(data['no_range_note'], NO_RANGE_PREVIEW)
        self.assertNotIn('Estimated valuation range', data['unlock_includes'])
        self.assertIn('no numeric range', data['unlock_includes'][0])
        self.assertEqual(data['range_disclosure'], VALUATION_RANGE_DISCLOSURE)
        self.assertNotIn('valuation_low', data)

    def test_report_with_a_range_keeps_the_range_teaser_without_revealing_it(self):
        data = self.preview(1_000_000, 2_000_000)
        self.assertTrue(data['range_available'])
        self.assertEqual(data['no_range_note'], '')
        self.assertIn('Estimated valuation range', data['unlock_includes'])
        self.assertNotIn('valuation_low', data)
        self.assertNotIn('1000000', str(data))

    def test_preview_page_renders_the_branch_and_the_disclosure_beside_the_unlock(self):
        source = (TEMPLATES / 'zelda_valuation_report.html').read_text(encoding='utf-8')
        preview = source[source.index('function renderPreview'):]
        preview = preview[:preview.index('create_valuation_purchase_checkout_session')]
        self.assertIn('data.range_available', preview)
        self.assertIn('data.no_range_note', preview)
        self.assertIn('data.range_disclosure', preview)
