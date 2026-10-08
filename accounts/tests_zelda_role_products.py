from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.models import (
    Application,
    BuyerApplication,
    InvestorApplication,
    SellerApplication,
)


User = get_user_model()
PRODUCT_KEYS = (
    'intelligence_memo',
    'ic_memo',
    'truth_delta',
    'complete_bundle',
    'three_pack',
    'entity',
    'valuation',
)


class ZeldaFounderProductSurfaceTests(TestCase):
    def test_founder_sidebar_shows_exact_seven_zelda_products(self):
        user = User.objects.create_user('zelda_surface_founder', password='x')
        Application.objects.create(
            user=user,
            founder_name='Founder',
            email='founder@example.com',
            company_name='Founder Co',
            sector='SaaS',
            stage='Seed',
            description='Test founder',
            is_private=False,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('accounts:profile', args=[user.username]))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        for key in PRODUCT_KEYS:
            with self.subTest(key=key):
                self.assertIn(f'tab-product-{key}', body)
        self.assertIn('data-tab="library"', body)
        self.assertContains(response, 'See your company the way an investor may see it')


class ZeldaSellerProductSurfaceTests(TestCase):
    def test_seller_sidebar_shows_same_seven_self_company_reports(self):
        user = User.objects.create_user('zelda_surface_seller', password='x')
        SellerApplication.objects.create(
            user=user,
            company_name='Seller Co',
            seller_name='Seller',
            email='seller@example.com',
            description='Test seller business',
            industry='SaaS',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('accounts:profile', args=[user.username]))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        for key in PRODUCT_KEYS:
            with self.subTest(key=key):
                self.assertIn(f'tab-product-{key}', body)
        self.assertContains(response, "See your business from a buyer's perspective")


class ZeldaDiligenceProductSurfaceTests(TestCase):
    def test_investor_uses_product_tabs_for_deal_materials(self):
        user = User.objects.create_user('zelda_surface_investor', password='x')
        InvestorApplication.objects.create(
            user=user,
            full_name='Investor',
            company_name='Fund',
            email='investor@example.com',
            investment_focus='SaaS',
            investment_stage='Seed',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('accounts:profile', args=[user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose a Zelda intelligence product to organize first-pass diligence.')
        self.assertNotContains(response, 'data-tab="upload"', html=False)
        self.assertNotContains(response, 'id="tab-upload"', html=False)
        self.assertNotContains(response, 'id="document-upload-form"', html=False)
        self.assertContains(response, 'tab-product-truth_delta_diligence')
        self.assertContains(response, 'tab-product-truth_delta_credit_pack')
        self.assertNotContains(response, 'tab-product-complete_bundle')

    def test_buyer_uses_product_tabs_for_acquisition_materials(self):
        user = User.objects.create_user('zelda_surface_buyer', password='x')
        BuyerApplication.objects.create(
            user=user,
            full_name='Buyer',
            company_name='Acquirer',
            email='buyer@example.com',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('accounts:profile', args=[user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose a Zelda intelligence product to organize first-pass diligence.')
        self.assertNotContains(response, 'data-tab="upload"', html=False)
        self.assertNotContains(response, 'id="tab-upload"', html=False)
        self.assertNotContains(response, 'id="document-upload-form"', html=False)
        self.assertContains(response, 'tab-product-truth_delta_diligence')
        self.assertContains(response, 'tab-product-truth_delta_credit_pack')
        self.assertNotContains(response, 'tab-product-entity')
