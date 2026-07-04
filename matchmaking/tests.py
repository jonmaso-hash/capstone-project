from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .models import (
    Application, InvestorApplication, MatchFeedback,
    SellerApplication, BuyerApplication, DealFeedback,
)
from .utils import (
    calculate_rule_based_score, get_blended_match, _is_adjacent_stage,
    calculate_deal_rule_based_score, get_deal_blended_match,
    compute_founder_journey_stage, compute_investor_journey_stage,
    compute_seller_journey_stage, compute_buyer_journey_stage,
)

User = get_user_model()


def _mock_embedding_generation(test_case):
    """
    matchmaking/signals.py auto-generates a real Gemini embedding on every
    Application/InvestorApplication save via post_save — patched out via
    this helper (call from setUp) so the test suite never makes live
    network calls: slow, costs real API quota, and would make CI depend
    on a working GEMINI_API_KEY just to test pure scoring logic.
    """
    patcher = mock.patch('matchmaking.signals.generate_profile_embedding', return_value=[])
    patcher.start()
    test_case.addCleanup(patcher.stop)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RuleBasedScoreTests(TestCase):
    """calculate_rule_based_score: sector (40%) + stage (60%) weighting."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('founder_test', password='x')
        self.investor_user = User.objects.create_user('investor_test', password='x')
        self.investor = InvestorApplication.objects.create(
            user=self.investor_user, full_name='Test Investor', email='i@test.com',
            company_name='Test VC', investment_focus='SaaS, FinTech', investment_stage='Seed',
        )

    def _founder(self, sector='SaaS', stage='Seed'):
        return Application.objects.create(
            user=self.founder_user, company_name='Test Co', founder_name='Founder',
            email='f@test.com', description='A startup.', sector=sector, stage=stage,
        )

    def test_exact_sector_and_stage_match_scores_100(self):
        app = self._founder(sector='SaaS', stage='Seed')
        self.assertEqual(calculate_rule_based_score(app, self.investor), 100)

    def test_partial_sector_match_scores_25(self):
        # 'saas' substring-contained in investor's focus counts as partial, not exact
        app = self._founder(sector='B2B SaaS', stage='Series C')
        score = calculate_rule_based_score(app, self.investor)
        self.assertEqual(score, 25)  # partial sector (25) + no stage match (0)

    def test_no_sector_match_no_stage_match_scores_0(self):
        app = self._founder(sector='HealthTech', stage='Series C')
        self.assertEqual(calculate_rule_based_score(app, self.investor), 0)

    def test_adjacent_stage_gets_partial_credit(self):
        app = self._founder(sector='HealthTech', stage='Pre-Seed')  # adjacent to Seed
        score = calculate_rule_based_score(app, self.investor)
        self.assertEqual(score, 30)  # no sector (0) + adjacent stage (30)

    def test_is_adjacent_stage_symmetric_lookup(self):
        self.assertTrue(_is_adjacent_stage('seed', 'pre-seed'))
        self.assertTrue(_is_adjacent_stage('seed', 'series a'))
        self.assertFalse(_is_adjacent_stage('seed', 'series c'))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class BlendedMatchTests(TestCase):
    """get_blended_match: rule*0.7 + ai*0.3, plus MatchFeedback thumbs nudge."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('founder_test', password='x')
        self.investor_user = User.objects.create_user('investor_test', password='x')
        self.investor = InvestorApplication.objects.create(
            user=self.investor_user, full_name='Test Investor', email='i@test.com',
            company_name='Test VC', investment_focus='SaaS', investment_stage='Seed',
        )
        self.app = Application.objects.create(
            user=self.founder_user, company_name='Test Co', founder_name='Founder',
            email='f@test.com', description='A startup.', sector='SaaS', stage='Seed',
        )

    def test_blend_with_no_feedback(self):
        # rule=100, ai=50 -> 100*0.7 + 50*0.3 = 85.0
        score = get_blended_match(ai_score=50, rule_score=100, application=self.app, investor=self.investor)
        self.assertEqual(score, 85.0)

    def test_thumbs_up_adds_15_capped_at_100(self):
        MatchFeedback.objects.create(user=self.investor_user, application=self.app, investor=self.investor, vote=1)
        score = get_blended_match(ai_score=50, rule_score=100, application=self.app, investor=self.investor)
        self.assertEqual(score, 100)  # 85 + 15 = 100, capped

    def test_thumbs_down_halves_score(self):
        MatchFeedback.objects.create(user=self.investor_user, application=self.app, investor=self.investor, vote=-1)
        score = get_blended_match(ai_score=50, rule_score=100, application=self.app, investor=self.investor)
        self.assertEqual(score, 42.5)  # 85 * 0.5


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DealRuleBasedScoreTests(TestCase):
    """calculate_deal_rule_based_score: industry (40%) + deal size fit (35%) + structure (25%)."""

    def setUp(self):
        self.seller_user = User.objects.create_user('seller_test', password='x')
        self.buyer_user = User.objects.create_user('buyer_test', password='x')

    def _seller(self, industry='Manufacturing', asking_price=1_000_000, deal_structure='ASSET_SALE'):
        return SellerApplication.objects.create(
            user=self.seller_user, company_name='Test Widgets', seller_name='Seller',
            email='s@test.com', description='A business.', industry=industry,
            asking_price=asking_price, deal_structure=deal_structure,
        )

    def _buyer(self, thesis='We acquire manufacturing businesses', budget_min=500_000,
               budget_max=1_500_000, preferred_structure='ASSET_SALE'):
        return BuyerApplication.objects.create(
            user=self.buyer_user, full_name='Buyer', email='b@test.com',
            company_name='Acquisitions LLC', acquisition_thesis=thesis,
            budget_min=budget_min, budget_max=budget_max,
            preferred_deal_structure=preferred_structure,
        )

    def test_perfect_match_scores_100(self):
        seller = self._seller()
        buyer = self._buyer()
        self.assertEqual(calculate_deal_rule_based_score(seller, buyer), 100)

    def test_no_industry_no_size_fit_no_structure_match_scores_0(self):
        seller = self._seller(industry='Restaurants', asking_price=10_000_000, deal_structure='STOCK_SALE')
        buyer = self._buyer(thesis='We acquire manufacturing businesses',
                             budget_min=500_000, budget_max=1_500_000,
                             preferred_structure='ASSET_SALE')
        self.assertEqual(calculate_deal_rule_based_score(seller, buyer), 0)

    def test_price_within_20_percent_of_budget_gets_partial_credit(self):
        # budget_max=1,000,000; asking_price=1,100,000 -> 10% over, within 20% band
        seller = self._seller(asking_price=1_100_000)
        buyer = self._buyer(budget_min=500_000, budget_max=1_000_000)
        score = calculate_deal_rule_based_score(seller, buyer)
        self.assertEqual(score, 40 + 15 + 25)  # industry(40) + partial size(15) + structure(25)

    def test_buyer_no_preference_always_gets_structure_credit(self):
        seller = self._seller(deal_structure='MERGER')
        buyer = self._buyer(preferred_structure='NO_PREFERENCE')
        score = calculate_deal_rule_based_score(seller, buyer)
        self.assertEqual(score, 40 + 35 + 25)  # full marks despite structure mismatch

    def test_seller_open_structure_gets_partial_credit_on_mismatch(self):
        seller = self._seller(deal_structure='OPEN')
        buyer = self._buyer(preferred_structure='STOCK_SALE')
        score = calculate_deal_rule_based_score(seller, buyer)
        self.assertEqual(score, 40 + 35 + 15)  # full industry+size, partial structure


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DealBlendedMatchTests(TestCase):
    """get_deal_blended_match: same shape as get_blended_match but for DealFeedback."""

    def setUp(self):
        self.seller_user = User.objects.create_user('seller_test', password='x')
        self.buyer_user = User.objects.create_user('buyer_test', password='x')
        self.seller = SellerApplication.objects.create(
            user=self.seller_user, company_name='Test Widgets', seller_name='Seller',
            email='s@test.com', description='A business.', industry='Manufacturing',
            asking_price=1_000_000, deal_structure='ASSET_SALE',
        )
        self.buyer = BuyerApplication.objects.create(
            user=self.buyer_user, full_name='Buyer', email='b@test.com',
            company_name='Acquisitions LLC', acquisition_thesis='We acquire manufacturing businesses',
            budget_min=500_000, budget_max=1_500_000, preferred_deal_structure='ASSET_SALE',
        )

    def test_thumbs_up_adds_15_capped_at_100(self):
        DealFeedback.objects.create(user=self.buyer_user, seller=self.seller, buyer=self.buyer, vote=1)
        score = get_deal_blended_match(ai_score=50, rule_score=100, seller=self.seller, buyer=self.buyer)
        self.assertEqual(score, 100)

    def test_thumbs_down_halves_score(self):
        DealFeedback.objects.create(user=self.buyer_user, seller=self.seller, buyer=self.buyer, vote=-1)
        score = get_deal_blended_match(ai_score=50, rule_score=100, seller=self.seller, buyer=self.buyer)
        self.assertEqual(score, 42.5)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class JourneyStageTests(TestCase):
    """
    compute_*_journey_stage: red (no profile) -> yellow (incomplete) ->
    green (complete). Covers the guided Zelda icon's stage computation for
    all four roles.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('journey_test', password='x')

    def test_founder_no_profile_is_red(self):
        stage = compute_founder_journey_stage(self.user)
        self.assertEqual(stage['stage_color'], 'red')

    def test_founder_no_pitch_asset_is_yellow(self):
        Application.objects.create(
            user=self.user, company_name='Test Co', founder_name='Founder',
            email='f@test.com', description='A startup.',
        )
        stage = compute_founder_journey_stage(self.user)
        self.assertEqual(stage['stage_color'], 'yellow')

    def test_founder_with_pitch_deck_is_green(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        Application.objects.create(
            user=self.user, company_name='Test Co', founder_name='Founder',
            email='f@test.com', description='A startup.',
            pitch_deck=SimpleUploadedFile('deck.pdf', b'x' * 100, content_type='application/pdf'),
        )
        stage = compute_founder_journey_stage(self.user)
        self.assertEqual(stage['stage_color'], 'green')

    def test_investor_no_profile_is_red(self):
        stage = compute_investor_journey_stage(self.user)
        self.assertEqual(stage['stage_color'], 'red')

    def test_investor_incomplete_mandate_is_yellow(self):
        InvestorApplication.objects.create(
            user=self.user, full_name='', email='i@test.com',
            company_name='Test VC', investment_focus='SaaS', investment_stage='Seed',
        )
        stage = compute_investor_journey_stage(self.user)
        self.assertEqual(stage['stage_color'], 'yellow')

    def test_investor_complete_mandate_is_green(self):
        InvestorApplication.objects.create(
            user=self.user, full_name='Investor Name', email='i@test.com', phone='555-0100',
            company_name='Test VC', website='https://test.vc', linkedin_url='https://linkedin.com/x',
            location='SF', investment_focus='SaaS', investment_stage='Seed',
        )
        stage = compute_investor_journey_stage(self.user)
        self.assertEqual(stage['stage_color'], 'green')

    def test_seller_no_profile_is_red(self):
        stage = compute_seller_journey_stage(self.user)
        self.assertEqual(stage['stage_color'], 'red')

    def test_seller_no_cim_is_yellow(self):
        SellerApplication.objects.create(
            user=self.user, company_name='Test Widgets', seller_name='Seller',
            email='s@test.com', description='A business.',
        )
        stage = compute_seller_journey_stage(self.user)
        self.assertEqual(stage['stage_color'], 'yellow')

    def test_seller_with_cim_is_green(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        SellerApplication.objects.create(
            user=self.user, company_name='Test Widgets', seller_name='Seller',
            email='s@test.com', description='A business.',
            cim_document=SimpleUploadedFile('cim.pdf', b'x' * 100, content_type='application/pdf'),
        )
        stage = compute_seller_journey_stage(self.user)
        self.assertEqual(stage['stage_color'], 'green')

    def test_buyer_no_profile_is_red(self):
        stage = compute_buyer_journey_stage(self.user)
        self.assertEqual(stage['stage_color'], 'red')

    def test_buyer_complete_mandate_is_green(self):
        BuyerApplication.objects.create(
            user=self.user, full_name='Buyer', email='b@test.com', phone='555-0100',
            company_name='Acquisitions LLC', website='https://test.com',
            acquisition_thesis='We acquire things.', budget_min=100, budget_max=200,
        )
        stage = compute_buyer_journey_stage(self.user)
        self.assertEqual(stage['stage_color'], 'green')


class CeleryRetryRegressionTests(TestCase):
    """
    Regression coverage for a real gap fixed this session: send_weekly_digests,
    snapshot_investor_predictions, and snapshot_buyer_predictions had no retry
    logic at all — a single transient failure (e.g. a DB hiccup) would drop
    that whole run silently, with only a log line nobody was watching.
    Confirms the fix: each task now retries with backoff and, once retries
    are exhausted, returns a clean error dict rather than crashing uncaught.
    """

    def _assert_bound_with_retries(self, task):
        # task.bind is a Task *method* present on every Celery task regardless
        # of whether bind=True was passed to the decorator — checking for its
        # presence would pass even if bind=True were removed. The real signal
        # that bind=True is in effect is that Celery passes the task instance
        # as the wrapped function's first positional arg (conventionally `self`).
        first_param = task.__wrapped__.__code__.co_varnames[0]
        self.assertEqual(first_param, 'self')
        self.assertEqual(task.max_retries, 3)

    def test_send_weekly_digests_is_bound_with_retries_configured(self):
        from .tasks import send_weekly_digests
        self._assert_bound_with_retries(send_weekly_digests)

    def test_snapshot_investor_predictions_is_bound_with_retries_configured(self):
        from .tasks import snapshot_investor_predictions
        self._assert_bound_with_retries(snapshot_investor_predictions)

    def test_snapshot_buyer_predictions_is_bound_with_retries_configured(self):
        from .tasks import snapshot_buyer_predictions
        self._assert_bound_with_retries(snapshot_buyer_predictions)

    def test_send_weekly_digests_exhausts_retries_and_returns_error_dict(self):
        """
        A body that always raises should retry exactly max_retries times
        (via Celery's synchronous .apply(), which needs no real broker),
        then return a clean error dict instead of an uncaught exception.
        """
        from .tasks import send_weekly_digests
        with mock.patch('matchmaking.tasks._send_weekly_digests_body', side_effect=Exception('simulated DB error')):
            result = send_weekly_digests.apply().result

        self.assertEqual(result['status'], 'error')
        self.assertTrue(result['retries_exhausted'])
        self.assertIn('simulated DB error', result['error'])
