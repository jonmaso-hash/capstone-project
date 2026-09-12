"""
A price quoted to a customer must come from one place.

The per-analysis prices already worked this way. The five subscription prices
did not: they were plain text in two templates -- nine literals across the
billing page and the home page -- with nothing tying "$250/mo" on screen to the
Stripe price the checkout session actually uses.

That is a billing-integrity hazard, not tidiness. It nearly bit while
configuring Stripe test prices: a proposed $99 Buyer and $499 Firm would have
been created against pages still advertising $250 and $5,000, so a customer
would have read one number and been charged another.

These tests hold the line two ways: the rendered pages must show the constants,
and neither template may reintroduce a bare price literal.
"""
import re

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from billing.pricing import (
    BUYER_PRICE_USD, FIRM_PRICE_USD, FOUNDER_PRICE_USD, INVESTOR_PRICE_USD,
    SELLER_PRICE_USD, subscription_prices,
)
from matchmaking.models import (
    Application, BuyerApplication, InvestorApplication, SellerApplication,
)
from matchmaking.tests import _mock_embedding_generation

User = get_user_model()

# Any "$<digits>/mo" written directly into a template rather than rendered from
# a constant. Matches the shape the literals had, including "$5,000/mo".
BARE_MONTHLY_PRICE = re.compile(r'\$\d[\d,]*/mo')


class PricingConstantsTests(TestCase):

    def test_context_helper_exposes_every_subscription_price(self):
        self.assertEqual(subscription_prices(), {
            'founder_price': FOUNDER_PRICE_USD,
            'investor_price': INVESTOR_PRICE_USD,
            'seller_price': SELLER_PRICE_USD,
            'buyer_price': BUYER_PRICE_USD,
            'firm_price': FIRM_PRICE_USD,
        })

    def test_the_prices_match_what_the_product_promises(self):
        """
        Pinned deliberately. Changing one of these is a pricing decision that
        must also change the matching Stripe price, which nothing here can
        enforce -- so it should at least be loud.
        """
        self.assertEqual(
            (FOUNDER_PRICE_USD, INVESTOR_PRICE_USD, SELLER_PRICE_USD,
             BUYER_PRICE_USD, FIRM_PRICE_USD),
            (99, 250, 99, 250, 5000))


class TemplatesHaveNoBarePricesTests(TestCase):
    """The other direction: a literal must not creep back in."""

    TEMPLATES = [
        'templates/billing/billing.html',
        'templates/pages/home.html',
    ]

    def test_no_template_hardcodes_a_monthly_price(self):
        import io
        for path in self.TEMPLATES:
            source = io.open(path, encoding='utf-8').read()
            found = BARE_MONTHLY_PRICE.findall(source)
            with self.subTest(template=path):
                self.assertEqual(
                    found, [],
                    '%s hardcodes %s. Render it from billing.pricing instead, or the '
                    'page and Stripe will disagree the next time a price changes.'
                    % (path, found))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RenderedPagesQuoteTheConstantsTests(TestCase):
    """Through the real pages, so a broken context variable fails loudly."""

    def setUp(self):
        _mock_embedding_generation(self)

    def test_home_page_quotes_the_constants(self):
        response = self.client.get(reverse('pages:home'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode(errors='ignore')

        self.assertIn('$%d/mo' % FOUNDER_PRICE_USD, html)
        self.assertIn('$%d/mo' % INVESTOR_PRICE_USD, html)
        self.assertIn('$%d/mo' % SELLER_PRICE_USD, html)
        self.assertIn('$%d/mo' % BUYER_PRICE_USD, html)

    def _billing_html_for(self, username, make_profile):
        """
        The billing page renders only the card matching the viewer's role, so
        each price needs a viewer who actually has that role.
        """
        user = User.objects.create_user(username, password='x')
        make_profile(user)
        user.refresh_from_db()
        self.client.force_login(user)
        response = self.client.get(reverse('billing:billing_page'))
        self.assertEqual(response.status_code, 200)
        return response.content.decode(errors='ignore')

    def test_founder_sees_the_founder_price(self):
        html = self._billing_html_for('pr_founder', lambda u: Application.objects.create(
            user=u, company_name='PriceCo', founder_name='F', email='pf@t.com',
            description='A company.', sector='SaaS', stage='Seed'))
        self.assertIn('Founder Premium', html, 'positive control: the card must render')
        self.assertIn('$%d/mo' % FOUNDER_PRICE_USD, html)

    def test_investor_sees_the_investor_and_firm_prices(self):
        html = self._billing_html_for('pr_investor', lambda u: InvestorApplication.objects.create(
            user=u, full_name='I', company_name='PriceCap', email='pi@t.com',
            investment_focus='SaaS', investment_stage='Seed'))
        self.assertIn('Investor Premium', html, 'positive control')
        self.assertIn('$%d/mo' % INVESTOR_PRICE_USD, html)
        self.assertIn('$5,000/mo', html)

    def test_seller_sees_the_seller_price(self):
        html = self._billing_html_for('pr_seller', lambda u: SellerApplication.objects.create(
            user=u, company_name='PriceSell', seller_name='S', email='ps@t.com',
            description='A business.', industry='Facilities Services'))
        self.assertIn('Seller Premium', html, 'positive control')
        self.assertIn('$%d/mo' % SELLER_PRICE_USD, html)

    def test_buyer_sees_the_buyer_price(self):
        html = self._billing_html_for('pr_buyer', lambda u: BuyerApplication.objects.create(
            user=u, full_name='B', company_name='PriceBuy', email='pb@t.com',
            acquisition_thesis='Buying things.'))
        self.assertIn('Buyer Premium', html, 'positive control')
        self.assertIn('$%d/mo' % BUYER_PRICE_USD, html)

    def test_changing_a_constant_changes_the_page(self):
        """
        The point of the refactor. Before it, the page said $250 however this
        constant was set.
        """
        import billing.pricing as pricing
        original = pricing.INVESTOR_PRICE_USD
        try:
            pricing.INVESTOR_PRICE_USD = 275
            html = self._billing_html_for('pr_investor2', lambda u: InvestorApplication.objects.create(
                user=u, full_name='I', company_name='PriceCap2', email='pi2@t.com',
                investment_focus='SaaS', investment_stage='Seed'))
            self.assertIn('$275/mo', html)
            self.assertNotIn('Investor Premium — $250/mo', html)
        finally:
            pricing.INVESTOR_PRICE_USD = original
