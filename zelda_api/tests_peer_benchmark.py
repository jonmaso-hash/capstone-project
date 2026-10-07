
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from matchmaking.models import Application, PeerMarketBenchmark, SellerApplication
from zelda_api.peer_benchmark import create_monthly_benchmark, generate_benchmark, interlink_benchmark

User = get_user_model()


class PeerMarketBenchmarkTests(TestCase):
    def founder(self, username, company, geography='San Diego, CA, US', **kwargs):
        user = User.objects.create_user(username, password='x')
        app = Application.objects.create(
            user=user, company_name=company, founder_name='Founder',
            email=f'{username}@example.com', description='Software company',
            sector='SaaS', stage='Seed', geography=geography,
            is_premium=kwargs.pop('is_premium', True),
            prior_amount_raised=kwargs.pop('prior_amount_raised', 0),
            raising_amount=kwargs.pop('raising_amount', 0),
            team_size=kwargs.pop('team_size', None),
            years_in_business=kwargs.pop('years_in_business', 0),
            **kwargs,
        )
        return user, app

    def seller(self, username, company, **kwargs):
        user = User.objects.create_user(username, password='x')
        profile = SellerApplication.objects.create(
            user=user, company_name=company, seller_name='Seller',
            email=f'{username}@example.com', description='Operating business',
            industry='Manufacturing', geography='San Diego, CA, US',
            is_premium=kwargs.pop('is_premium', True),
            annual_revenue=kwargs.pop('annual_revenue', None),
            ebitda=kwargs.pop('ebitda', None),
            asking_price=kwargs.pop('asking_price', 0),
            team_size=kwargs.pop('team_size', None),
            years_in_business=kwargs.pop('years_in_business', 0),
            **kwargs,
        )
        return user, profile

    def test_founder_interlink_benchmark_uses_sector_stage_and_geography(self):
        _, subject = self.founder(
            'bench_founder', 'SubjectCo', prior_amount_raised=3000000,
            raising_amount=2000000, team_size=12, years_in_business=4,
        )
        self.founder(
            'bench_peer1', 'PeerOne', prior_amount_raised=1000000,
            raising_amount=1000000, team_size=8, years_in_business=3,
            field_visibility={'prior_amount_raised': 'PUBLIC', 'raising_amount': 'PUBLIC'},
        )
        self.founder(
            'bench_peer2', 'PeerTwo', prior_amount_raised=5000000,
            raising_amount=4000000, team_size=20, years_in_business=6,
            field_visibility={'prior_amount_raised': 'PUBLIC', 'raising_amount': 'PUBLIC'},
        )
        data = interlink_benchmark(subject, 'founder')
        self.assertEqual(data['site']['peer_count'], 2)
        self.assertEqual(data['city']['peer_count'], 2)
        self.assertEqual(data['site']['metrics']['funding_raised']['median'], 3000000)
        self.assertEqual(data['site']['metrics']['employee_count']['percentile'], 50)

    def test_seller_interlink_benchmark_uses_industry(self):
        _, subject = self.seller(
            'bench_seller', 'SellerCo', annual_revenue=2000000,
            ebitda=400000, asking_price=3000000, team_size=10, years_in_business=8,
        )
        self.seller(
            'bench_seller_peer', 'SellerPeer', annual_revenue=1000000,
            ebitda=200000, asking_price=2000000, team_size=7, years_in_business=6,
            field_visibility={'annual_revenue': 'PUBLIC', 'ebitda': 'PUBLIC', 'asking_price': 'PUBLIC'},
        )
        data = interlink_benchmark(subject, 'seller')
        self.assertEqual(data['site']['peer_count'], 1)
        self.assertEqual(data['site']['metrics']['annual_revenue']['percentile'], 100)
        self.assertEqual(data['site']['metrics']['asking_price']['median'], 2000000)

    def test_hidden_peer_financials_do_not_enter_benchmark_aggregates(self):
        _, subject = self.founder(
            'privacy_subject', 'PrivacySubject', prior_amount_raised=3000000,
            raising_amount=2000000, team_size=12, years_in_business=4,
        )
        self.founder(
            'privacy_peer', 'PrivacyPeer', prior_amount_raised=9000000,
            raising_amount=8000000, team_size=9, years_in_business=3,
            field_visibility={'prior_amount_raised': 'PRIVATE', 'raising_amount': 'PRIVATE'},
        )

        data = interlink_benchmark(subject, 'founder')
        funding = data['site']['metrics']['funding_raised']
        current_raise = data['site']['metrics']['current_raise']

        self.assertIsNone(funding['median'])
        self.assertIsNone(funding['percentile'])
        self.assertEqual(funding['peer_values_available'], 0)
        self.assertIsNone(current_raise['median'])
        self.assertEqual(current_raise['peer_values_available'], 0)

    def test_monthly_gate_prevents_duplicate_research_spend(self):
        user, app = self.founder('monthly_founder', 'MonthlyCo')
        first, created = create_monthly_benchmark(user, 'founder')
        self.assertTrue(created)
        second, created = create_monthly_benchmark(user, 'founder')
        self.assertFalse(created)
        self.assertEqual(second.pk, first.pk)
        first.status = 'ready'
        first.refresh_eligible_at = timezone.now() + timedelta(days=29)
        first.save(update_fields=['status', 'refresh_eligible_at'])
        third, created = create_monthly_benchmark(user, 'founder')
        self.assertFalse(created)
        self.assertEqual(third.pk, first.pk)

    def test_failed_generation_is_throttled_for_an_hour(self):
        user, app = self.founder('failed_founder', 'FailedCo')
        first = PeerMarketBenchmark.objects.create(
            user=user, role='founder', founder=app, subject_name=app.company_name, status='failed'
        )
        second, created = create_monthly_benchmark(user, 'founder')
        self.assertFalse(created)
        self.assertEqual(second.pk, first.pk)

    def test_generate_benchmark_freezes_sources_and_sets_refresh(self):
        user, app = self.founder('generate_founder', 'GenerateCo', prior_amount_raised=2000000)
        benchmark = PeerMarketBenchmark.objects.create(
            user=user, role='founder', founder=app, subject_name=app.company_name
        )
        external = {
            'cohort_label': 'Seed SaaS peers',
            'peers': [{'company_name': 'Peer A', 'funding_raised': 1000000}],
            'metrics': {'funding_raised': {'value': 2000000, 'median': 1000000, 'percentile': 100, 'peer_values_available': 1}},
            'sources': [{'url': 'https://example.com/peer-a', 'title': 'Peer A source', 'cited_text': 'Raised $1M'}],
            'summary': 'GenerateCo has more disclosed funding than the cited peer.',
        }
        with mock.patch('zelda_api.peer_benchmark.external_research', return_value=external):
            result = generate_benchmark(benchmark.id)
        self.assertEqual(result.status, 'ready')
        self.assertEqual(result.sources[0]['url'], 'https://example.com/peer-a')
        self.assertGreater(result.refresh_eligible_at, result.generated_at + timedelta(days=29))

    def test_share_link_is_revocable_and_public_only_when_enabled(self):
        user, app = self.founder('share_founder', 'ShareCo')
        benchmark = PeerMarketBenchmark.objects.create(
            user=user, role='founder', founder=app, subject_name=app.company_name,
            status='ready', generated_at=timezone.now(),
        )
        url = reverse('accounts:peer_market_benchmark_share', args=[benchmark.share_token])
        self.assertEqual(self.client.get(url).status_code, 404)
        benchmark.sharing_enabled = True
        benchmark.save(update_fields=['sharing_enabled'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Peer Market Benchmark')
        self.assertContains(response, 'ShareCo')
        benchmark.sharing_enabled = False
        benchmark.save(update_fields=['sharing_enabled'])
        self.assertEqual(self.client.get(url).status_code, 404)
