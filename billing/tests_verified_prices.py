"""
Quote only prices that are verified against the live Stripe catalog.

Business valuation can be bought two ways, and they are different purchases:

- The Zelda catalog "Business valuation" report (billing/zelda_catalog.py,
  $0.99). Its checkout goes through zelda_views.stripe_price, which refuses
  unless the live Stripe price is active, USD, one-time and exactly this
  amount, so the page cannot quote one number while Stripe charges another.
- The full-report unlock of a free valuation preview
  (create_valuation_purchase_checkout_session). It charges whatever
  STRIPE_VALUATION_*_PRICE_ID points at, with no such check, and those ids have
  not been verified against the live catalog. The $9.99 / $5 / $1.99 in
  zelda_api/quotas.py are therefore not quoted anywhere a customer reads;
  Stripe Checkout shows the real amount before payment.

Investor Firm's live price has not been verified either, and the code
disagreed about its interval ("/mo" on pages, "per year" in renewal_terms).
Until it is confirmed, Firm is closed to new subscriptions and no page quotes
its price. Existing firms keep their access: seats, joining, and webhook
handling are unchanged.
"""
import datetime
import io
import json
import re
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from billing import zelda_catalog
from billing.models import Subscription
from billing.pricing import FIRM_PRICE_USD
from matchmaking.models import (
    Application, BusinessEmailVerification, Firm, FirmMembership, InvestorApplication, SellerApplication,
)
from matchmaking.tests import _mock_embedding_generation

User = get_user_model()

FAKE_STRIPE = dict(
    STRIPE_SECRET_KEY='sk_test_fake', STRIPE_WEBHOOK_SECRET='whsec_fake',
    STRIPE_FOUNDER_PRICE_ID='price_founder_fake', STRIPE_INVESTOR_PRICE_ID='price_investor_fake',
    STRIPE_SELLER_PRICE_ID='price_seller_fake', STRIPE_BUYER_PRICE_ID='price_buyer_fake',
    STRIPE_FIRM_PRICE_ID='price_firm_fake',
    STRIPE_VALUATION_REPORT_PRICE_ID='price_valuation_report_fake',
    STRIPE_VALUATION_OVERAGE_PRICE_ID='price_valuation_overage_fake',
    STRIPE_VALUATION_FIRM_OVERAGE_PRICE_ID='price_valuation_firm_overage_fake',
)
# The unverified preview-unlock amounts as the copy used to print them. Bare
# '9.99' and '1.99' would collide with real catalog prices (Entity Integrity
# Report $9.99, Intelligence Memo $1.99), so match the per-report phrasing.
UNVERIFIED_UNLOCK_AMOUNTS = ('$9.99/report', '$5.00/report', '$1.99/report', 'pay-per-use', '/report after that')
FIRM_AMOUNTS = (f'{FIRM_PRICE_USD:,}', f'${FIRM_PRICE_USD}')
ZELDA_VALUATION = f"${zelda_catalog.PRODUCTS['valuation'][1] / 100:.2f}"
UNLOCK_IS_SEPARATE = 'a separate purchase; the price is shown at Stripe Checkout before you pay'


def _founder(user):
    return Application.objects.create(
        user=user, company_name='VPCo', founder_name='F', email='vp-founder@example.com',
        description='A company.', sector='SaaS', stage='Seed')


def _seller(user):
    return SellerApplication.objects.create(
        user=user, seller_name='S', company_name='VPSell', email='vp-seller@example.com',
        description='A business.')


def _investor(user, email='vp-investor@example.com'):
    return InvestorApplication.objects.create(
        user=user, full_name='I', company_name='VPCap', email=email,
        investment_focus='SaaS', investment_stage='Seed')


def _verified_investor(username, domain='vpcapital.com'):
    user = User.objects.create_user(username, email=f'{username}@example.com', password='x')
    _investor(user, email=f'{username}@example.com')
    BusinessEmailVerification.objects.create(
        user=user, business_email=f'{username}@{domain}', status='VERIFIED', verified_at=timezone.now())
    return user


class _Base(TestCase):
    def setUp(self):
        _mock_embedding_generation(self)

    def _page(self, url_name, user=None):
        if user is not None:
            self.client.force_login(user)
        response = self.client.get(reverse(url_name))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], **FAKE_STRIPE)
class ValuationPurchasePathsTests(_Base):

    def test_zelda_catalog_valuation_is_the_99_cent_price_stripe_price_enforces(self):
        self.assertEqual(zelda_catalog.PRODUCTS['valuation'][1], 99)
        self.assertEqual(ZELDA_VALUATION, '$0.99')

    def test_founder_and_seller_billing_pages_label_both_paths_and_quote_only_the_verified_one(self):
        for label, make in (('founder', _founder), ('seller', _seller)):
            with self.subTest(role=label):
                user = User.objects.create_user(f'vp_{label}', password='x')
                make(user)
                html = self._page('billing:billing_page', user)
                self.assertIn(f'Business valuation report from Zelda — {ZELDA_VALUATION}, one-time purchase', html)
                self.assertIn('Unlocking the full version of a free valuation preview', html)
                self.assertIn(UNLOCK_IS_SEPARATE, html)
                for amount in UNVERIFIED_UNLOCK_AMOUNTS:
                    self.assertNotIn(amount, html)

    def test_investor_billing_page_quotes_no_unlock_or_firm_overage_price(self):
        user = User.objects.create_user('vp_investor_val', password='x')
        _investor(user)
        html = self._page('billing:billing_page', user)
        self.assertIn('Zelda business valuation — purchased separately', html, 'positive control')
        for amount in UNVERIFIED_UNLOCK_AMOUNTS:
            self.assertNotIn(amount, html)

    def test_public_pricing_page_lists_the_zelda_report_and_labels_the_unlock_as_separate(self):
        html = self._page('billing:pricing')
        row = re.search(r'<tr data-product="valuation">(.*?)</tr>', html, re.S)
        self.assertIsNotNone(row, 'positive control: the valuation row must render')
        self.assertIn(ZELDA_VALUATION, row.group(1))
        self.assertNotIn('9.99', row.group(1))
        self.assertIn('data-note="valuation-unlock"', html)
        self.assertIn('Unlocking the full version of a free valuation', html)
        for amount in UNVERIFIED_UNLOCK_AMOUNTS:
            self.assertNotIn(amount, html)

    def test_preview_unlock_button_quotes_no_amount(self):
        source = io.open('templates/zelda_valuation_report.html', encoding='utf-8').read()
        self.assertIn('create_valuation_purchase_checkout_session', source, 'positive control')
        self.assertNotIn('unlock_price', source)
        self.assertIn('Stripe Checkout shows the price before you pay', source)

    def test_no_customer_view_hands_a_template_the_unverified_unlock_prices(self):
        for url_name, user_factory in (('pages:home', None), ('billing:billing_page', _founder)):
            with self.subTest(page=url_name):
                user = None
                if user_factory:
                    user = User.objects.create_user('vp_ctx_founder', password='x')
                    user_factory(user)
                    self.client.force_login(user)
                response = self.client.get(reverse(url_name))
                for key in ('valuation_report_price', 'valuation_overage_price', 'valuation_firm_overage_price'):
                    self.assertNotIn(key, response.context)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], **FAKE_STRIPE)
class FirmClosedToNewSubscriptionsTests(_Base):

    def test_pricing_page_lists_firm_as_unavailable_without_a_price(self):
        html = self._page('billing:pricing')
        card = re.search(r'data-plan="firm"(.*?)</div>\s*</div>', html, re.S)
        self.assertIsNotNone(card, 'positive control: the Firm card must render')
        self.assertIn('data-firm-status="closed"', html)
        self.assertIn('Unavailable for new subscriptions', card.group(1))
        for amount in FIRM_AMOUNTS:
            self.assertNotIn(amount, html)

    def test_investor_billing_page_offers_no_firm_checkout_and_no_price(self):
        user = User.objects.create_user('vp_firm_view', password='x')
        _investor(user)
        html = self._page('billing:billing_page', user)
        self.assertIn('Investing as a firm?', html, 'positive control')
        self.assertIn('data-firm-status="closed"', html)
        self.assertNotIn(reverse('billing:create_firm_checkout_session'), html)
        self.assertIn(reverse('billing:join_firm'), html, 'existing firms can still add teammates')
        for amount in FIRM_AMOUNTS:
            self.assertNotIn(amount, html)

    @mock.patch('billing.views.stripe.checkout.Session.create')
    def test_firm_checkout_refuses_before_reaching_stripe(self, mock_create):
        user = _verified_investor('vp_firm_owner')
        self.client.force_login(user)
        response = self.client.post(reverse('billing:create_firm_checkout_session'),
                                    {'firm_name': 'VP Capital'}, follow=True)
        self.assertRedirects(response, reverse('billing:billing_page'))
        self.assertContains(response, "Investor Firm isn&#x27;t open to new subscriptions right now.")
        mock_create.assert_not_called()
        self.assertFalse(Firm.objects.exists())

    def test_existing_teammates_can_still_join_their_firm(self):
        owner = _verified_investor('vp_join_owner')
        firm = Firm.objects.create(name='VP Capital', verified_domain='vpcapital.com', owner=owner)
        FirmMembership.objects.create(firm=firm, user=owner)
        joiner = _verified_investor('vp_join_mate')
        self.client.force_login(joiner)
        self.client.post(reverse('billing:join_firm'))
        self.assertTrue(FirmMembership.objects.filter(firm=firm, user=joiner).exists())
        joiner.match_investor_profile.refresh_from_db()
        self.assertTrue(joiner.match_investor_profile.is_premium)

    def _firm(self, owner_username):
        owner = _verified_investor(owner_username)
        firm = Firm.objects.create(name='VP Capital', verified_domain='vpcapital.com', owner=owner)
        FirmMembership.objects.create(firm=firm, user=owner)
        return owner, firm

    def test_a_firm_seat_still_sees_their_firm(self):
        _owner, firm = self._firm('vp_seat_owner')
        seat = _verified_investor('vp_seat_member')
        FirmMembership.objects.create(firm=firm, user=seat)
        html = self._page('billing:billing_page', seat)
        self.assertIn("You're part of <strong>VP Capital</strong>", html)
        self.assertNotIn('data-firm-status="closed"', html, 'members are not told their plan is unavailable')
        for amount in FIRM_AMOUNTS:
            self.assertNotIn(amount, html)

    def test_an_active_firm_subscription_keeps_its_management_without_quoting_an_amount(self):
        owner, _firm = self._firm('vp_member_owner')
        Subscription.objects.create(
            user=owner, plan=Subscription.Plan.INVESTOR_FIRM, stripe_customer_id='cus_vp',
            stripe_subscription_id='sub_vp', status=Subscription.Status.ACTIVE,
            current_period_end=timezone.now() + datetime.timedelta(days=30))
        html = self._page('billing:billing_page', owner)
        self.assertIn('Investor Firm', html)
        self.assertIn(reverse('billing:create_billing_portal_session'), html)
        self.assertIn(reverse('billing:cancel_subscription'), html)
        renewal = re.search(r'Renews automatically[^<]*', html)
        self.assertIsNotNone(renewal, 'positive control: the renewal line must render')
        self.assertNotIn('$', renewal.group(0))
        self.assertNotIn('per month', renewal.group(0))
        for amount in FIRM_AMOUNTS:
            self.assertNotIn(amount, html)

    def test_an_in_flight_firm_checkout_still_creates_the_firm(self):
        """A session started before Firm closed must still be honoured when Stripe confirms it."""
        user = _verified_investor('vp_webhook_owner')
        event = {'type': 'checkout.session.completed', 'data': {'object': {
            'metadata': {'user_id': str(user.id), 'plan': Subscription.Plan.INVESTOR_FIRM,
                         'firm_name': 'VP Capital', 'firm_domain': 'vpcapital.com'},
            'customer': 'cus_vp_wh', 'subscription': 'sub_vp_wh'}}}
        with mock.patch('billing.views.stripe.Webhook.construct_event', return_value=event):
            response = self.client.post(reverse('billing:stripe_webhook'), data=json.dumps(event),
                                        content_type='application/json', HTTP_STRIPE_SIGNATURE='sig')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(FirmMembership.objects.filter(firm__verified_domain='vpcapital.com', user=user).exists())

    def test_firm_subscription_email_states_no_unconfirmed_amount_or_interval(self):
        from billing.emails import send_subscription_started_email
        user = User.objects.create_user('vp_firm_mail', email='vp-firm-mail@example.com', password='x')
        subscription = Subscription.objects.create(
            user=user, plan=Subscription.Plan.INVESTOR_FIRM, stripe_customer_id='cus_m',
            stripe_subscription_id='sub_m', status=Subscription.Status.ACTIVE,
            current_period_end=timezone.now() + datetime.timedelta(days=30))
        mail.outbox.clear()
        send_subscription_started_email(subscription)
        body = mail.outbox[0].body
        self.assertIn('renews automatically until you cancel', body)
        self.assertNotIn('5000', body)
        self.assertNotIn('per month', body)


@mock.patch('billing.pricing.FIRM_OPEN_FOR_NEW_SUBSCRIPTIONS', True)
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], **FAKE_STRIPE)
class FirmReopenedTests(_Base):
    """Positive control: one flag restores the price and checkout once confirmed."""

    def test_pricing_and_billing_quote_firm_and_offer_checkout_again(self):
        self.assertIn(f'${FIRM_PRICE_USD:,}/mo', self._page('billing:pricing'))
        user = User.objects.create_user('vp_firm_open', password='x')
        _investor(user)
        html = self._page('billing:billing_page', user)
        self.assertIn(f'${FIRM_PRICE_USD:,}/mo', html)
        self.assertIn(reverse('billing:create_firm_checkout_session'), html)

    @mock.patch('billing.views.stripe.checkout.Session.create')
    def test_firm_checkout_reaches_stripe_again(self, mock_create):
        mock_create.return_value = mock.Mock(url='https://checkout.stripe.com/fake-firm')
        user = _verified_investor('vp_firm_open_owner')
        self.client.force_login(user)
        self.client.post(reverse('billing:create_firm_checkout_session'), {'firm_name': 'VP Capital'})
        mock_create.assert_called_once()
