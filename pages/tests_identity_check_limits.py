"""
Free identity checks are limited per user, and in total.

Any investor, buyer or staff member can ask for a business's Entity Integrity
check, and nothing counted how many. Each NEW check sends roughly 45 requests
to SEC EDGAR under one declared user agent (up to 40 Form D documents plus the
lookups), fetches the company's website, and asks WHOIS -- so one account could
sustain thousands of SEC requests and degrade Entity Integrity for everyone,
since SEC's fair-access policy applies to the identity, not the account.

Two limits, both counted in the database by accounts/rate_limits.py (never the
cache: production runs several workers and a deploy wipes memory):

  identity_check_user     10 new checks per user per day
  identity_check_global  200 new checks across the platform per hour

Only checks that actually RUN count. A request inside the 7-day reuse window
returns the stored report and releases its slot, the same way a signup that
fails validation releases its own. Staff are exempt, and so is the identity
check that rides along with a paid analysis -- that one already cost a credit.

A refusal is 429 with the same "try again in N minutes" wording the sign-in
limits use, and the check is never started.
"""
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts import rate_limits
from accounts.models import RateLimitEvent
from matchmaking.models import Application, BuyerApplication, InvestorApplication
from matchmaking.tests import _mock_embedding_generation
from zelda_api.entity_verification_models import EntityVerificationReport
from zelda_api.safe_fetch import FetchResult

User = get_user_model()


class _Checks(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.investor_user = User.objects.create_user('rl_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', email='i@t.com', company_name='Harbor Capital',
            investment_focus='Robotics', investment_stage='Seed',
        )
        self.staff = User.objects.create_user('rl_staff', password='x', is_staff=True)
        self.companies = [self._company(n) for n in range(12)]
        self._external()

    def _company(self, n):
        founder_user = User.objects.create_user(f'rl_founder_{n}', password='x')
        return Application.objects.create(
            user=founder_user, company_name=f'Company {n} Inc.', founder_name=f'F{n}', email=f'f{n}@t.com',
            description='test', sector='Robotics', stage='Seed', years_in_business=3,
            company_website=f'https://company{n}.example.com',
        )

    def _external(self):
        """Same shape as pages/tests_entity_identity_check.py: nothing reaches the network."""
        from zelda_api import entity_verification, entity_verification_tasks

        patches = [
            mock.patch.object(entity_verification, 'fetch_public_page', mock.Mock(
                return_value=FetchResult(final_url='https://company.example.com/', status=200, text='<html></html>'))),
            mock.patch.object(entity_verification, 'lookup_domain_creation_date',
                              mock.Mock(return_value=(date(2020, 1, 1), ''))),
            mock.patch('zelda_api.sec_identity.sec_findings'),
            mock.patch.object(entity_verification_tasks.run_entity_check, 'delay',
                              side_effect=lambda report_id: entity_verification_tasks.run_entity_check.run(report_id)),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def _request(self, user, company):
        self.client.force_login(user)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                reverse('zelda_api:identity_check_request', args=[company.id]),
                HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def _use(self, user, count, start=0):
        """Runs `count` new checks, one per distinct company."""
        for company in self.companies[start:start + count]:
            response = self._request(user, company)
            self.assertIn(response.status_code, (200, 202), response.content[:200])


class PerUserLimitTests(_Checks):

    def test_ten_new_checks_a_day_then_the_next_is_refused(self):
        self._use(self.investor_user, 10)
        response = self._request(self.investor_user, self.companies[10])
        self.assertEqual(response.status_code, 429)
        self.assertEqual(EntityVerificationReport.objects.count(), 10)

    def test_the_refusal_says_when_to_come_back(self):
        self._use(self.investor_user, 10)
        response = self._request(self.investor_user, self.companies[10])
        self.assertIn('minute', response.json()['error'].lower())

    def test_a_refused_request_never_starts_a_check(self):
        from zelda_api import entity_verification

        self._use(self.investor_user, 10)
        with mock.patch.object(entity_verification, 'collect_findings') as collect:
            self._request(self.investor_user, self.companies[10])
        collect.assert_not_called()

    def test_another_user_has_their_own_allowance(self):
        self._use(self.investor_user, 10)
        second = User.objects.create_user('rl_investor_two', password='x')
        InvestorApplication.objects.create(
            user=second, full_name='I2', email='i2@t.com', company_name='North Capital',
            investment_focus='Robotics', investment_stage='Seed',
        )
        self.assertIn(self._request(second, self.companies[10]).status_code, (200, 202))

    def test_a_buyer_is_limited_the_same_way(self):
        buyer = User.objects.create_user('rl_buyer', password='x')
        BuyerApplication.objects.create(
            user=buyer, full_name='B', email='b@t.com', company_name='Acquire Co',
            acquisition_thesis='Robotics', budget_min=1, budget_max=2,
        )
        self._use(buyer, 10)
        self.assertEqual(self._request(buyer, self.companies[10]).status_code, 429)

    def test_the_allowance_returns_when_the_day_passes(self):
        self._use(self.investor_user, 10)
        old = timezone.now() - timedelta(days=1, minutes=1)
        RateLimitEvent.objects.filter(scope='identity_check_user').update(created_at=old)
        self.assertIn(self._request(self.investor_user, self.companies[10]).status_code, (200, 202))

    def test_the_count_survives_clearing_the_cache(self):
        self._use(self.investor_user, 10)
        cache.clear()
        self.assertEqual(self._request(self.investor_user, self.companies[10]).status_code, 429)


class ReusedCheckTests(_Checks):

    def test_asking_again_about_the_same_business_costs_nothing(self):
        first = self._request(self.investor_user, self.companies[0])
        self.assertIn(first.status_code, (200, 202))
        for _ in range(20):
            self.assertIn(self._request(self.investor_user, self.companies[0]).status_code, (200, 202))
        self.assertEqual(EntityVerificationReport.objects.count(), 1)
        self.assertEqual(RateLimitEvent.objects.filter(scope='identity_check_user').count(), 1)

    def test_a_reuse_does_not_use_up_the_allowance(self):
        self._use(self.investor_user, 9)
        for _ in range(5):
            self._request(self.investor_user, self.companies[0])  # already checked, reused
        self.assertIn(self._request(self.investor_user, self.companies[9]).status_code, (200, 202))
        self.assertEqual(self._request(self.investor_user, self.companies[10]).status_code, 429)


class GlobalLimitTests(_Checks):

    def _fill_global(self, remaining=0):
        limit, _window = rate_limits.LIMITS['identity_check_global']
        for _ in range(limit - remaining):
            rate_limits.reserve('identity_check_global', 'all')

    def test_the_platform_wide_ceiling_refuses_further_checks(self):
        self._fill_global()
        response = self._request(self.investor_user, self.companies[0])
        self.assertEqual(response.status_code, 429)
        self.assertFalse(EntityVerificationReport.objects.exists())

    def test_a_check_refused_globally_does_not_use_the_users_allowance(self):
        self._fill_global()
        self._request(self.investor_user, self.companies[0])
        self.assertEqual(RateLimitEvent.objects.filter(scope='identity_check_user').count(), 0)

    def test_checks_still_run_while_the_ceiling_has_room(self):
        self._fill_global(remaining=1)
        self.assertIn(self._request(self.investor_user, self.companies[0]).status_code, (200, 202))


class ExemptionTests(_Checks):

    def test_staff_are_not_limited(self):
        self._use(self.staff, 11)
        self.assertEqual(RateLimitEvent.objects.filter(scope='identity_check_user').count(), 0)

    def test_the_identity_check_that_rides_with_a_paid_analysis_is_exempt(self):
        # confirm_analyze_founder_profile already charged the investor a credit
        # for the analysis; the check that comes with it isn't counted again.
        from zelda_api.entity_verification import request_identity_check

        self._use(self.investor_user, 10)
        report, created = request_identity_check(
            self.companies[10], self.investor_user, counts_against_limits=False)
        self.assertTrue(created)
        self.assertIsNotNone(report)


class RetentionTests(TestCase):

    def test_rows_are_kept_longer_than_the_longest_window(self):
        longest = max(window for _limit, window in rate_limits.LIMITS.values())
        self.assertGreater(rate_limits.RETENTION, longest)

    def test_pruning_keeps_attempts_still_inside_the_day_window(self):
        from accounts.tasks import prune_rate_limit_events

        rate_limits.reserve('identity_check_user', 'someone')
        RateLimitEvent.objects.update(created_at=timezone.now() - timedelta(hours=23))
        prune_rate_limit_events()
        self.assertEqual(RateLimitEvent.objects.filter(scope='identity_check_user').count(), 1)
