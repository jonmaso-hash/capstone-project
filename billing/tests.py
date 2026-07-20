"""
Coverage for the Stripe subscription lifecycle: checkout session creation
picks the right price per role, and the webhook handler is the only thing
that flips is_premium (mirrors real Stripe behavior — entitlement changes
only on confirmed webhook events, never on the client-side redirect alone).
"""
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from matchmaking.models import Application, InvestorApplication, SellerApplication, BuyerApplication
from matchmaking.tests import _mock_embedding_generation
from .models import Subscription

User = get_user_model()

FAKE_STRIPE_SETTINGS = dict(
    STRIPE_SECRET_KEY='sk_test_fake',
    STRIPE_PUBLISHABLE_KEY='pk_test_fake',
    STRIPE_WEBHOOK_SECRET='whsec_fake',
    STRIPE_FOUNDER_PRICE_ID='price_founder_fake',
    STRIPE_INVESTOR_PRICE_ID='price_investor_fake',
    STRIPE_SELLER_PRICE_ID='price_seller_fake',
    STRIPE_BUYER_PRICE_ID='price_buyer_fake',
    STRIPE_FIRM_PRICE_ID='price_firm_fake',
    STRIPE_VALUATION_REPORT_PRICE_ID='price_valuation_report_fake',
    STRIPE_VALUATION_OVERAGE_PRICE_ID='price_valuation_overage_fake',
    STRIPE_VALUATION_FIRM_OVERAGE_PRICE_ID='price_valuation_firm_overage_fake',
)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], **FAKE_STRIPE_SETTINGS)
class CheckoutSessionTests(TestCase):
    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('founder_billing', password='x')
        Application.objects.create(
            user=self.founder_user, founder_name='F', email='f@t.com',
            company_name='FCo', sector='SaaS', stage='Seed', description='test', is_private=False,
        )
        self.investor_user = User.objects.create_user('investor_billing', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', email='i@t.com',
            company_name='ICo', investment_focus='SaaS', investment_stage='Seed', is_private=False,
        )
        self.seller_user = User.objects.create_user('seller_billing', password='x')
        SellerApplication.objects.create(
            user=self.seller_user, seller_name='S', email='s@t.com',
            company_name='SCo', description='test business',
        )
        self.buyer_user = User.objects.create_user('buyer_billing', password='x')
        BuyerApplication.objects.create(
            user=self.buyer_user, full_name='B', email='b@t.com',
            company_name='BCo', acquisition_thesis='test thesis',
        )

    @mock.patch('billing.views.stripe.checkout.Session.create')
    def test_founder_checkout_uses_founder_price(self, mock_create):
        mock_create.return_value = mock.Mock(url='https://checkout.stripe.com/fake-founder')
        self.client.force_login(self.founder_user)

        response = self.client.post(reverse('billing:create_checkout_session'))

        self.assertRedirects(response, 'https://checkout.stripe.com/fake-founder', fetch_redirect_response=False)
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs['line_items'][0]['price'], 'price_founder_fake')
        self.assertEqual(kwargs['metadata']['plan'], Subscription.Plan.FOUNDER_PREMIUM)

    @mock.patch('billing.views.stripe.checkout.Session.create')
    def test_investor_checkout_uses_investor_price(self, mock_create):
        mock_create.return_value = mock.Mock(url='https://checkout.stripe.com/fake-investor')
        self.client.force_login(self.investor_user)

        response = self.client.post(reverse('billing:create_checkout_session'))

        self.assertRedirects(response, 'https://checkout.stripe.com/fake-investor', fetch_redirect_response=False)
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs['line_items'][0]['price'], 'price_investor_fake')
        self.assertEqual(kwargs['metadata']['plan'], Subscription.Plan.INVESTOR_PREMIUM)

    @mock.patch('billing.views.stripe.checkout.Session.create')
    def test_seller_checkout_uses_seller_price(self, mock_create):
        mock_create.return_value = mock.Mock(url='https://checkout.stripe.com/fake-seller')
        self.client.force_login(self.seller_user)

        response = self.client.post(reverse('billing:create_checkout_session'))

        self.assertRedirects(response, 'https://checkout.stripe.com/fake-seller', fetch_redirect_response=False)
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs['line_items'][0]['price'], 'price_seller_fake')
        self.assertEqual(kwargs['metadata']['plan'], Subscription.Plan.SELLER_PREMIUM)

    @mock.patch('billing.views.stripe.checkout.Session.create')
    def test_buyer_checkout_uses_buyer_price(self, mock_create):
        mock_create.return_value = mock.Mock(url='https://checkout.stripe.com/fake-buyer')
        self.client.force_login(self.buyer_user)

        response = self.client.post(reverse('billing:create_checkout_session'))

        self.assertRedirects(response, 'https://checkout.stripe.com/fake-buyer', fetch_redirect_response=False)
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs['line_items'][0]['price'], 'price_buyer_fake')
        self.assertEqual(kwargs['metadata']['plan'], Subscription.Plan.BUYER_PREMIUM)

    def test_checkout_blocked_without_a_role_profile(self):
        bare_user = User.objects.create_user('no_role_user', password='x')
        self.client.force_login(bare_user)

        response = self.client.post(reverse('billing:create_checkout_session'), follow=True)

        self.assertContains(response, "Complete your founder, investor, seller, or buyer profile")
        self.assertEqual(Subscription.objects.count(), 0)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], **FAKE_STRIPE_SETTINGS)
class WebhookLifecycleTests(TestCase):
    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('webhook_founder', password='x')
        self.founder_app = Application.objects.create(
            user=self.founder_user, founder_name='F', email='f@t.com',
            company_name='FCo', sector='SaaS', stage='Seed', description='test', is_private=False,
        )

    def _post_webhook(self, event_type, data_object):
        fake_event = {'type': event_type, 'data': {'object': data_object}}
        with mock.patch('billing.views.stripe.Webhook.construct_event', return_value=fake_event):
            return self.client.post(
                reverse('billing:stripe_webhook'),
                data=json.dumps(fake_event),
                content_type='application/json',
                HTTP_STRIPE_SIGNATURE='fake-signature',
            )

    def test_checkout_completed_activates_premium(self):
        self.assertFalse(self.founder_app.is_premium)

        response = self._post_webhook('checkout.session.completed', {
            'metadata': {'user_id': str(self.founder_user.id), 'plan': Subscription.Plan.FOUNDER_PREMIUM},
            'customer': 'cus_fake123',
            'subscription': 'sub_fake123',
        })

        self.assertEqual(response.status_code, 200)
        self.founder_app.refresh_from_db()
        self.assertTrue(self.founder_app.is_premium)

        sub = Subscription.objects.get(stripe_subscription_id='sub_fake123')
        self.assertEqual(sub.user, self.founder_user)
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)

    def test_subscription_deleted_deactivates_premium(self):
        self._post_webhook('checkout.session.completed', {
            'metadata': {'user_id': str(self.founder_user.id), 'plan': Subscription.Plan.FOUNDER_PREMIUM},
            'customer': 'cus_fake456',
            'subscription': 'sub_fake456',
        })
        self.founder_app.refresh_from_db()
        self.assertTrue(self.founder_app.is_premium)

        response = self._post_webhook('customer.subscription.deleted', {'id': 'sub_fake456'})

        self.assertEqual(response.status_code, 200)
        self.founder_app.refresh_from_db()
        self.assertFalse(self.founder_app.is_premium)
        sub = Subscription.objects.get(stripe_subscription_id='sub_fake456')
        self.assertEqual(sub.status, Subscription.Status.CANCELED)

    def test_invalid_signature_rejected(self):
        with mock.patch('billing.views.stripe.Webhook.construct_event', side_effect=ValueError('bad payload')):
            response = self.client.post(
                reverse('billing:stripe_webhook'),
                data=json.dumps({'type': 'checkout.session.completed'}),
                content_type='application/json',
                HTTP_STRIPE_SIGNATURE='garbage',
            )
        self.assertEqual(response.status_code, 400)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], **FAKE_STRIPE_SETTINGS)
class BillingPageCopyTests(TestCase):
    """
    The membership page's AI-analyses bullet is sourced from
    zelda_api.quotas' real constants rather than a hardcoded number, so it
    can never drift out of sync the way the funnel metric and intro-email
    copy did earlier this session — this locks that wiring in.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('copy_founder', password='x')
        Application.objects.create(
            user=self.founder_user, founder_name='F', email='f@t.com',
            company_name='FCo', sector='SaaS', stage='Seed', description='test', is_private=False,
        )

    def test_billing_page_shows_real_ai_credit_numbers(self):
        from zelda_api.quotas import FREE_CREDITS, PREMIUM_CREDITS

        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('billing:billing_page'))

        self.assertContains(response, f"{PREMIUM_CREDITS} monthly AI analyses")
        self.assertContains(response, f"free tier: {FREE_CREDITS}/month")

    def test_billing_page_shows_real_crm_lead_limit(self):
        from matchmaking.views import FREE_CRM_LEAD_LIMIT

        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('billing:billing_page'))

        self.assertContains(response, f"free tier is capped at {FREE_CRM_LEAD_LIMIT}")

    def test_founder_premium_shows_new_price_and_highlight_perk(self):
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('billing:billing_page'))

        self.assertContains(response, "Founder Premium — $99/mo")
        self.assertContains(response, "Monthly Highlight")
        # Replaced by the highlight perk — see digest.py's asymmetric identity design.
        self.assertNotContains(response, "See the investor's full identity")

    def test_investor_premium_shows_new_price_and_keeps_identity_reveal(self):
        investor_user = User.objects.create_user('copy_investor', password='x')
        InvestorApplication.objects.create(
            user=investor_user, full_name='I', email='i@t.com', company_name='ICo',
            investment_focus='SaaS', investment_stage='Seed', is_private=False,
        )
        self.client.force_login(investor_user)
        response = self.client.get(reverse('billing:billing_page'))

        self.assertContains(response, "Investor Premium — $250/mo")
        self.assertContains(response, "See the founder's full identity")

    def test_seller_premium_shows_new_price_and_highlight_perk(self):
        seller_user = User.objects.create_user('copy_seller', password='x')
        SellerApplication.objects.create(
            user=seller_user, seller_name='S', email='s@t.com', company_name='SCo', description='test business',
        )
        self.client.force_login(seller_user)
        response = self.client.get(reverse('billing:billing_page'))

        self.assertContains(response, "Seller Premium — $99/mo")
        self.assertContains(response, "Monthly Highlight")

    def test_buyer_premium_shows_new_price(self):
        buyer_user = User.objects.create_user('copy_buyer', password='x')
        BuyerApplication.objects.create(
            user=buyer_user, full_name='B', email='b@t.com', company_name='BCo', acquisition_thesis='test thesis',
        )
        self.client.force_login(buyer_user)
        response = self.client.get(reverse('billing:billing_page'))

        self.assertContains(response, "Buyer Premium — $250/mo")

    def test_founder_premium_shows_pay_per_use_valuation_price(self):
        from zelda_api.quotas import VALUATION_REPORT_PRICE_USD

        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('billing:billing_page'))

        self.assertContains(
            response,
            f"${VALUATION_REPORT_PRICE_USD:.2f}/report, pay-per-use (not included in your subscription)",
        )

    def test_seller_premium_shows_pay_per_use_valuation_price(self):
        from zelda_api.quotas import VALUATION_REPORT_PRICE_USD

        seller_user = User.objects.create_user('copy_seller_val', password='x')
        SellerApplication.objects.create(
            user=seller_user, seller_name='S', email='sv@t.com', company_name='SVCo', description='test business',
        )
        self.client.force_login(seller_user)
        response = self.client.get(reverse('billing:billing_page'))

        self.assertContains(
            response,
            f"${VALUATION_REPORT_PRICE_USD:.2f}/report, pay-per-use (not included in your subscription)",
        )

    def test_investor_premium_shows_included_valuation_allowance(self):
        from zelda_api.quotas import VALUATION_INVESTOR_BUYER_MONTHLY_LIMIT, VALUATION_OVERAGE_PRICE_USD

        investor_user = User.objects.create_user('copy_investor_val', password='x')
        InvestorApplication.objects.create(
            user=investor_user, full_name='I', email='iv@t.com', company_name='ICoV',
            investment_focus='SaaS', investment_stage='Seed', is_private=False,
        )
        self.client.force_login(investor_user)
        response = self.client.get(reverse('billing:billing_page'))

        self.assertContains(
            response,
            f"{VALUATION_INVESTOR_BUYER_MONTHLY_LIMIT} included every month "
            f"(${VALUATION_OVERAGE_PRICE_USD:.2f}/report after that)",
        )

    def test_buyer_premium_shows_included_valuation_allowance(self):
        from zelda_api.quotas import VALUATION_INVESTOR_BUYER_MONTHLY_LIMIT, VALUATION_OVERAGE_PRICE_USD

        buyer_user = User.objects.create_user('copy_buyer_val', password='x')
        BuyerApplication.objects.create(
            user=buyer_user, full_name='B', email='bv@t.com', company_name='BCoV', acquisition_thesis='test thesis',
        )
        self.client.force_login(buyer_user)
        response = self.client.get(reverse('billing:billing_page'))

        self.assertContains(
            response,
            f"{VALUATION_INVESTOR_BUYER_MONTHLY_LIMIT} included every month "
            f"(${VALUATION_OVERAGE_PRICE_USD:.2f}/report after that)",
        )

    def test_firm_section_shows_included_valuation_allowance(self):
        from zelda_api.quotas import VALUATION_FIRM_MONTHLY_LIMIT, VALUATION_FIRM_OVERAGE_PRICE_USD

        investor_user = User.objects.create_user('copy_investor_firm_val', password='x')
        InvestorApplication.objects.create(
            user=investor_user, full_name='I', email='ifv@t.com', company_name='ICoFV',
            investment_focus='SaaS', investment_stage='Seed', is_private=False,
        )
        self.client.force_login(investor_user)
        response = self.client.get(reverse('billing:billing_page'))

        self.assertContains(response, f"plus {VALUATION_FIRM_MONTHLY_LIMIT} business")
        self.assertContains(response, f"valuations per seat per month (${VALUATION_FIRM_OVERAGE_PRICE_USD:.2f}/report after that)")


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], **FAKE_STRIPE_SETTINGS)
class FirmTierTests(TestCase):
    """
    The $5,000/mo Firm plan (matchmaking.models.Firm/FirmMembership) — one
    subscription covering up to 100 verified-domain investor seats, gated
    on the same self-serve business-email verification individual users
    already go through (not a separate approval flow).
    """

    def setUp(self):
        _mock_embedding_generation(self)

    def _verified_investor(self, username, domain='acmecapital.com'):
        from matchmaking.models import BusinessEmailVerification
        user = User.objects.create_user(username, password='x')
        InvestorApplication.objects.create(
            user=user, full_name='I', email=f'{username}@t.com', company_name='Acme Capital',
            investment_focus='SaaS', investment_stage='Seed',
        )
        BusinessEmailVerification.objects.create(
            user=user, business_email=f'{username}@{domain}', status='VERIFIED', verified_at=None,
        )
        return user

    def test_checkout_blocked_without_verified_business_email(self):
        user = User.objects.create_user('firm_noverify', password='x')
        InvestorApplication.objects.create(
            user=user, full_name='I', email='i@t.com', company_name='ICo',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse('billing:create_firm_checkout_session'), {'firm_name': 'Acme Capital'}, follow=True,
        )
        self.assertContains(response, "Verify your business email")

    @mock.patch('billing.views.stripe.checkout.Session.create')
    def test_checkout_uses_firm_price_and_metadata(self, mock_create):
        mock_create.return_value = mock.Mock(url='https://checkout.stripe.com/fake-firm')
        user = self._verified_investor('firm_owner')
        self.client.force_login(user)

        response = self.client.post(
            reverse('billing:create_firm_checkout_session'), {'firm_name': 'Acme Capital'},
        )
        self.assertRedirects(response, 'https://checkout.stripe.com/fake-firm', fetch_redirect_response=False)
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs['line_items'][0]['price'], 'price_firm_fake')
        self.assertEqual(kwargs['metadata']['plan'], Subscription.Plan.INVESTOR_FIRM)
        self.assertEqual(kwargs['metadata']['firm_domain'], 'acmecapital.com')

    def test_webhook_creates_firm_and_first_membership(self):
        from matchmaking.models import Firm, FirmMembership
        user = self._verified_investor('firm_webhook_owner')

        fake_event = {
            'type': 'checkout.session.completed',
            'data': {'object': {
                'metadata': {
                    'user_id': str(user.id), 'plan': Subscription.Plan.INVESTOR_FIRM,
                    'firm_name': 'Acme Capital', 'firm_domain': 'acmecapital.com',
                },
                'customer': 'cus_firm_fake', 'subscription': 'sub_firm_fake',
            }},
        }
        with mock.patch('billing.views.stripe.Webhook.construct_event', return_value=fake_event):
            response = self.client.post(
                reverse('billing:stripe_webhook'), data=json.dumps(fake_event),
                content_type='application/json', HTTP_STRIPE_SIGNATURE='fake-signature',
            )
        self.assertEqual(response.status_code, 200)

        firm = Firm.objects.get(verified_domain='acmecapital.com')
        self.assertEqual(firm.owner, user)
        self.assertEqual(firm.name, 'Acme Capital')
        self.assertTrue(FirmMembership.objects.filter(firm=firm, user=user).exists())

        user.match_investor_profile.refresh_from_db()
        self.assertTrue(user.match_investor_profile.is_premium)

    def test_second_owner_cannot_create_firm_for_same_domain(self):
        from matchmaking.models import Firm
        Firm.objects.create(name='Acme Capital', verified_domain='acmecapital.com', owner=self._verified_investor('firm_first'))
        second_user = self._verified_investor('firm_second')
        self.client.force_login(second_user)

        response = self.client.post(
            reverse('billing:create_firm_checkout_session'), {'firm_name': 'Acme Capital 2'}, follow=True,
        )
        self.assertContains(response, "ask its admin to add you as a seat instead")

    def test_join_firm_adds_seat_and_grants_premium(self):
        from matchmaking.models import Firm, FirmMembership
        owner = self._verified_investor('firm_join_owner')
        firm = Firm.objects.create(name='Acme Capital', verified_domain='acmecapital.com', owner=owner)
        FirmMembership.objects.create(firm=firm, user=owner)

        joiner = self._verified_investor('firm_join_teammate')
        self.client.force_login(joiner)

        response = self.client.post(reverse('billing:join_firm'), follow=True)
        self.assertContains(response, "joined")
        self.assertContains(response, "Acme Capital")
        self.assertTrue(FirmMembership.objects.filter(firm=firm, user=joiner).exists())
        joiner.match_investor_profile.refresh_from_db()
        self.assertTrue(joiner.match_investor_profile.is_premium)

    def test_join_firm_blocked_without_matching_domain(self):
        from matchmaking.models import Firm
        Firm.objects.create(name='Acme Capital', verified_domain='acmecapital.com', owner=self._verified_investor('firm_domain_owner'))
        stranger = self._verified_investor('firm_stranger', domain='othercompany.com')
        self.client.force_login(stranger)

        response = self.client.post(reverse('billing:join_firm'), follow=True)
        self.assertContains(response, "No firm found for your email domain")

    def test_join_firm_blocked_at_seat_cap(self):
        from matchmaking.models import Firm, FirmMembership
        owner = self._verified_investor('firm_cap_owner')
        firm = Firm.objects.create(name='Acme Capital', verified_domain='acmecapital.com', owner=owner)
        FirmMembership.objects.create(firm=firm, user=owner)

        with mock.patch('matchmaking.models.Firm.MAX_SEATS', 1):
            latecomer = self._verified_investor('firm_cap_latecomer')
            self.client.force_login(latecomer)
            response = self.client.post(reverse('billing:join_firm'), follow=True)
            self.assertContains(response, "reached its 1-seat limit")

    def test_billing_page_shows_firm_membership_status(self):
        from matchmaking.models import Firm, FirmMembership
        owner = self._verified_investor('firm_status_owner')
        firm = Firm.objects.create(name='Acme Capital', verified_domain='acmecapital.com', owner=owner)
        FirmMembership.objects.create(firm=firm, user=owner)
        self.client.force_login(owner)

        response = self.client.get(reverse('billing:billing_page'))
        self.assertContains(response, "You're part of")
        self.assertContains(response, "Acme Capital")

    def test_firm_seat_gets_higher_weekly_ai_cap(self):
        from matchmaking.models import Firm, FirmMembership
        from zelda_api.quotas import weekly_credit_limit
        owner = self._verified_investor('firm_quota_owner')
        firm = Firm.objects.create(name='Acme Capital', verified_domain='acmecapital.com', owner=owner)
        FirmMembership.objects.create(firm=firm, user=owner)
        owner.match_investor_profile.is_premium = True
        owner.match_investor_profile.save(update_fields=['is_premium'])

        self.assertEqual(weekly_credit_limit(owner), 70)  # ceil(100 * 0.7), vs 40 for an individual Premium seat


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], **FAKE_STRIPE_SETTINGS)
class ValuationPurchaseCheckoutTests(TestCase):
    """
    One-time (mode='payment') Stripe Checkout that unlocks ONE specific
    preview-tier business valuation report into 'full' — a genuinely
    different Stripe primitive from every other checkout in this app (all
    of which are mode='subscription'). Covers all three unlock prices
    (Founder/Seller's flat $9.99, Investor/Buyer's $5, Firm's $1.99) and
    confirms the webhook only unlocks the specific document named in
    checkout metadata, not "the next generation."
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('valuation_purchase_user', password='x')

    def _preview_doc(self, user, source_entity='FounderCo'):
        from zelda_api.vector_models import DocumentSource
        return DocumentSource.objects.create(
            filename='deck.txt', source_entity=source_entity, uploaded_by=user,
            document_type='business_valuation', status='analyzed', valuation_tier='preview',
        )

    @mock.patch('billing.views.stripe.checkout.Session.create')
    def test_founder_checkout_uses_flat_report_price_and_payment_mode(self, mock_create):
        from matchmaking.models import Application
        Application.objects.create(user=self.user, company_name='FounderCo')
        doc = self._preview_doc(self.user)
        mock_create.return_value = mock.Mock(url='https://checkout.stripe.com/fake-valuation-report')
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('billing:create_valuation_purchase_checkout_session'), {'document_id': doc.id},
        )

        self.assertRedirects(response, 'https://checkout.stripe.com/fake-valuation-report', fetch_redirect_response=False)
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs['mode'], 'payment')
        self.assertEqual(kwargs['line_items'][0]['price'], 'price_valuation_report_fake')
        self.assertEqual(kwargs['metadata']['purpose'], 'valuation_purchase')
        self.assertEqual(kwargs['metadata']['purchase_type'], 'report')
        self.assertEqual(kwargs['metadata']['document_id'], str(doc.id))

    @mock.patch('billing.views.stripe.checkout.Session.create')
    def test_investor_checkout_uses_overage_price(self, mock_create):
        from matchmaking.models import InvestorApplication
        InvestorApplication.objects.create(user=self.user, is_premium=False)
        doc = self._preview_doc(self.user, source_entity='ValCo')
        mock_create.return_value = mock.Mock(url='https://checkout.stripe.com/fake-overage')
        self.client.force_login(self.user)

        self.client.post(reverse('billing:create_valuation_purchase_checkout_session'), {'document_id': doc.id})

        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs['line_items'][0]['price'], 'price_valuation_overage_fake')

    @mock.patch('billing.views.stripe.checkout.Session.create')
    def test_firm_member_checkout_uses_firm_overage_price(self, mock_create):
        from matchmaking.models import Firm, FirmMembership, InvestorApplication
        InvestorApplication.objects.create(user=self.user, is_premium=True)
        firm = Firm.objects.create(name='Acme Capital', verified_domain='acme.com', owner=self.user)
        FirmMembership.objects.create(firm=firm, user=self.user)
        doc = self._preview_doc(self.user, source_entity='ValCo')
        mock_create.return_value = mock.Mock(url='https://checkout.stripe.com/fake-firm-overage')
        self.client.force_login(self.user)

        self.client.post(reverse('billing:create_valuation_purchase_checkout_session'), {'document_id': doc.id})

        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs['line_items'][0]['price'], 'price_valuation_firm_overage_fake')

    def test_unknown_document_id_rejected_without_calling_stripe(self):
        self.client.force_login(self.user)
        with mock.patch('billing.views.stripe.checkout.Session.create') as mock_create:
            response = self.client.post(
                reverse('billing:create_valuation_purchase_checkout_session'), {'document_id': 999999}, follow=True,
            )
        mock_create.assert_not_called()
        self.assertContains(response, "Valuation report not found")

    def test_other_users_document_rejected_without_calling_stripe(self):
        other = User.objects.create_user('valuation_purchase_other', password='x')
        doc = self._preview_doc(other)
        self.client.force_login(self.user)

        with mock.patch('billing.views.stripe.checkout.Session.create') as mock_create:
            response = self.client.post(
                reverse('billing:create_valuation_purchase_checkout_session'), {'document_id': doc.id}, follow=True,
            )
        mock_create.assert_not_called()
        self.assertContains(response, "Valuation report not found")

    def test_already_full_document_rejected_without_calling_stripe(self):
        from zelda_api.vector_models import DocumentSource
        doc = DocumentSource.objects.create(
            filename='deck.txt', source_entity='FounderCo', uploaded_by=self.user,
            document_type='business_valuation', status='analyzed', valuation_tier='full',
        )
        self.client.force_login(self.user)

        with mock.patch('billing.views.stripe.checkout.Session.create') as mock_create:
            response = self.client.post(
                reverse('billing:create_valuation_purchase_checkout_session'), {'document_id': doc.id}, follow=True,
            )
        mock_create.assert_not_called()
        self.assertContains(response, "already unlocked")

    def test_webhook_unlocks_the_specific_document_and_creates_redeemed_purchase(self):
        from zelda_api.models import ValuationPurchase
        doc = self._preview_doc(self.user)
        fake_event = {
            'type': 'checkout.session.completed',
            'data': {'object': {
                'id': 'cs_fake_valuation_123',
                'metadata': {
                    'user_id': str(self.user.id), 'purpose': 'valuation_purchase',
                    'purchase_type': 'report', 'document_id': str(doc.id),
                },
                'customer': 'cus_fake', 'client_reference_id': str(self.user.id),
            }},
        }
        with mock.patch('billing.views.stripe.Webhook.construct_event', return_value=fake_event):
            response = self.client.post(
                reverse('billing:stripe_webhook'), data=json.dumps(fake_event),
                content_type='application/json', HTTP_STRIPE_SIGNATURE='fake-signature',
            )

        self.assertEqual(response.status_code, 200)
        doc.refresh_from_db()
        self.assertEqual(doc.valuation_tier, 'full')
        purchase = ValuationPurchase.objects.get(user=self.user)
        self.assertEqual(purchase.purchase_type, 'report')
        self.assertEqual(purchase.redeemed_document_id, doc.id)
        self.assertIsNotNone(purchase.redeemed_at)
        self.assertEqual(purchase.stripe_checkout_session_id, 'cs_fake_valuation_123')

    def test_webhook_does_not_unlock_a_different_document(self):
        """Metadata names one specific document — only that one flips to 'full', not any other preview the user has."""
        doc_to_unlock = self._preview_doc(self.user, source_entity='UnlockMe')
        untouched_doc = self._preview_doc(self.user, source_entity='LeaveMeLocked')
        fake_event = {
            'type': 'checkout.session.completed',
            'data': {'object': {
                'id': 'cs_fake_valuation_789',
                'metadata': {
                    'user_id': str(self.user.id), 'purpose': 'valuation_purchase',
                    'purchase_type': 'report', 'document_id': str(doc_to_unlock.id),
                },
                'customer': 'cus_fake', 'client_reference_id': str(self.user.id),
            }},
        }
        with mock.patch('billing.views.stripe.Webhook.construct_event', return_value=fake_event):
            self.client.post(
                reverse('billing:stripe_webhook'), data=json.dumps(fake_event),
                content_type='application/json', HTTP_STRIPE_SIGNATURE='fake-signature',
            )

        doc_to_unlock.refresh_from_db()
        untouched_doc.refresh_from_db()
        self.assertEqual(doc_to_unlock.valuation_tier, 'full')
        self.assertEqual(untouched_doc.valuation_tier, 'preview')

    def test_webhook_valuation_purchase_does_not_touch_subscription_or_premium_flag(self):
        """A one-time report unlock must never grant or imply Premium status — that's a completely separate subscription concept."""
        from matchmaking.models import Application
        app = Application.objects.create(user=self.user, company_name='FounderCo', is_premium=False)
        doc = self._preview_doc(self.user)
        fake_event = {
            'type': 'checkout.session.completed',
            'data': {'object': {
                'id': 'cs_fake_valuation_456',
                'metadata': {
                    'user_id': str(self.user.id), 'purpose': 'valuation_purchase',
                    'purchase_type': 'report', 'document_id': str(doc.id),
                },
                'customer': 'cus_fake', 'client_reference_id': str(self.user.id),
            }},
        }
        with mock.patch('billing.views.stripe.Webhook.construct_event', return_value=fake_event):
            self.client.post(
                reverse('billing:stripe_webhook'), data=json.dumps(fake_event),
                content_type='application/json', HTTP_STRIPE_SIGNATURE='fake-signature',
            )

        app.refresh_from_db()
        self.assertFalse(app.is_premium)
        self.assertEqual(Subscription.objects.count(), 0)
