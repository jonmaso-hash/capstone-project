"""
The valuation report says what it is not, where a reader will see it.

"Not an appraisal, an audit, or a price" already existed -- inside a
`data-bs-content` attribute on an info icon, shown only if someone clicks it.
An existing assertion covered that (zelda_api/tests.py), but it searched the
whole document, so an attribute satisfied it. A disclaimer nobody opens is
disclosed in the same sense a value buried in json_script is rendered: present
in the markup, absent from the reader.

That distinction matters more here than on most surfaces. A valuation report
puts a dollar range on someone's business, and a range presented without
qualification reads as a number they can take to a negotiation or a lender.
The popover keeps the long explanation; the line that constrains what the
number MEANS has to be on the page.

Both halves are asserted:

    the phrase survives with popover attributes stripped -- i.e. it is body
    text, not a tooltip

    the popover itself still carries the fuller explanation, so making the
    line inline did not just move text around and lose the detail
"""
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .vector_models import BusinessValuationReport, DocumentSource

User = get_user_model()

NOT_AN_APPRAISAL = 'not an appraisal, an audit, or a price'

# Everything a reader only sees after clicking. Stripping these is what
# separates "on the page" from "hidden behind an info icon".
POPOVER_ATTRS = re.compile(r'data-bs-content="[^"]*"', re.IGNORECASE)


class TheValuationSaysWhatItIsNotTests(TestCase):

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        from matchmaking.models import InvestorApplication

        self.user = User.objects.create_user('val_owner', password='x')
        InvestorApplication.objects.create(user=self.user, is_premium=True)
        self.client.force_login(self.user)

        self.document = DocumentSource.objects.create(
            filename='v.pptx', source_entity='Northwind Grid', uploaded_by=self.user,
            document_type='business_valuation', status='analyzed', valuation_tier='full')
        BusinessValuationReport.objects.create(
            document=self.document, confidence_score=0.6,
            valuation_low=1_000_000, valuation_high=2_000_000,
            valuation_summary='x', financial_summary='x', risk_report='x')

    def page(self):
        response = self.client.get(
            reverse('zelda_api:valuation_report', args=[self.document.id]))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_the_report_renders_at_all(self):
        """Positive control: every assertion below reads this page."""
        self.assertIn('Business Valuation Report', self.page())

    def test_the_qualification_is_on_the_page_not_only_in_a_tooltip(self):
        readable = POPOVER_ATTRS.sub('', self.page())
        self.assertIn(
            NOT_AN_APPRAISAL, readable,
            'the only statement that this is not an appraisal is inside a popover, '
            'so a reader who never clicks the info icon sees an unqualified '
            'dollar range')

    def test_the_popover_still_carries_the_longer_explanation(self):
        """
        Paired with the above. Moving the phrase inline must not gut the
        popover: the long version explains what the range is FOR (planning and
        negotiation) and how it was produced, which the short inline line does
        not.
        """
        html = self.page()
        popovers = ' '.join(POPOVER_ATTRS.findall(html))
        self.assertIn('model estimate', popovers,
                      'the popover lost its explanation of what the range is')

    def test_the_qualification_sits_with_the_number(self):
        """
        Placement, not just presence. A disclaimer in a page footer, far below
        the range it qualifies, is read by almost nobody. It has to appear
        before the valuation figures in the document.
        """
        readable = POPOVER_ATTRS.sub('', self.page())
        qualification = readable.find(NOT_AN_APPRAISAL)
        figures = readable.find('valuation-loading')
        self.assertNotEqual(qualification, -1, 'the qualification is not on the page')
        self.assertNotEqual(figures, -1, 'the report body was not found')
        self.assertLess(qualification, figures,
                        'the qualification appears after the valuation body')
