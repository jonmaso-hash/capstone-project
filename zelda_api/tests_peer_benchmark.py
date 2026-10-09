
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from matchmaking.models import (
    AcquisitionInterestEvent, Application, InvestorInterestEvent,
    PeerMarketBenchmark, SellerApplication,
)
from zelda_api.peer_benchmark import (
    INTERLINK_PRIVACY_VERSION, MIN_INTERLINK_PEERS, create_monthly_benchmark,
    generate_benchmark, interlink_benchmark, safe_interlink_snapshot, subject_snapshot,
)

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
        for i, funding in enumerate((1000000, 3000000, 5000000)):
            self.founder(
                f'bench_extra{i}', f'Extra{i}', prior_amount_raised=funding, team_size=8,
                field_visibility={'prior_amount_raised': 'PUBLIC', 'raising_amount': 'PUBLIC'},
            )
        data = interlink_benchmark(subject, 'founder')
        self.assertEqual(data['site']['peer_count'], 5)
        self.assertEqual(data['city']['peer_count'], 5)
        self.assertEqual(data['site']['metrics']['funding_raised']['median'], 3000000)
        self.assertEqual(data['site']['metrics']['employee_count']['percentile'], 80)

    def test_seller_interlink_benchmark_uses_industry(self):
        _, subject = self.seller(
            'bench_seller', 'SellerCo', annual_revenue=2000000,
            ebitda=400000, asking_price=3000000, team_size=10, years_in_business=8,
        )
        for i in range(MIN_INTERLINK_PEERS):
            self.seller(
                f'bench_seller_peer{i}', f'SellerPeer{i}', annual_revenue=1000000,
                ebitda=200000, asking_price=2000000, team_size=7, years_in_business=6,
                field_visibility={'annual_revenue': 'PUBLIC', 'ebitda': 'PUBLIC', 'asking_price': 'PUBLIC'},
            )
        data = interlink_benchmark(subject, 'seller')
        self.assertEqual(data['site']['peer_count'], 5)
        self.assertEqual(data['site']['metrics']['annual_revenue']['percentile'], 100)
        self.assertEqual(data['site']['metrics']['asking_price']['median'], 2000000)

    def test_hidden_peer_financials_do_not_enter_benchmark_aggregates(self):
        _, subject = self.founder(
            'privacy_subject', 'PrivacySubject', prior_amount_raised=3000000,
            raising_amount=2000000, team_size=12, years_in_business=4,
        )
        for i in range(MIN_INTERLINK_PEERS):
            self.founder(
                f'privacy_peer{i}', f'PrivacyPeer{i}', prior_amount_raised=9000000,
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

    def test_small_geographic_cohorts_are_suppressed(self):
        _, subject = self.founder('small_subject', 'Subject')
        for i in range(MIN_INTERLINK_PEERS):
            self.founder(f'small_peer{i}', f'Peer{i}', geography=(
                'San Diego, CA, US' if i == 0 else 'Austin, TX, US'
            ))
        data = interlink_benchmark(subject, 'founder')
        for level in ('city', 'state'):
            self.assertEqual(data[level]['peer_count'], 0)
            self.assertEqual(data[level]['metrics'], {})
        self.assertEqual(data['site']['peer_count'], 5)
        self.assertEqual(data['country']['peer_count'], 5)

    def test_four_peers_are_suppressed_and_five_are_available_for_both_roles(self):
        for role, factory in (('founder', self.founder), ('seller', self.seller)):
            _, subject = factory(f'boundary_{role}', 'Subject', team_size=10)
            for i in range(MIN_INTERLINK_PEERS - 1):
                factory(f'boundary_{role}{i}', f'Peer{i}', team_size=8)
            data = interlink_benchmark(subject, role)
            self.assertTrue(all(row['peer_count'] == 0 and row['metrics'] == {}
                                for row in data.values()))
            factory(f'boundary_{role}_fifth', 'Fifth', team_size=8)
            data = interlink_benchmark(subject, role)
            self.assertEqual(data['site']['metrics']['employee_count']['median'], 8)
            self.assertEqual(data['site']['metrics']['employee_count']['peer_values_available'], 5)
            safe = safe_interlink_snapshot(data, role)
            self.assertEqual(safe['site']['metrics']['employee_count']['median'], 8)
            self.assertNotIn('contributor_ids', safe['site']['metrics']['employee_count'])
            self.assertNotIn('peer_ids', safe['site'])

    def test_minimum_applies_to_each_visible_metric_and_hidden_equals_absent(self):
        _, subject = self.founder('metric_subject', 'Subject', team_size=10)
        hidden = []
        for i in range(MIN_INTERLINK_PEERS):
            _, peer = self.founder(
                f'metric_peer{i}', f'Peer{i}', team_size=777,
                field_visibility={'team_size': 'PUBLIC' if i == 0 else 'PRIVATE'},
            )
            if i:
                hidden.append(peer)
        before = interlink_benchmark(subject, 'founder')
        row = before['site']['metrics']['employee_count']
        self.assertIsNone(row['median'])
        self.assertIsNone(row['percentile'])
        self.assertEqual(row['peer_values_available'], 0)
        for peer in hidden:
            peer.team_size = None
            peer.save(update_fields=['team_size'])
        self.assertEqual(before, interlink_benchmark(subject, 'founder'))

    def test_private_cohort_fields_and_geography_cannot_affect_results(self):
        _, subject = self.founder('cohort_subject', 'Subject')
        for i in range(MIN_INTERLINK_PEERS):
            self.founder(f'cohort_peer{i}', f'Peer{i}', field_visibility={'geography': 'PRIVATE'})
        _, hidden = self.founder('cohort_hidden', 'Hidden', field_visibility={'sector': 'PRIVATE'})
        before = interlink_benchmark(subject, 'founder')
        self.assertEqual(before['site']['peer_count'], 5)
        for level in ('city', 'state', 'country'):
            self.assertEqual(before[level]['peer_count'], 0)
        hidden.sector = 'Healthcare'
        hidden.save(update_fields=['sector'])
        self.assertEqual(before, interlink_benchmark(subject, 'founder'))

    def test_activity_never_enters_founder_or_seller_benchmark(self):
        for role, factory, event_model, owner_field in (
            ('founder', self.founder, InvestorInterestEvent, 'founder'),
            ('seller', self.seller, AcquisitionInterestEvent, 'seller'),
        ):
            _, subject = factory(f'activity_{role}', 'Subject')
            peers = [factory(f'activity_{role}{i}', f'Peer{i}')[1]
                     for i in range(MIN_INTERLINK_PEERS)]
            before = interlink_benchmark(subject, role)
            for event_type in ('memo_view', 'truth_delta_view', 'message_sent', 'intro_request'):
                actor_field = 'investor' if role == 'founder' else 'buyer'
                event_model.objects.create(
                    **{owner_field: peers[0], actor_field: subject.user}, event_type=event_type,
                )
            self.assertEqual(before, interlink_benchmark(subject, role))
            for cohort in before.values():
                self.assertNotIn('investor_interest_events', cohort['metrics'])
                self.assertNotIn('buyer_interest_events', cohort['metrics'])

    def test_legacy_saved_aggregates_are_suppressed_on_owner_and_share_pages(self):
        user, app = self.founder('legacy_owner', 'LegacyCo')
        for count in (1, 20):
            benchmark = PeerMarketBenchmark.objects.create(
                user=user, role='founder', founder=app, subject_name=app.company_name,
                status='ready', sharing_enabled=True, interlink_benchmark={
                    'site': {'peer_count': count, 'metrics': {
                        'investor_interest_events': {'value': 1, 'median': 987654321, 'percentile': 100},
                        'funding_raised': {'value': 2, 'median': 987654321, 'percentile': 100},
                    }},
                },
            )
            share_url = reverse('accounts:peer_market_benchmark_share', args=[benchmark.share_token])
            detail_url = reverse('accounts:peer_market_benchmark_detail', args=[benchmark.id])
            for url in (share_url, detail_url):
                if url == detail_url:
                    self.client.force_login(user)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, '987654321')
                self.assertNotContains(response, 'investor_interest_events')
                self.assertEqual(response.context['benchmark'].interlink_benchmark['site']['metrics'], {})
            benchmark.refresh_from_db()
            self.assertIn('investor_interest_events', benchmark.interlink_benchmark['site']['metrics'])
            self.client.logout()

    def test_snapshot_reader_requires_supported_metrics_and_five_contributors(self):
        ids = [self.founder(
            f'snapshot_peer{i}', f'Peer{i}',
            prior_amount_raised=10,
            field_visibility={'prior_amount_raised': 'PUBLIC'},
        )[1].pk for i in range(MIN_INTERLINK_PEERS)]
        data = safe_interlink_snapshot({'site': {
            'privacy_version': INTERLINK_PRIVACY_VERSION, 'peer_count': 5, 'peer_ids': ids,
            'metrics': {
                'funding_raised': {'value': 1, 'median': 2, 'percentile': 50,
                                   'peer_values_available': 5, 'contributor_ids': ids},
                'employee_count': {'value': 3, 'median': 4, 'percentile': 50, 'peer_values_available': 1},
                'investor_interest_events': {'median': 777, 'peer_values_available': 10},
            },
        }}, 'founder')
        self.assertEqual(data['site']['metrics']['funding_raised']['median'], 2)
        self.assertIsNone(data['site']['metrics']['employee_count']['median'])
        self.assertEqual(data['site']['metrics']['employee_count']['peer_values_available'], 0)
        self.assertNotIn('investor_interest_events', data['site']['metrics'])

    def test_default_zeros_are_unknown_and_do_not_meet_contributor_threshold(self):
        for role, factory, names in (
            ('founder', self.founder, ('funding_raised', 'current_raise', 'years_in_business')),
            ('seller', self.seller, ('asking_price', 'years_in_business')),
        ):
            _, subject = factory(f'zeros_{role}', 'Subject', years_in_business=3)
            visibility = {'prior_amount_raised': 'PUBLIC', 'raising_amount': 'PUBLIC'} if role == 'founder' else {}
            peers = [factory(f'zeros_{role}{i}', f'Peer{i}', field_visibility=visibility)[1]
                     for i in range(MIN_INTERLINK_PEERS)]
            data = interlink_benchmark(subject, role)
            for name in names:
                row = data['site']['metrics'][name]
                self.assertIsNone(row['median'])
                self.assertIsNone(row['percentile'])
                self.assertEqual(row['peer_values_available'], 0)
                self.assertEqual(row['contributor_ids'], [])
            self.assertIsNone(subject_snapshot(peers[0], role)['years_in_business'])
            # Four disclosed nonzero values plus one default still fail.
            for peer in peers[:4]:
                peer.years_in_business = 2
                peer.save(update_fields=['years_in_business'])
            self.assertIsNone(interlink_benchmark(subject, role)['site']['metrics']['years_in_business']['median'])
            peers[4].years_in_business = 2
            peers[4].save(update_fields=['years_in_business'])
            row = interlink_benchmark(subject, role)['site']['metrics']['years_in_business']
            self.assertEqual(row['median'], 2)
            self.assertEqual(row['percentile'], 100)

    def test_zero_nullable_financials_remain_disclosed_values(self):
        _, subject = self.seller('real_zero_subject', 'Subject', annual_revenue=0, ebitda=-10)
        for i in range(MIN_INTERLINK_PEERS):
            self.seller(f'real_zero_peer{i}', f'Peer{i}', annual_revenue=0, ebitda=-20,
                        field_visibility={'annual_revenue': 'PUBLIC', 'ebitda': 'PUBLIC'})
        rows = interlink_benchmark(subject, 'seller')['site']['metrics']
        self.assertEqual(rows['annual_revenue']['median'], 0)
        self.assertEqual(rows['annual_revenue']['peer_values_available'], 5)
        self.assertEqual(rows['ebitda']['median'], -20)

    def test_version_one_aggregates_are_suppressed(self):
        _, subject = self.founder('old_zero_subject', 'Subject')
        for i in range(MIN_INTERLINK_PEERS):
            self.founder(f'old_zero_peer{i}', f'Peer{i}', team_size=2)
        data = interlink_benchmark(subject, 'founder')
        for cohort in data.values():
            cohort['privacy_version'] = 1
        self.assertTrue(all(row['metrics'] == {} for row in safe_interlink_snapshot(data, 'founder').values()))

    def test_old_external_subject_defaults_have_no_value_or_percentile_on_either_page(self):
        user, subject = self.seller('external_zero_owner', 'Subject')
        benchmark = PeerMarketBenchmark.objects.create(
            user=user, role='seller', seller=subject, subject_name='Subject',
            status='ready', sharing_enabled=True, external_benchmark={
                'asking_or_transaction_value': {
                    'value': 0, 'median': 500, 'percentile': 0, 'peer_values_available': 5,
                },
            },
        )
        self.client.force_login(user)
        for url in (
            reverse('accounts:peer_market_benchmark_detail', args=[benchmark.id]),
            reverse('accounts:peer_market_benchmark_share', args=[benchmark.share_token]),
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            row = response.context['benchmark'].external_benchmark['asking_or_transaction_value']
            self.assertIsNone(row['value'])
            self.assertIsNone(row['percentile'])
            self.assertEqual(row['median'], 500)

    def test_cleared_contributor_suppresses_saved_metric(self):
        _, subject = self.seller('clear_subject', 'Subject', asking_price=1000)
        peers = [self.seller(f'clear_peer{i}', f'Peer{i}', asking_price=500)[1]
                 for i in range(MIN_INTERLINK_PEERS)]
        data = interlink_benchmark(subject, 'seller')
        peers[0].asking_price = 0
        peers[0].save(update_fields=['asking_price'])
        row = safe_interlink_snapshot(data, 'seller')['site']['metrics']['asking_price']
        self.assertIsNone(row['median'])
        self.assertIsNone(row['percentile'])
        self.assertEqual(row['peer_values_available'], 0)

    def test_public_share_masks_owner_values_and_percentiles_after_revocation(self):
        for role, factory, field, internal_name, external_name in (
            ('founder', self.founder, 'raising_amount', 'current_raise', 'latest_round_size'),
            ('seller', self.seller, 'asking_price', 'asking_price', 'asking_or_transaction_value'),
        ):
            user, subject = factory(f'owner_mask_{role}', 'Subject', **{field: 987654321},
                                    field_visibility={field: 'PUBLIC'})
            for i in range(MIN_INTERLINK_PEERS):
                factory(f'owner_mask_{role}{i}', f'Peer{i}', **{field: 500},
                        field_visibility={field: 'PUBLIC'})
            benchmark = PeerMarketBenchmark.objects.create(
                user=user, role=role, subject_name='Subject', status='ready', sharing_enabled=True,
                **{role: subject}, interlink_benchmark=interlink_benchmark(subject, role),
                external_benchmark={external_name: {
                    'value': 987654321, 'median': 500, 'percentile': 100, 'peer_values_available': 5,
                }}, narrative='Private figure: 987654321', cohort_label='987654321',
                sources=[{'url': 'https://example.com', 'title': 'Public source', 'cited_text': '987654321'}],
            )
            public_url = reverse('accounts:peer_market_benchmark_share', args=[benchmark.share_token])
            owner_url = reverse('accounts:peer_market_benchmark_detail', args=[benchmark.id])
            self.assertContains(self.client.get(public_url), '987654321')
            for visibility in ('CONNECTED', 'PRIVATE'):
                subject.field_visibility = {field: visibility}
                subject.save(update_fields=['field_visibility'])
                # Public URL never carries owner privileges, even when logged in.
                for logged_in in (False, True):
                    if logged_in:
                        self.client.force_login(user)
                    else:
                        self.client.logout()
                    response = self.client.get(public_url)
                    self.assertEqual(response.status_code, 200)
                    self.assertNotContains(response, '987654321')
                    safe = response.context['benchmark']
                    for row in (safe.external_benchmark[external_name],
                                safe.interlink_benchmark['site']['metrics'][internal_name]):
                        self.assertIsNone(row['value'])
                        self.assertIsNone(row['percentile'])
                        self.assertEqual(row['median'], 500)
            self.client.force_login(user)
            self.assertContains(self.client.get(owner_url), '987654321')
            benchmark.refresh_from_db()
            self.assertEqual(benchmark.external_benchmark[external_name]['value'], 987654321)
            self.assertEqual(benchmark.narrative, 'Private figure: 987654321')
            self.client.logout()

    def test_private_subject_geography_and_cohort_are_not_inferred_by_sharing(self):
        user, subject = self.founder('hidden_cohort_owner', 'Subject', field_visibility={'geography': 'PRIVATE'})
        for i in range(MIN_INTERLINK_PEERS):
            self.founder(f'hidden_cohort_peer{i}', f'Peer{i}', team_size=5)
        benchmark = PeerMarketBenchmark.objects.create(
            user=user, role='founder', founder=subject, subject_name='Subject',
            status='ready', sharing_enabled=True, interlink_benchmark=interlink_benchmark(subject, 'founder'),
            cohort_label='San Diego', narrative='San Diego',
            external_peers=[{'company_name': 'San Diego peer'}],
        )
        url = reverse('accounts:peer_market_benchmark_share', args=[benchmark.share_token])
        response = self.client.get(url)
        safe = response.context['benchmark']
        self.assertNotContains(response, 'San Diego peer')
        self.assertEqual(safe.cohort_label, '')
        self.assertEqual(safe.narrative, '')
        self.assertEqual(safe.interlink_benchmark['city']['peer_count'], 0)
        self.assertEqual(safe.interlink_benchmark['site']['peer_count'], 5)
        subject.field_visibility = {'sector': 'PRIVATE'}
        subject.save(update_fields=['field_visibility'])
        safe = self.client.get(url).context['benchmark']
        self.assertEqual(safe.interlink_benchmark['site']['peer_count'], 0)

    def test_visibility_revocation_suppresses_saved_aggregates_on_both_pages(self):
        for role, factory, field, metric_name in (
            ('founder', self.founder, 'team_size', 'employee_count'),
            ('seller', self.seller, 'asking_price', 'asking_price'),
        ):
            user, subject = factory(f'revoke_{role}', 'Subject')
            peers = [factory(f'revoke_{role}{i}', f'Peer{i}', **{field: 777})[1]
                     for i in range(MIN_INTERLINK_PEERS)]
            benchmark = PeerMarketBenchmark.objects.create(
                user=user, role=role, subject_name='Subject', status='ready', sharing_enabled=True,
                **{role: subject}, interlink_benchmark=interlink_benchmark(subject, role),
            )
            public_url = reverse('accounts:peer_market_benchmark_share', args=[benchmark.share_token])
            owner_url = reverse('accounts:peer_market_benchmark_detail', args=[benchmark.id])
            self.assertContains(self.client.get(public_url), '777')
            peers[0].field_visibility = {field: 'PRIVATE'}
            peers[0].save(update_fields=['field_visibility'])
            self.client.force_login(user)
            for url in (public_url, owner_url):
                response = self.client.get(url)
                row = response.context['benchmark'].interlink_benchmark['site']['metrics'][metric_name]
                self.assertIsNone(row['median'])
                self.assertEqual(row['peer_values_available'], 0)
                self.assertNotContains(response, '777')
            peers[0].delete()
            self.assertEqual(self.client.get(public_url).context['benchmark'].interlink_benchmark['site']['peer_count'], 0)
            self.client.logout()

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
