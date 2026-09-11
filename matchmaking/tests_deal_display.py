"""
An unstated asking price must never render as $0.

`SellerApplication.asking_price` is a non-null DecimalField defaulting to 0, so
a seller who has not priced the business is stored identically to one asking
zero. `deal_size_signal` already draws the distinction correctly and abstains.

Four templates did not, and printed `Asking: $0` -- absence presented to a buyer
as a stated price of zero. Found by walking the buyer dashboard in a browser;
no test saw it, because every test asserted on the model value rather than on
what the page says.

These tests pin the display contract, and the last one asserts on the rendered
page so a template that stops using the filter fails loudly.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .models import BuyerApplication, SellerApplication
from .templatetags.deal_display import UNSTATED_LABEL, asking_price_display
from .tests import _mock_embedding_generation

User = get_user_model()


class AskingPriceDisplayTests(TestCase):
    """The filter itself."""

    def test_a_stated_price_is_formatted_as_money(self):
        self.assertEqual(asking_price_display(4200000), '$4,200,000')

    def test_zero_is_not_a_price(self):
        self.assertEqual(asking_price_display(0), UNSTATED_LABEL)

    def test_none_is_not_a_price(self):
        self.assertEqual(asking_price_display(None), UNSTATED_LABEL)

    def test_decimals_round_to_whole_dollars(self):
        from decimal import Decimal
        self.assertEqual(asking_price_display(Decimal('4200000.49')), '$4,200,000')

    def test_garbage_degrades_to_unstated_rather_than_raising(self):
        self.assertEqual(asking_price_display('not a number'), UNSTATED_LABEL)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class BuyerDashboardDoesNotShowZeroTests(TestCase):
    """
    The page the defect was found on, rendered for real.

    A buyer with a seller in range whose price is unstated must not be shown a
    business that appears to be free.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        buyer_user = User.objects.create_user('dd_buyer', password='x')
        BuyerApplication.objects.create(
            user=buyer_user, full_name='B', company_name='BuyCo', email='b@t.com',
            acquisition_thesis='Buying things.', budget_min=1000000, budget_max=9000000)

        seller_user = User.objects.create_user('dd_seller', password='x')
        self.seller = SellerApplication.objects.create(
            user=seller_user, company_name='Unpriced Co', seller_name='S',
            email='s@t.com', description='A business with no price yet.',
            industry='Facilities Services', asking_price=0)

        self.client.force_login(buyer_user)

    def _dashboard_html(self):
        response = self.client.get('/matchmaking/dashboard/buyer/')
        self.assertEqual(response.status_code, 200)
        return response.content.decode(errors='ignore')

    def test_an_unpriced_seller_never_renders_as_zero_dollars(self):
        html = self._dashboard_html()
        self.assertIn('Unpriced Co', html,
                      'positive control: the seller must actually be on the page')
        self.assertNotIn('Asking: $0', html)
        self.assertIn(UNSTATED_LABEL, html)

    def test_a_priced_seller_still_shows_its_price(self):
        self.seller.asking_price = 4200000
        self.seller.save(update_fields=['asking_price'])

        html = self._dashboard_html()
        self.assertIn('Unpriced Co', html, 'positive control')
        self.assertIn('$4,200,000', html)
