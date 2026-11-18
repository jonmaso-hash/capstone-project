"""
Three issues found walking production before launch (2026-11-17).

1. /billing/ told a signed-in member with no role profile that "an admin needs
   to add Stripe API keys". With no profile there is no plan and so no price
   id, which is unfinished onboarding, not a Stripe problem.
2. The founder dashboard is shown before any profile exists, but its
   Fundraising CRM button answered such a member with a bare 403.
3. The homepage's "View plans and report pricing" pointed at /billing/, which
   is sign-in only, so a visitor could not see a single price.
"""
import re
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from billing import zelda_catalog
from billing.pricing import (
    BUYER_PRICE_USD, FIRM_PRICE_USD, FOUNDER_PRICE_USD, INVESTOR_PRICE_USD, SELLER_PRICE_USD,
)
from matchmaking.models import Application, InvestorApplication
from matchmaking.tests import _mock_embedding_generation

User = get_user_model()

PAYMENTS_WARNING = "Payments aren't fully configured yet"
NEEDS_PROFILE = 'Complete your profile to see your membership plan'
CRM_MESSAGE = 'Complete your founder profile to use the Fundraising CRM.'
STRIPE_READY = dict(STRIPE_SECRET_KEY='sk_test_walkthrough', STRIPE_FOUNDER_PRICE_ID='price_founder',
                    STRIPE_INVESTOR_PRICE_ID='price_investor', STRIPE_SELLER_PRICE_ID='price_seller',
                    STRIPE_BUYER_PRICE_ID='price_buyer')


def _founder(user):
    return Application.objects.create(
        user=user, company_name='WalkCo', founder_name='F', email='walk-founder@example.com',
        description='A company.', sector='SaaS', stage='Seed')


def _investor(user):
    return InvestorApplication.objects.create(
        user=user, full_name='I', company_name='WalkCap', email='walk-investor@example.com',
        investment_focus='SaaS', investment_stage='Seed')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PublicPricingTests(TestCase):
    """Signed-out visitors can read every price; nothing on the page can charge them."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.url = reverse('billing:pricing')

    def test_homepage_pricing_link_leads_to_the_public_pricing_page(self):
        home = self.client.get(reverse('pages:home'))
        self.assertEqual(home.status_code, 200)
        link = re.search(r'<a href="([^"]+)"[^>]*>View plans and report pricing</a>', home.content.decode())
        self.assertIsNotNone(link, 'positive control: the homepage link must render')
        self.assertEqual(link.group(1), self.url)

    def test_a_signed_out_visitor_sees_every_subscription_price(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        for name, price in (('Founder Premium', FOUNDER_PRICE_USD), ('Investor Premium', INVESTOR_PRICE_USD),
                            ('Seller Premium', SELLER_PRICE_USD), ('Buyer Premium', BUYER_PRICE_USD)):
            with self.subTest(plan=name):
                self.assertIn(name, html)
                self.assertIn(f'${price}/mo', html)
        # Firm is closed to new subscriptions, so it is listed without a price
        # (billing/tests_verified_prices.py covers both states).
        self.assertIn('data-plan="firm"', html)
        self.assertNotIn(f'{FIRM_PRICE_USD:,}', html)

    def test_a_signed_out_visitor_sees_every_report_price_checkout_charges(self):
        html = self.client.get(self.url).content.decode()
        for key, (name, cents, _description) in zelda_catalog.ALL_STRIPE_PRODUCTS.items():
            with self.subTest(product=key):
                row = re.search(rf'<tr data-product="{key}">(.*?)</tr>', html, re.S)
                self.assertIsNotNone(row, f'{key} is missing from the public pricing page')
                self.assertIn(name, row.group(1))
                self.assertIn(f'${cents / 100:.2f}', row.group(1))

    def test_prices_come_from_the_definitions_not_the_template(self):
        import billing.pricing as pricing
        with mock.patch.object(pricing, 'SELLER_PRICE_USD', 123), \
                mock.patch.dict(zelda_catalog.PRODUCTS, {'valuation': ('Business valuation', 4321, 'Changed.')}):
            html = self.client.get(self.url).content.decode()
        self.assertIn('$123/mo', html)
        self.assertIn('$43.21', html)

    def test_the_page_is_read_only_and_checkout_stays_behind_sign_in(self):
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn(reverse('accounts:signup'), html, 'positive control: the sign-up call to action renders')
        main = html.split('<main', 1)[-1].split('</main>', 1)[0]
        self.assertNotIn('<form', main)
        for name in ('billing:create_checkout_session', 'billing:create_firm_checkout_session',
                     'billing:create_valuation_purchase_checkout_session', 'billing:zelda_checkout',
                     'billing:truth_delta_credit_pack_checkout'):
            with self.subTest(endpoint=name):
                self.assertNotIn(f'href="{reverse(name)}"', main)
                checkout = self.client.post(reverse(name))
                self.assertEqual(checkout.status_code, 302)
                self.assertTrue(checkout['Location'].startswith(reverse('accounts:login')))
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_the_membership_page_itself_still_requires_sign_in(self):
        response = self.client.get(reverse('billing:billing_page'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(reverse('accounts:login')))

    def test_a_signed_in_member_is_sent_to_their_membership(self):
        self.client.force_login(User.objects.create_user('walk_pricing_member', password='x'))
        html = self.client.get(self.url).content.decode()
        self.assertIn(f'href="{reverse("billing:billing_page")}"', html)
        self.assertIn(f'${FOUNDER_PRICE_USD}/mo', html)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class NoRoleProfileBillingTests(TestCase):
    """The payment warning is for Stripe configuration, not for unfinished onboarding."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('walk_no_profile', password='x')
        self.client.force_login(self.user)

    def billing(self):
        response = self.client.get(reverse('billing:billing_page'))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_no_role_profile_is_told_to_complete_their_profile(self):
        for settings in (STRIPE_READY, {**STRIPE_READY, 'STRIPE_SECRET_KEY': '', 'STRIPE_FOUNDER_PRICE_ID': ''}):
            with self.subTest(stripe_key_set=bool(settings['STRIPE_SECRET_KEY'])), override_settings(**settings):
                html = self.billing()
                self.assertIn(NEEDS_PROFILE, html)
                self.assertIn(f'href="{reverse("accounts:create_profile")}"', html)
                self.assertIn(f'href="{reverse("billing:pricing")}"', html)
                self.assertNotIn(PAYMENTS_WARNING, html)

    def test_the_warning_still_shows_when_a_plan_has_no_stripe_price(self):
        _founder(self.user)
        self.user.refresh_from_db()
        with override_settings(**{**STRIPE_READY, 'STRIPE_FOUNDER_PRICE_ID': ''}):
            html = self.billing()
        self.assertIn('Founder Premium', html, 'positive control: the founder card renders')
        self.assertIn(PAYMENTS_WARNING, html)
        self.assertNotIn(NEEDS_PROFILE, html)

    def test_the_warning_still_shows_when_the_stripe_key_is_missing(self):
        _founder(self.user)
        self.user.refresh_from_db()
        with override_settings(**{**STRIPE_READY, 'STRIPE_SECRET_KEY': ''}):
            self.assertIn(PAYMENTS_WARNING, self.billing())

    def test_a_configured_plan_shows_no_warning(self):
        _founder(self.user)
        self.user.refresh_from_db()
        with override_settings(**STRIPE_READY):
            html = self.billing()
        self.assertIn('Founder Premium', html, 'positive control')
        self.assertNotIn(PAYMENTS_WARNING, html)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FundraisingCrmWithoutProfileTests(TestCase):
    """Guide unfinished founders to setup; keep the CRM's access check for everyone else."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.crm = reverse('matchmaking:fundraising_crm')
        self.setup_url = reverse('usersettings:edit_founder_profile')

    def login(self, username):
        user = User.objects.create_user(username, password='x')
        self.client.force_login(user)
        return user

    def test_the_dashboard_crm_button_leads_a_member_with_no_profile_to_setup(self):
        self.login('walk_crm_none')
        dashboard = self.client.get(reverse('matchmaking:founder_dashboard'))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, f'href="{self.crm}"')

        response = self.client.get(self.crm, follow=True)
        self.assertEqual(response.redirect_chain, [(self.setup_url, 302)])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, CRM_MESSAGE)

    def test_guiding_creates_no_profile(self):
        user = self.login('walk_crm_nothing_saved')
        self.client.get(self.crm)
        self.assertFalse(Application.objects.filter(user=user).exists())

    def test_a_founder_with_a_profile_opens_the_crm(self):
        _founder(self.login('walk_crm_founder'))
        response = self.client.get(self.crm)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, CRM_MESSAGE)

    def test_another_role_is_still_refused(self):
        _investor(self.login('walk_crm_investor'))
        self.assertEqual(self.client.get(self.crm).status_code, 403)

    def test_a_signed_out_visitor_is_sent_to_sign_in(self):
        response = self.client.get(self.crm)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(reverse('accounts:login')))
