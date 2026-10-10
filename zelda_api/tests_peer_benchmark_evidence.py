"""Per-figure provenance reaches both frozen reports and public rendering."""
import copy
import json
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from matchmaking.models import Application, PeerMarketBenchmark
from .peer_benchmark import external_research, extract_text_and_sources, prepare_external_report
from .peer_benchmark_evidence import (
    EVIDENCE_VERSION, external_metrics, normalized_peers, source_set,
)


def fixture(values=(1000000, 2000000, 3000000), metric='funding_raised', unit='USD',
            basis='total_equity_funding', as_of='2025-12-31'):
    peers, sources = [], []
    for i, value in enumerate(values):
        name, url = f'Peer {i} Holdings', f'https://example.com/peer-{i}'
        descriptions = {
            'funding_raised': f'total equity funding of {unit} {value}',
            'current_raise': f'a fundraising target of {unit} {value}',
            'latest_round_size': f'closed a completed equity round of {unit} {value}',
            'annual_revenue': f'annual reported revenue of {unit} {value} for the year ended',
            'ebitda': f'annual reported EBITDA of {unit} {value} for the year ended',
            'asking_price': f'an asking enterprise value of {unit} {value}',
            'transaction_value': f'a completed transaction enterprise value of {unit} {value}',
            'employee_count': f'{value} employees',
            'years_in_business': f'{value} years in business',
        }
        quote = f'{name} disclosed {descriptions[metric]} as of {as_of}.'
        fact = dict(value=value, unit=unit, basis=basis, as_of=as_of,
                    period_kind='annual' if metric in ('annual_revenue', 'ebitda') else None,
                    period_end=as_of if metric in ('annual_revenue', 'ebitda') else None,
                    source_url=url, source_quote=quote)
        peers.append(dict(company_name=name, facts={metric: fact}))
        sources.append(dict(url=url, title=name, cited_text=quote))
    return peers, sources


def rows(peers, sources, role='founder', subject=None):
    return external_metrics(role, subject or {}, normalized_peers(peers, sources, role))


class PeerFigureAdmissionTests(SimpleTestCase):
    def test_three_distinct_cited_figures_have_a_median_and_no_invented_owner_basis(self):
        peers, sources = fixture()
        row = rows(peers, sources, subject={'funding_raised': 5000000})['funding_raised']
        self.assertEqual(row['median'], 2000000)
        self.assertEqual(row['peer_values_available'], 3)
        self.assertIsNone(row['percentile'])
        self.assertIsNone(row['groups'][0]['value'])
        self.assertEqual(len(row['groups'][0]['figures']), 3)

    def test_percentile_requires_the_same_explicit_subject_measurement_basis(self):
        peers, sources = fixture()
        subject = {'funding_raised': 5000000, 'metric_bases': {'funding_raised': {
            'unit': 'USD', 'basis': 'total_equity_funding', 'period_kind': '',
            'period_end': '', 'as_of': '2025-12-31'}}}
        self.assertEqual(rows(peers, sources, subject=subject)['funding_raised']['percentile'], 100)
        for key, value in (('unit', 'EUR'), ('basis', 'total_funding'), ('as_of', '2024-12-31')):
            changed = copy.deepcopy(subject)
            changed['metric_bases']['funding_raised'][key] = value
            self.assertIsNone(rows(peers, sources, subject=changed)['funding_raised']['percentile'])

    def test_bare_legacy_numbers_or_a_url_without_a_provider_excerpt_are_not_evidence(self):
        peers, sources = fixture()
        peers[0] = {'company_name': 'Peer 0 Holdings', 'funding_raised': 1000000}
        sources[1]['cited_text'] = ''
        self.assertIsNone(rows(peers, sources)['funding_raised']['median'])
        self.assertEqual(rows(peers, sources)['funding_raised']['peer_values_available'], 1)

    def test_unknown_urls_fabricated_quotes_wrong_entities_and_wrong_values_do_not_contribute(self):
        for change in (
            {'source_url': 'https://example.com/invented'}, {'source_quote': 'Invented passage'},
            {'source_quote': 'Peer 0 Holdings reported total equity funding USD 1000000 as of 2025-12-31.'},
            {'source_quote': 'Peer 1 Holdings has USD 1000000 total equity funding as of 2025-12-31.'},
            {'value': 987654321}, {'value': True}, {'value': float('nan')},
            {'value': float('inf')}, {'source_url': {'url': 'malformed'}},
        ):
            peers, sources = fixture()
            peers[0]['facts']['funding_raised'].update(change)
            result = rows(peers, sources)['funding_raised']
            self.assertIsNone(result['median'], change)
            self.assertEqual(result['peer_values_available'], 2, change)

    def test_currencies_dates_and_equity_vs_total_funding_have_separate_groups(self):
        for unit, basis, as_of in (
            ('EUR', 'total_equity_funding', '2025-12-31'),
            ('USD', 'total_funding', '2025-12-31'),
            ('USD', 'total_equity_funding', '2024-12-31'),
        ):
            peers, sources = fixture()
            more, other_sources = fixture((9000000, 10000000, 11000000), unit=unit, basis=basis, as_of=as_of)
            for i, peer in enumerate(more):
                peer['company_name'] = f'Other {i} Holdings'
                fact = peer['facts']['funding_raised']
                fact['source_url'] += '/other'
                fact['source_quote'] = fact['source_quote'].replace(f'Peer {i}', f'Other {i}')
                if basis == 'total_funding':
                    fact['source_quote'] = fact['source_quote'].replace('total equity funding', 'total funding')
                other_sources[i].update(url=fact['source_url'], cited_text=fact['source_quote'])
            result = rows(peers + more, sources + other_sources)['funding_raised']
            self.assertEqual(len(result['groups']), 2)
            self.assertEqual(sorted(g['median'] for g in result['groups']), [2000000, 10000000])

    def test_missing_currency_and_bare_dollar_are_excluded_without_conversion(self):
        peers, sources = fixture()
        peers[0]['facts']['funding_raised']['unit'] = None
        quote = peers[1]['facts']['funding_raised']['source_quote'].replace('USD ', '$')
        peers[1]['facts']['funding_raised']['source_quote'] = quote
        sources[1]['cited_text'] = quote
        clean = normalized_peers(peers, sources, 'founder')
        self.assertFalse(clean[0]['figures'][0]['eligible'])
        self.assertFalse(clean[1]['figures'][0]['eligible'])
        self.assertEqual(rows(peers, sources)['funding_raised']['peer_values_available'], 1)

    def test_currency_needs_to_qualify_the_figure_and_names_cannot_match_partial_words(self):
        peers, sources = fixture()
        quote = 'Peer 0 Holdings total equity funding EUR 1000000; USD reporting preferred as of 2025-12-31.'
        peers[0]['facts']['funding_raised']['source_quote'] = quote
        sources[0]['cited_text'] = quote
        self.assertFalse(normalized_peers(peers, sources, 'founder')[0]['facts']['funding_raised']['eligible'])
        peers, sources = fixture()
        quote = peers[0]['facts']['funding_raised']['source_quote'].replace('Holdings', 'Holdingslight')
        peers[0]['facts']['funding_raised']['source_quote'] = quote
        sources[0]['cited_text'] = quote
        self.assertEqual(rows(peers, sources)['funding_raised']['peer_values_available'], 2)

    def test_missing_invented_future_or_invalid_measurement_dates_are_excluded(self):
        for value in (None, '2024-12-31', '2099-12-31', '2025-99-99', '20251231'):
            peers, sources = fixture()
            peers[0]['facts']['funding_raised']['as_of'] = value
            self.assertFalse(normalized_peers(peers, sources, 'founder')[0]['facts']['funding_raised']['eligible'])
            self.assertEqual(rows(peers, sources)['funding_raised']['peer_values_available'], 2)

    def test_annual_periods_are_not_inferred_and_adjusted_ebitda_is_not_pooled(self):
        peers, sources = fixture(metric='annual_revenue', basis='reported_revenue')
        self.assertEqual(rows(peers, sources, 'seller')['annual_revenue']['median'], 2000000)
        peers[0]['facts']['annual_revenue']['period_end'] = None
        self.assertFalse(normalized_peers(peers, sources, 'seller')[0]['facts']['annual_revenue']['eligible'])
        self.assertIsNone(rows(peers, sources, 'seller')['annual_revenue']['median'])
        peers, sources = fixture(metric='ebitda', basis='reported_ebitda')
        quote = peers[0]['facts']['ebitda']['source_quote'].replace('reported EBITDA', 'adjusted EBITDA')
        peers[0]['facts']['ebitda']['source_quote'] = quote
        sources[0]['cited_text'] = quote
        self.assertIsNone(rows(peers, sources, 'seller')['ebitda']['median'])

    def test_negative_reported_ebitda_and_explicit_zero_are_kept(self):
        peers, sources = fixture(values=(-100000, 0, 200000), metric='ebitda', basis='reported_ebitda')
        row = rows(peers, sources, 'seller')['ebitda']
        self.assertEqual(row['median'], 0)
        self.assertEqual(row['peer_values_available'], 3)

    def test_targets_and_forecasts_do_not_become_completed_or_reported_figures(self):
        for metric, basis, old, new, role in (
            ('funding_raised', 'total_equity_funding', 'disclosed', 'is seeking a target of', 'founder'),
            ('annual_revenue', 'reported_revenue', 'annual reported', 'projected annual', 'seller'),
            ('ebitda', 'reported_ebitda', 'annual reported', 'estimated annual', 'seller'),
            ('transaction_value', 'enterprise_value', 'completed transaction', 'proposed completed transaction', 'seller'),
        ):
            peers, sources = fixture(metric=metric, basis=basis)
            quote = peers[0]['facts'][metric]['source_quote'].replace(old, new)
            peers[0]['facts'][metric]['source_quote'] = quote
            sources[0]['cited_text'] = quote
            self.assertFalse(normalized_peers(peers, sources, role)[0]['facts'][metric]['eligible'])

    def test_employee_counts_do_not_admit_linkedin_associated_profiles(self):
        peers, sources = fixture(values=(10, 20, 30), metric='employee_count', unit='employees', basis='employees')
        self.assertEqual(rows(peers, sources)['employee_count']['median'], 20)
        quote = peers[0]['facts']['employee_count']['source_quote'].replace('employees', 'LinkedIn associated profiles')
        peers[0]['facts']['employee_count']['source_quote'] = quote
        sources[0]['cited_text'] = quote
        self.assertIsNone(rows(peers, sources)['employee_count']['median'])

    def test_completed_rounds_are_not_the_owner_current_fundraising_target(self):
        peers, sources = fixture(metric='latest_round_size', basis='completed_equity_round')
        result = rows(peers, sources, subject={'current_raise': 9999999})
        self.assertIsNone(result['latest_round_size']['value'])
        self.assertIsNone(result['latest_round_size']['percentile'])
        self.assertEqual(result['latest_round_size']['median'], 2000000)
        self.assertEqual(result['current_raise']['value'], 9999999)
        self.assertIsNone(result['current_raise']['median'])

    def test_asking_prices_and_completed_transactions_are_separate_metrics(self):
        peers, sources = fixture(metric='transaction_value', basis='enterprise_value')
        result = rows(peers, sources, 'seller', subject={'asking_price': 9999999})
        self.assertEqual(result['transaction_value']['median'], 2000000)
        self.assertIsNone(result['transaction_value']['value'])
        self.assertIsNone(result['asking_price']['median'])

    def test_repeated_company_does_not_inflate_sample_and_conflicts_exclude_that_company(self):
        peers, sources = fixture()
        repeated = copy.deepcopy(peers[0])
        repeated['company_name'] += ' Inc.'
        self.assertEqual(rows(peers + [repeated], sources)['funding_raised']['peer_values_available'], 3)
        repeated['facts']['funding_raised']['value'] = 5000000
        repeated['facts']['funding_raised']['source_url'] += '/conflict'
        repeated['facts']['funding_raised']['source_quote'] = 'Peer 0 Holdings total equity funding USD 5000000 as of 2025-12-31.'
        sources.append(dict(url=repeated['facts']['funding_raised']['source_url'],
                            cited_text=repeated['facts']['funding_raised']['source_quote']))
        self.assertEqual(rows(peers + [repeated], sources)['funding_raised']['peer_values_available'], 2)

    def test_million_normalization_preserves_the_cited_figure(self):
        peers, sources = fixture()
        quote = peers[0]['facts']['funding_raised']['source_quote'].replace('1000000', '1 million')
        peers[0]['facts']['funding_raised']['source_quote'] = quote
        sources[0]['cited_text'] = quote
        self.assertEqual(rows(peers, sources)['funding_raised']['median'], 2000000)

    def test_dates_company_digits_and_conflicting_amounts_do_not_support_a_figure(self):
        for value, quote in (
            (2025, 'Peer 0 Holdings total equity funding USD 1000000 as of 2025-12-31.'),
            (0, 'Peer 0 Holdings total equity funding USD 1000000 as of 2025-12-31.'),
            (1000000, 'Peer 0 Holdings total equity funding USD 1000000; another company USD 5000000 as of 2025-12-31.'),
        ):
            peers, sources = fixture()
            peers[0]['facts']['funding_raised'].update(value=value, source_quote=quote)
            sources[0]['cited_text'] = quote
            self.assertEqual(rows(peers, sources)['funding_raised']['peer_values_available'], 2)

    def test_unsafe_source_urls_are_dropped_and_multiple_excerpts_are_preserved(self):
        sources = [{'url': 'https://example.com', 'cited_text': 'One'},
                   {'url': 'https://example.com', 'cited_text': 'Two'},
                   {'url': 'javascript:alert(1)', 'cited_text': 'Three'},
                   {'url': 'https://user:password@example.com', 'cited_text': 'Four'}]
        self.assertEqual(source_set(sources)[0]['excerpts'], ['One', 'Two'])
        self.assertEqual(len(source_set(sources)), 1)
        response = SimpleNamespace(content=[SimpleNamespace(type='text', text='{}', citations=[
            SimpleNamespace(url=s['url'], title='Source', cited_text=s['cited_text']) for s in sources])])
        self.assertEqual(extract_text_and_sources(response)[1][0]['excerpts'], ['One', 'Two'])

    def test_external_research_uses_only_admitted_figures_and_deterministic_prose(self):
        peers, sources = fixture()
        response = SimpleNamespace(content=[SimpleNamespace(type='text',
            text=json.dumps({'peers': peers, 'summary': 'The owner is best; median 99999999.', 'cohort_label': 'invented'}),
            citations=[SimpleNamespace(url=s['url'], title=s['title'], cited_text=s['cited_text']) for s in sources])])
        client = mock.Mock()
        client.messages.create.return_value = response
        with mock.patch('zelda_api.peer_benchmark.background_anthropic_client', return_value=client):
            result = external_research('founder', {'company_name': 'Owner', 'sector': 'SaaS', 'stage': 'Seed'})
        self.assertEqual(result['metrics']['funding_raised']['median'], 2000000)
        self.assertNotIn('99999999', result['summary'])
        self.assertEqual(result['cohort_label'], 'Seed SaaS')
        self.assertEqual(result['metrics']['funding_raised']['evidence_version'], EVIDENCE_VERSION)


class FrozenPeerEvidenceViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('p2_owner', password='x')
        self.profile = Application.objects.create(user=self.user, company_name='Owner', founder_name='Owner',
            email='owner@example.com', description='SaaS', sector='SaaS', stage='Seed',
            prior_amount_raised=7771234, field_visibility={field: 'PUBLIC' for field in (
                'prior_amount_raised', 'raising_amount', 'team_size', 'years_in_business',
                'current_revenue', 'sector', 'stage', 'geography')})
        self.peers, self.sources = fixture()

    def report(self, legacy=False):
        subject = {'funding_raised': 7771234}
        return PeerMarketBenchmark.objects.create(user=self.user, role='founder', founder=self.profile,
            subject_name='Owner', status='ready', sharing_enabled=True, subject_snapshot=subject,
            external_peers=self.peers, sources=self.sources, narrative='Unsupported median 987654321',
            external_benchmark=({'funding_raised': {'value': 7771234, 'median': 987654321,
                                'percentile': 100, 'peer_values_available': 20}} if legacy else rows(
                                    self.peers, self.sources, subject=subject)))

    def test_both_pages_recompute_from_frozen_figures_and_show_per_figure_evidence(self):
        report = self.report()
        for name, key in (('peer_market_benchmark_detail', report.pk), ('peer_market_benchmark_share', report.share_token)):
            self.client.force_login(self.user)
            with mock.patch('zelda_api.peer_benchmark.external_research', side_effect=AssertionError('No paid research')):
                response = self.client.get(reverse('accounts:' + name, args=[key]))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, '2000000')
            self.assertContains(response, self.sources[0]['cited_text'])
            self.assertContains(response, self.sources[0]['url'])
            self.assertNotContains(response, '987654321')
            self.assertIsNone(response.context['benchmark'].external_benchmark['funding_raised']['percentile'])
        report.refresh_from_db()
        self.assertEqual(report.narrative, 'Unsupported median 987654321')

    def test_stored_aggregates_cannot_override_the_evidence(self):
        report = self.report()
        report.external_benchmark['funding_raised']['median'] = 987654321
        report.external_benchmark['funding_raised']['groups'] = [{'median': 987654321}]
        prepare_external_report(report)
        self.assertEqual(report.external_benchmark['funding_raised']['median'], 2000000)

    def test_legacy_comparisons_and_prose_are_hidden_without_rewriting_or_research(self):
        report = self.report(legacy=True)
        before = PeerMarketBenchmark.objects.values().get(pk=report.pk)
        for name, key in (('peer_market_benchmark_detail', report.pk), ('peer_market_benchmark_share', report.share_token)):
            self.client.force_login(self.user)
            response = self.client.get(reverse('accounts:' + name, args=[key]))
            self.assertNotContains(response, '987654321')
            self.assertContains(response, 'older snapshot')
            self.assertContains(response, 'Peer 0 Holdings')
            self.assertIsNone(response.context['benchmark'].external_benchmark['funding_raised']['median'])
        self.assertEqual(PeerMarketBenchmark.objects.values().get(pk=report.pk), before)

    def test_subject_revocation_masks_all_group_values_and_citation_excerpts(self):
        report = self.report()
        self.profile.field_visibility = {'prior_amount_raised': 'PRIVATE'}
        self.profile.save(update_fields=['field_visibility'])
        response = self.client.get(reverse('accounts:peer_market_benchmark_share', args=[report.share_token]))
        self.assertNotContains(response, '7771234')
        self.assertNotContains(response, self.sources[0]['cited_text'])
        self.assertContains(response, self.sources[0]['url'])
        row = response.context['benchmark'].external_benchmark['funding_raised']
        self.assertIsNone(row['value'])
        self.assertTrue(all(g['value'] is None and g['percentile'] is None for g in row['groups']))

    def test_private_cohort_hides_external_figures_and_sources(self):
        report = self.report()
        self.profile.field_visibility = {'sector': 'PRIVATE'}
        self.profile.save(update_fields=['field_visibility'])
        response = self.client.get(reverse('accounts:peer_market_benchmark_share', args=[report.share_token]))
        self.assertNotContains(response, 'Peer 0 Holdings')
        self.assertNotContains(response, self.sources[0]['url'])
