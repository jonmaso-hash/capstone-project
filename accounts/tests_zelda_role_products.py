from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.models import Application


User = get_user_model()


class ZeldaFounderProductSurfaceTests(TestCase):
    def test_founder_sidebar_shows_four_individual_reports_but_not_packs(self):
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
        for key in ('truth_delta', 'valuation', 'ic_memo', 'entity'):
            with self.subTest(key=key):
                self.assertIn(f'tab-product-{key}', body)
        self.assertIn('data-tab="library"', body)
        self.assertNotIn('tab-product-complete_bundle', body)
        self.assertNotIn('tab-product-three_pack', body)
