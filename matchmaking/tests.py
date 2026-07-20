import json
import tempfile
import uuid
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    Application, InvestorApplication, MatchFeedback,
    SellerApplication, BuyerApplication, DealFeedback,
    MatchTrainingExample, log_training_example, Connection,
    PitchVideoComment, InvestorInterestEvent, AcquisitionInterestEvent,
)
from .utils import (
    calculate_rule_based_score, get_blended_match, _is_adjacent_stage,
    calculate_deal_rule_based_score, get_deal_blended_match,
    compute_founder_journey_stage, compute_investor_journey_stage,
    compute_seller_journey_stage, compute_buyer_journey_stage,
    passes_hard_filters, get_weighted_chunk_score,
)

User = get_user_model()


def _mock_embedding_generation(test_case):
    """
    matchmaking/signals.py auto-generates a real embedding (local
    sentence-transformers model, matchmaking/services/ai_utils.py) on every
    Application/InvestorApplication save via post_save — patched out via
    this helper (call from setUp) so the test suite never pays for loading
    the ML model: slow on first call and irrelevant to testing pure scoring
    logic.
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

    @staticmethod
    def _checklist_done(stage, label):
        return next(item['done'] for item in stage['checklist'] if item['label'] == label)

    def test_founder_business_verification_item_reflects_is_verified(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        app = Application.objects.create(
            user=self.user, company_name='Test Co', founder_name='Founder',
            email='f@test.com', description='A startup.',
            pitch_deck=SimpleUploadedFile('deck.pdf', b'x' * 100, content_type='application/pdf'),
        )
        stage = compute_founder_journey_stage(self.user)
        self.assertFalse(self._checklist_done(stage, 'Verify your business email'))

        app.is_verified = True
        app.save(update_fields=['is_verified'])
        stage = compute_founder_journey_stage(self.user)
        self.assertTrue(self._checklist_done(stage, 'Verify your business email'))

    def test_investor_business_verification_item_reflects_is_verified(self):
        investor = InvestorApplication.objects.create(
            user=self.user, full_name='Investor Name', email='i@test.com', phone='555-0100',
            company_name='Test VC', website='https://test.vc', linkedin_url='https://linkedin.com/x',
            location='SF', investment_focus='SaaS', investment_stage='Seed',
        )
        stage = compute_investor_journey_stage(self.user)
        self.assertFalse(self._checklist_done(stage, 'Verify your business email'))

        investor.is_verified = True
        investor.save(update_fields=['is_verified'])
        stage = compute_investor_journey_stage(self.user)
        self.assertTrue(self._checklist_done(stage, 'Verify your business email'))

    def test_seller_business_verification_item_reflects_is_verified(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        seller = SellerApplication.objects.create(
            user=self.user, company_name='Test Widgets', seller_name='Seller',
            email='s@test.com', description='A business.',
            cim_document=SimpleUploadedFile('cim.pdf', b'x' * 100, content_type='application/pdf'),
        )
        stage = compute_seller_journey_stage(self.user)
        self.assertFalse(self._checklist_done(stage, 'Verify your business email'))

        seller.is_verified = True
        seller.save(update_fields=['is_verified'])
        stage = compute_seller_journey_stage(self.user)
        self.assertTrue(self._checklist_done(stage, 'Verify your business email'))

    def test_buyer_business_verification_item_reflects_is_verified(self):
        buyer = BuyerApplication.objects.create(
            user=self.user, full_name='Buyer', email='b@test.com', phone='555-0100',
            company_name='Acquisitions LLC', website='https://test.com',
            acquisition_thesis='We acquire things.', budget_min=100, budget_max=200,
        )
        stage = compute_buyer_journey_stage(self.user)
        self.assertFalse(self._checklist_done(stage, 'Verify your business email'))

        buyer.is_verified = True
        buyer.save(update_fields=['is_verified'])
        stage = compute_buyer_journey_stage(self.user)
        self.assertTrue(self._checklist_done(stage, 'Verify your business email'))


class ProfileStrengthTests(TestCase):
    """
    compute_profile_strength buckets a checklist's done/total ratio into a
    word label (never a raw percentage — see matchmaking/journey_actions.py).
    """

    def _checklist(self, done_flags):
        return [{'label': f'item-{i}', 'done': d} for i, d in enumerate(done_flags)]

    def test_empty_checklist_is_just_started(self):
        from .journey_actions import compute_profile_strength
        result = compute_profile_strength([])
        self.assertEqual(result['label'], 'Just Started')
        self.assertEqual(result['ratio'], 0.0)

    def test_all_done_is_strong(self):
        from .journey_actions import compute_profile_strength
        result = compute_profile_strength(self._checklist([True, True, True]))
        self.assertEqual(result['label'], 'Strong')
        self.assertEqual(result['ratio'], 1.0)

    def test_majority_done_is_good(self):
        from .journey_actions import compute_profile_strength
        result = compute_profile_strength(self._checklist([True, True, True, False, False]))
        self.assertEqual(result['label'], 'Good')

    def test_minority_done_is_building(self):
        from .journey_actions import compute_profile_strength
        result = compute_profile_strength(self._checklist([True, False, False, False, False]))
        self.assertEqual(result['label'], 'Building')

    def test_nothing_done_is_just_started(self):
        from .journey_actions import compute_profile_strength
        result = compute_profile_strength(self._checklist([False, False, False]))
        self.assertEqual(result['label'], 'Just Started')
        self.assertEqual(result['ratio'], 0.0)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class HighlightFeatureTests(TestCase):
    """
    Founder/Seller Premium's monthly 24-hour highlight boost (replaces the
    old "full counterpart identity in digest" perk — see matchmaking/
    digest.py's module docstring). Covers the model mechanics
    (is_highlighted/can_activate_highlight/activate_highlight) and the two
    activation views.
    """

    def setUp(self):
        _mock_embedding_generation(self)

    def _founder(self, username, **kwargs):
        u = User.objects.create_user(username, password='x')
        defaults = dict(
            company_name=f'{username}Co', founder_name='F', email=f'{username}@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        defaults.update(kwargs)
        return Application.objects.create(user=u, **defaults)

    def _seller(self, username, **kwargs):
        u = User.objects.create_user(username, password='x')
        defaults = dict(
            company_name=f'{username}Co', seller_name='S', email=f'{username}@t.com',
            description='test', industry='Manufacturing',
        )
        defaults.update(kwargs)
        return SellerApplication.objects.create(user=u, **defaults)

    # -- model mechanics (Application; SellerApplication mirrors it) --

    def test_never_activated_is_not_highlighted(self):
        app = self._founder('neverhl')
        self.assertFalse(app.is_highlighted)

    def test_recently_activated_is_highlighted(self):
        app = self._founder('recenthl', last_highlight_at=timezone.now())
        self.assertTrue(app.is_highlighted)

    def test_highlight_older_than_24h_is_not_highlighted(self):
        app = self._founder('stalehl', last_highlight_at=timezone.now() - timedelta(hours=25))
        self.assertFalse(app.is_highlighted)

    def test_free_user_cannot_activate_highlight(self):
        app = self._founder('freehl', is_premium=False)
        self.assertFalse(app.can_activate_highlight)

    def test_premium_user_with_no_prior_highlight_can_activate(self):
        app = self._founder('premiumhl', is_premium=True)
        self.assertTrue(app.can_activate_highlight)

    def test_premium_user_within_cooldown_cannot_reactivate(self):
        app = self._founder('cooldownhl', is_premium=True, last_highlight_at=timezone.now() - timedelta(days=10))
        self.assertFalse(app.can_activate_highlight)

    def test_premium_user_past_cooldown_can_reactivate(self):
        app = self._founder('pastcooldownhl', is_premium=True, last_highlight_at=timezone.now() - timedelta(days=31))
        self.assertTrue(app.can_activate_highlight)

    def test_activate_highlight_sets_timestamp_and_persists(self):
        app = self._founder('activatehl', is_premium=True)
        app.activate_highlight()
        app.refresh_from_db()
        self.assertTrue(app.is_highlighted)

    # -- founder activation view --

    def test_free_founder_cannot_activate_via_view(self):
        app = self._founder('viewfreehl', is_premium=False)
        self.client.force_login(app.user)
        response = self.client.post(reverse('matchmaking:activate_founder_highlight'), follow=True)
        self.assertContains(response, "Founder Premium perk")
        app.refresh_from_db()
        self.assertFalse(app.is_highlighted)

    def test_premium_founder_activates_via_view(self):
        app = self._founder('viewpremiumhl', is_premium=True)
        self.client.force_login(app.user)
        response = self.client.post(reverse('matchmaking:activate_founder_highlight'), follow=True)
        self.assertContains(response, "highlighted for the next 24 hours")
        app.refresh_from_db()
        self.assertTrue(app.is_highlighted)

    def test_founder_within_cooldown_blocked_via_view(self):
        app = self._founder('viewcooldownhl', is_premium=True, last_highlight_at=timezone.now() - timedelta(days=5))
        self.client.force_login(app.user)
        response = self.client.post(reverse('matchmaking:activate_founder_highlight'), follow=True)
        self.assertContains(response, "already used this month")

    # -- seller activation view (mirrors founder) --

    def test_premium_seller_activates_via_view(self):
        seller = self._seller('sellerviewhl', is_premium=True)
        self.client.force_login(seller.user)
        response = self.client.post(reverse('matchmaking:activate_seller_highlight'), follow=True)
        self.assertContains(response, "highlighted for the next 24 hours")
        seller.refresh_from_db()
        self.assertTrue(seller.is_highlighted)

    def test_free_seller_cannot_activate_via_view(self):
        seller = self._seller('sellerviewfreehl', is_premium=False)
        self.client.force_login(seller.user)
        response = self.client.post(reverse('matchmaking:activate_seller_highlight'), follow=True)
        self.assertContains(response, "Seller Premium perk")
        seller.refresh_from_db()
        self.assertFalse(seller.is_highlighted)

    # -- bulletin board sort order --

    def test_highlighted_founder_ranks_above_featured_on_bulletin_board(self):
        self._founder('bbfeatured', is_staff_featured=True, is_private=False)
        self._founder('bbhighlighted', is_premium=True, last_highlight_at=timezone.now(), is_private=False)

        response = self.client.get(reverse('matchmaking:bulletin_board'))
        usernames = [p.user.username for p in response.context['pitches']]
        self.assertEqual(usernames[0], 'bbhighlighted')

    def test_highlighted_seller_ranks_above_featured_on_acquisition_board(self):
        self._seller('abfeatured', is_staff_featured=True, is_private=False)
        self._seller('abhighlighted', is_premium=True, last_highlight_at=timezone.now(), is_private=False)

        response = self.client.get(reverse('matchmaking:acquisition_bulletin_board'))
        usernames = [l.user.username for l in response.context['listings']]
        self.assertEqual(usernames[0], 'abhighlighted')

    # -- blog / jobs badge properties --

    def test_article_is_highlighted_reflects_founder_highlight(self):
        from blog.models import Article
        app = self._founder('blogauthorhl', is_premium=True, last_highlight_at=timezone.now())
        article = Article.objects.create(author=app.user, title='Post', body='body text')
        self.assertTrue(article.is_highlighted)

    def test_article_not_highlighted_without_founder_profile(self):
        from blog.models import Article
        plain_user = User.objects.create_user('bloguserplain', password='x')
        article = Article.objects.create(author=plain_user, title='Post', body='body text')
        self.assertFalse(article.is_highlighted)

    def test_joblisting_is_highlighted_reflects_founder_highlight(self):
        from jobs.models import JobListing
        app = self._founder('jobposterhl', is_premium=True, last_highlight_at=timezone.now())
        job = JobListing.objects.create(
            poster=app.user, company_name='TestCo', title='Engineer', description='job',
        )
        self.assertTrue(job.is_highlighted)


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

    def test_exhausted_retries_writes_a_failed_task_log(self):
        """
        Dead-letter coverage: once retries are exhausted, the failure must
        be recorded in ops.FailedTaskLog (not just logged) so it's visible
        and requeueable from the ops dashboard.
        """
        from ops.models import FailedTaskLog
        from .tasks import send_weekly_digests

        with mock.patch('matchmaking.tasks._send_weekly_digests_body', side_effect=Exception('simulated DB error')):
            send_weekly_digests.apply()

        failure = FailedTaskLog.objects.get()
        self.assertEqual(failure.task_name, 'matchmaking.tasks.send_weekly_digests')
        self.assertIn('simulated DB error', failure.exception_message)


class EmbeddingAndSparseSimilarityCacheTests(TestCase):
    """generate_profile_embedding/calculate_sparse_similarity cache hit-vs-miss behavior."""

    def setUp(self):
        cache.clear()

    def test_embedding_cache_hit_skips_the_model_call(self):
        from matchmaking.services import ai_engine

        with mock.patch.object(ai_engine, 'generate_vector') as mock_generate_vector:
            mock_generate_vector.return_value.tolist.return_value = [0.1, 0.2, 0.3]

            first = ai_engine.generate_profile_embedding("a unique test description")
            second = ai_engine.generate_profile_embedding("a unique test description")

            self.assertEqual(first, [0.1, 0.2, 0.3])
            self.assertEqual(second, [0.1, 0.2, 0.3])
            # Second call should be a pure cache hit — model only invoked once.
            self.assertEqual(mock_generate_vector.call_count, 1)

    def test_different_text_is_a_cache_miss(self):
        from matchmaking.services import ai_engine

        with mock.patch.object(ai_engine, 'generate_vector') as mock_generate_vector:
            mock_generate_vector.return_value.tolist.return_value = [0.4, 0.5]

            ai_engine.generate_profile_embedding("text one")
            ai_engine.generate_profile_embedding("text two")

            self.assertEqual(mock_generate_vector.call_count, 2)

    def test_sparse_similarity_cache_hit_skips_recomputation(self):
        from matchmaking.services import ai_engine

        with mock.patch('sklearn.feature_extraction.text.TfidfVectorizer') as mock_vectorizer_cls:
            mock_vectorizer = mock.MagicMock()
            mock_vectorizer_cls.return_value = mock_vectorizer
            mock_vectorizer.fit_transform.return_value = mock.MagicMock()

            with mock.patch('sklearn.metrics.pairwise.cosine_similarity', return_value=[[0.42]]):
                first = ai_engine.calculate_sparse_similarity("SaaS focused fund", "SaaS startup pitch")
                second = ai_engine.calculate_sparse_similarity("SaaS focused fund", "SaaS startup pitch")

            self.assertEqual(first, 0.42)
            self.assertEqual(second, 0.42)
            self.assertEqual(mock_vectorizer_cls.call_count, 1)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class HardFilterCacheCorrectnessTests(TestCase):
    """passes_hard_filters caching: same inputs hit the cache, changed inputs recompute."""

    def setUp(self):
        cache.clear()
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('hfc_founder', password='x')
        self.investor_user = User.objects.create_user('hfc_investor', password='x')
        self.investor = InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', email='i@t.com', company_name='ICo',
            investment_focus='SaaS', investment_stage='Seed', ticket_size_min=100000, ticket_size_max=500000,
        )
        self.app = Application.objects.create(
            user=self.founder_user, company_name='FCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed', raising_amount=250000,
        )

    def test_same_inputs_return_cached_result(self):
        first = passes_hard_filters(self.app, self.investor)
        with mock.patch('matchmaking.utils._compute_hard_filters') as mock_compute:
            second = passes_hard_filters(self.app, self.investor)
            mock_compute.assert_not_called()  # second call must be a pure cache hit
        self.assertEqual(first, second)
        self.assertTrue(first)

    def test_changed_raising_amount_produces_a_different_cache_key_and_result(self):
        self.assertTrue(passes_hard_filters(self.app, self.investor))

        self.app.raising_amount = 999999  # now outside the investor's ticket range
        self.app.save(update_fields=['raising_amount'])

        # New raising_amount means a new cache key — must recompute, not
        # return the stale cached True.
        self.assertFalse(passes_hard_filters(self.app, self.investor))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class LogPageEventTests(TestCase):
    """log_page_event: fires on first view, dedupes same session+type+day."""

    def setUp(self):
        from django.test import RequestFactory
        self.factory = RequestFactory()

    def _request_with_session(self):
        from django.contrib.sessions.middleware import SessionMiddleware
        request = self.factory.get('/')
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        return request

    def test_first_call_creates_a_row(self):
        from .models import PageEvent, log_page_event
        request = self._request_with_session()

        log_page_event(request, 'landing_view')

        self.assertEqual(PageEvent.objects.filter(event_type='landing_view').count(), 1)

    def test_repeat_call_same_session_same_day_is_deduped(self):
        from .models import PageEvent, log_page_event
        request = self._request_with_session()

        log_page_event(request, 'landing_view')
        log_page_event(request, 'landing_view')
        log_page_event(request, 'landing_view')

        self.assertEqual(PageEvent.objects.filter(event_type='landing_view').count(), 1)

    def test_different_session_is_not_deduped(self):
        from .models import PageEvent, log_page_event
        request_a = self._request_with_session()
        request_b = self._request_with_session()

        log_page_event(request_a, 'landing_view')
        log_page_event(request_b, 'landing_view')

        self.assertEqual(PageEvent.objects.filter(event_type='landing_view').count(), 2)

    def test_role_and_user_are_recorded(self):
        from .models import PageEvent, log_page_event
        request = self._request_with_session()
        user = User.objects.create_user('funnel_test_user', password='x')

        log_page_event(request, 'signup_completed', role='founder', user=user)

        event = PageEvent.objects.get(event_type='signup_completed')
        self.assertEqual(event.role, 'founder')
        self.assertEqual(event.user, user)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FunnelAnalyticsTests(TestCase):
    """get_founder_investor_funnel/get_seller_buyer_funnel: each stage count
    reflects the underlying data exactly, against known fixtures."""

    def setUp(self):
        _mock_embedding_generation(self)

    def test_founder_stage_counts_match_fixtures(self):
        from .models import Application, InvestorApplication, Connection, InvestorInterestEvent
        from .analytics import get_founder_investor_funnel

        founder_user = User.objects.create_user('funnel_founder', password='x')
        founder = Application.objects.create(
            user=founder_user, founder_name='F', email='f@t.com', company_name='FCo',
            sector='SaaS', stage='Seed', description='test', is_private=False,
        )
        investor_user = User.objects.create_user('funnel_investor', password='x')
        investor = InvestorApplication.objects.create(
            user=investor_user, full_name='I', email='i@t.com', company_name='ICo',
            investment_focus='SaaS', investment_stage='Seed', is_private=False,
        )
        InvestorInterestEvent.objects.create(investor=investor_user, founder=founder, event_type='view')
        Connection.objects.create(investor=investor, founder=founder, status='ACCEPTED', initiated_by='INVESTOR')

        funnel = get_founder_investor_funnel()
        by_key = {row['key']: row['count'] for row in funnel['founder']}

        self.assertEqual(by_key['signup_completed'], 1)
        self.assertEqual(by_key['matched'], 1)
        self.assertEqual(by_key['intro_sent'], 1)
        self.assertEqual(by_key['intro_accepted'], 1)
        self.assertEqual(by_key['deal_room'], 0)
        self.assertEqual(by_key['premium'], 0)

    def test_seller_stage_counts_match_fixtures(self):
        from .models import SellerApplication, BuyerApplication, AcquisitionConnection
        from .analytics import get_seller_buyer_funnel

        seller_user = User.objects.create_user('funnel_seller', password='x')
        SellerApplication.objects.create(
            user=seller_user, seller_name='S', email='s@t.com', company_name='SCo',
            description='test biz', is_premium=True,
        )
        buyer_user = User.objects.create_user('funnel_buyer', password='x')
        BuyerApplication.objects.create(
            user=buyer_user, full_name='B', email='b@t.com', company_name='BCo',
            acquisition_thesis='test',
        )

        funnel = get_seller_buyer_funnel()
        by_key = {row['key']: row['count'] for row in funnel['seller']}

        self.assertEqual(by_key['signup_completed'], 1)
        self.assertEqual(by_key['intro_sent'], 0)
        self.assertEqual(by_key['premium'], 1)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PassesHardFiltersTests(TestCase):
    """passes_hard_filters: excludes on ticket-size/stage mismatch, fails open when unset."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('hf_founder', password='x')
        self.investor_user = User.objects.create_user('hf_investor', password='x')

    def _investor(self, ticket_min=None, ticket_max=None, stage=''):
        return InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', email='i@t.com', company_name='ICo',
            investment_focus='SaaS', investment_stage=stage,
            ticket_size_min=ticket_min, ticket_size_max=ticket_max,
        )

    def _founder(self, raising_amount=500000, stage='Seed'):
        return Application.objects.create(
            user=self.founder_user, company_name='FCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage=stage, raising_amount=raising_amount,
        )

    def test_no_constraints_declared_passes(self):
        investor = self._investor()
        app = self._founder(raising_amount=10_000_000, stage='Series C')
        self.assertTrue(passes_hard_filters(app, investor))

    def test_raising_amount_below_ticket_min_excluded(self):
        investor = self._investor(ticket_min=250000, ticket_max=1000000)
        app = self._founder(raising_amount=50000)
        self.assertFalse(passes_hard_filters(app, investor))

    def test_raising_amount_above_ticket_max_excluded(self):
        investor = self._investor(ticket_min=250000, ticket_max=1000000)
        app = self._founder(raising_amount=5_000_000)
        self.assertFalse(passes_hard_filters(app, investor))

    def test_raising_amount_within_range_passes(self):
        investor = self._investor(ticket_min=250000, ticket_max=1000000)
        app = self._founder(raising_amount=500000)
        self.assertTrue(passes_hard_filters(app, investor))

    def test_stage_mismatch_excluded(self):
        investor = self._investor(stage='Seed')
        app = self._founder(stage='Series C')
        self.assertFalse(passes_hard_filters(app, investor))

    def test_adjacent_stage_passes(self):
        investor = self._investor(stage='Seed')
        app = self._founder(stage='Pre-Seed')
        self.assertTrue(passes_hard_filters(app, investor))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class BlendedMatchSparseChunkTests(TestCase):
    """get_blended_match's new sparse_score term and chunk-score fallback behavior."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('bm2_founder', password='x')
        self.investor_user = User.objects.create_user('bm2_investor', password='x')
        self.investor = InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', email='i@t.com', company_name='ICo',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.app = Application.objects.create(
            user=self.founder_user, company_name='FCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )

    def test_sparse_score_none_preserves_old_70_30_blend(self):
        score = get_blended_match(ai_score=50, rule_score=100, application=self.app, investor=self.investor)
        self.assertEqual(score, 85.0)  # 100*0.7 + 50*0.3, unchanged from before this feature

    def test_sparse_score_switches_to_3_way_blend(self):
        # rule=100, ai=50, sparse=20 -> 100*0.5 + 50*0.25 + 20*0.25 = 67.5
        score = get_blended_match(
            ai_score=50, rule_score=100, application=self.app, investor=self.investor, sparse_score=20,
        )
        self.assertEqual(score, 67.5)

    def test_chunk_score_none_when_no_chunk_vectors_present(self):
        self.assertIsNone(get_weighted_chunk_score(self.app, self.investor))

    def test_chunk_score_falls_back_to_ai_score_when_absent(self):
        # No chunk vectors set on either side -> get_blended_match should use
        # the passed-in whole-profile ai_score untouched, not silently zero it.
        score_with_chunks_absent = get_blended_match(
            ai_score=50, rule_score=100, application=self.app, investor=self.investor,
        )
        self.assertEqual(score_with_chunks_absent, 85.0)

    def test_chunk_score_used_when_vectors_present_on_both_sides(self):
        self.app.problem_solution_vector = [1.0, 0.0]
        self.app.save(update_fields=['problem_solution_vector'])
        self.investor.thesis_vector = [1.0, 0.0]
        self.investor.weight_problem_solution = 1.0
        self.investor.weight_capital_plan = 0.0
        self.investor.weight_market_context = 0.0
        self.investor.save(update_fields=['thesis_vector', 'weight_problem_solution', 'weight_capital_plan', 'weight_market_context'])

        chunk_score = get_weighted_chunk_score(self.app, self.investor)
        self.assertIsNotNone(chunk_score)
        self.assertAlmostEqual(chunk_score, 100.0, places=2)  # identical vectors -> cosine sim 1.0 -> 100

        # get_blended_match should transparently swap in the chunk score in place of ai_score=50
        score = get_blended_match(ai_score=50, rule_score=0, application=self.app, investor=self.investor)
        self.assertAlmostEqual(score, 30.0, places=1)  # rule*0.7 + chunk_score(100)*0.3 = 30


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class LogTrainingExampleTests(TestCase):
    """log_training_example: fire-and-forget helper, wired into vote/connection endpoints."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('lte_founder', password='x')
        self.investor_user = User.objects.create_user('lte_investor', password='x')
        self.investor = InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', email='i@t.com', company_name='ICo',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.app = Application.objects.create(
            user=self.founder_user, company_name='FCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )

    def test_helper_creates_a_row_with_correct_fields(self):
        log_training_example('INVESTOR', self.investor.id, 'FOUNDER', self.app.id, 'POSITIVE', 'thumbs_up')
        example = MatchTrainingExample.objects.get()
        self.assertEqual(example.anchor_type, 'INVESTOR')
        self.assertEqual(example.anchor_id, self.investor.id)
        self.assertEqual(example.candidate_type, 'FOUNDER')
        self.assertEqual(example.candidate_id, self.app.id)
        self.assertEqual(example.label, 'POSITIVE')
        self.assertEqual(example.source, 'thumbs_up')

    def test_helper_swallows_errors_instead_of_raising(self):
        # An invalid choice value would normally raise on full_clean, but
        # .create() skips validation - this asserts the try/except still
        # protects the caller even against a lower-level DB error.
        with mock.patch(
            'matchmaking.models.MatchTrainingExample.objects.create',
            side_effect=Exception('db exploded'),
        ):
            log_training_example('INVESTOR', self.investor.id, 'FOUNDER', self.app.id, 'POSITIVE', 'thumbs_up')
        self.assertEqual(MatchTrainingExample.objects.count(), 0)

    def test_thumbs_up_vote_logs_positive_example(self):
        self.client.force_login(self.investor_user)
        response = self.client.post(
            reverse('matchmaking:record_vote'),
            {'application_id': self.app.id, 'vote': 'up'},
        )
        self.assertEqual(response.status_code, 302)
        example = MatchTrainingExample.objects.get()
        self.assertEqual(example.label, 'POSITIVE')
        self.assertEqual(example.source, 'thumbs_up')

    def test_thumbs_down_vote_logs_negative_example(self):
        self.client.force_login(self.investor_user)
        self.client.post(
            reverse('matchmaking:record_vote'),
            {'application_id': self.app.id, 'vote': 'down'},
        )
        example = MatchTrainingExample.objects.get()
        self.assertEqual(example.label, 'NEGATIVE')
        self.assertEqual(example.source, 'thumbs_down')

    def test_funded_transition_logs_positive_example(self):
        from .models import Connection

        conn = Connection.objects.create(
            founder=self.app, investor=self.investor, status='ACCEPTED', initiated_by='FOUNDER',
        )
        self.client.force_login(self.founder_user)
        self.client.post(
            reverse('matchmaking:connection_action'),
            data=json.dumps({'id': conn.id, 'action': 'FUNDED'}),
            content_type='application/json',
        )
        example = MatchTrainingExample.objects.get()
        self.assertEqual(example.anchor_type, 'INVESTOR')
        self.assertEqual(example.candidate_type, 'FOUNDER')
        self.assertEqual(example.label, 'POSITIVE')
        self.assertEqual(example.source, 'funded')

    def test_declined_transition_logs_negative_example(self):
        from .models import Connection

        conn = Connection.objects.create(
            founder=self.app, investor=self.investor, status='PENDING', initiated_by='FOUNDER',
        )
        self.client.force_login(self.investor_user)
        self.client.post(
            reverse('matchmaking:connection_action'),
            data=json.dumps({'id': conn.id, 'action': 'DECLINED'}),
            content_type='application/json',
        )
        example = MatchTrainingExample.objects.get()
        self.assertEqual(example.label, 'NEGATIVE')
        self.assertEqual(example.source, 'declined')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class VectorFieldLockGracePeriodTests(TestCase):
    """
    vector_fields_locked/vector_fields_unlock_at: a 24h grace window right
    after a vector-field edit, THEN a 30-day lock — not a 30-day lock
    starting immediately. Covers Application; SellerApplication uses the
    identical implementation.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('lock_grace_founder', password='x')

    def _founder(self, updated_at):
        # All 6 VECTOR_FIELDS filled in — vector_fields_locked now also
        # requires vector_fields_complete, which is a separate concern from
        # the grace/lock timing these tests exercise (see
        # VectorFieldsCompleteGateTests for the completeness gate itself).
        return Application.objects.create(
            user=self.founder_user, company_name='FCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed', extra_info='extra',
            reason_for_capital='reason', geography='Remote', vector_fields_updated_at=updated_at,
        )

    def test_never_edited_is_not_locked(self):
        app = Application.objects.create(
            user=self.founder_user, company_name='FCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed', extra_info='extra',
            reason_for_capital='reason', geography='Remote',
        )
        self.assertFalse(app.vector_fields_locked)

    def test_within_24h_grace_window_is_not_locked(self):
        from django.utils import timezone
        app = self._founder(timezone.now() - timedelta(hours=1))
        self.assertFalse(app.vector_fields_locked)

    def test_past_grace_window_within_30_days_is_locked(self):
        from django.utils import timezone
        app = self._founder(timezone.now() - timedelta(hours=25))
        self.assertTrue(app.vector_fields_locked)

    def test_past_grace_plus_30_days_is_unlocked_again(self):
        from django.utils import timezone
        app = self._founder(timezone.now() - timedelta(hours=24, days=31))
        self.assertFalse(app.vector_fields_locked)

    def test_unlock_at_is_updated_at_plus_grace_plus_lock_duration(self):
        from django.utils import timezone
        now = timezone.now()
        app = self._founder(now)
        expected = now + timedelta(hours=24) + timedelta(days=30)
        self.assertAlmostEqual(app.vector_fields_unlock_at, expected, delta=timedelta(seconds=1))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class VectorFieldsCompleteGateTests(TestCase):
    """
    The 30-day lock only protects a *complete* profile from being gamed
    after the fact — it shouldn't fire on someone still filling the form
    out for the first time. vector_fields_locked/vector_fields_unlock_at
    must stay False/None regardless of how far past the grace+lock window
    vector_fields_updated_at is, as long as any VECTOR_FIELDS entry is
    still blank. Covers Application; SellerApplication uses the identical
    implementation against its own VECTOR_FIELDS list.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('complete_gate_founder', password='x')

    def _founder(self, **overrides):
        from django.utils import timezone
        defaults = dict(
            user=self.founder_user, company_name='FCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed', extra_info='extra',
            reason_for_capital='reason', geography='Remote',
            # Past the 24h grace window but inside the 30-day lock window —
            # a complete profile with this timestamp should be locked.
            vector_fields_updated_at=timezone.now() - timedelta(hours=25),
        )
        defaults.update(overrides)
        return Application.objects.create(**defaults)

    def test_complete_profile_reports_complete(self):
        app = self._founder()
        self.assertTrue(app.vector_fields_complete)

    def test_missing_extra_info_is_incomplete(self):
        app = self._founder(extra_info='')
        self.assertFalse(app.vector_fields_complete)

    def test_missing_reason_for_capital_is_incomplete(self):
        app = self._founder(reason_for_capital='')
        self.assertFalse(app.vector_fields_complete)

    def test_missing_geography_is_incomplete(self):
        app = self._founder(geography='')
        self.assertFalse(app.vector_fields_complete)

    def test_incomplete_profile_never_locks_even_long_past_the_lock_window(self):
        from django.utils import timezone
        app = self._founder(extra_info='', vector_fields_updated_at=timezone.now() - timedelta(days=100))
        self.assertFalse(app.vector_fields_locked)

    def test_incomplete_profile_has_no_unlock_at(self):
        app = self._founder(geography='')
        self.assertIsNone(app.vector_fields_unlock_at)

    def test_completing_the_profile_makes_it_lockable(self):
        app = self._founder()
        self.assertTrue(app.vector_fields_complete)
        self.assertTrue(app.vector_fields_locked)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SellerVectorFieldsCompleteGateTests(TestCase):
    """SellerApplication's identical implementation against its own VECTOR_FIELDS list."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.seller_user = User.objects.create_user('seller_complete_gate', password='x')

    def _seller(self, **overrides):
        from django.utils import timezone
        from .models import SellerApplication
        defaults = dict(
            user=self.seller_user, company_name='SCo', seller_name='S', email='s@t.com',
            description='test', industry='SaaS', reason_for_sale='reason',
            extra_info='extra', geography='Remote',
            vector_fields_updated_at=timezone.now() - timedelta(hours=25),
        )
        defaults.update(overrides)
        return SellerApplication.objects.create(**defaults)

    def test_complete_profile_is_lockable(self):
        seller = self._seller()
        self.assertTrue(seller.vector_fields_complete)
        self.assertTrue(seller.vector_fields_locked)

    def test_missing_reason_for_sale_never_locks(self):
        seller = self._seller(reason_for_sale='')
        self.assertFalse(seller.vector_fields_complete)
        self.assertFalse(seller.vector_fields_locked)
        self.assertIsNone(seller.vector_fields_unlock_at)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EmbeddingSemanticOrderingTests(TestCase):
    """
    Model-agnostic regression guard for the embedding provider itself
    (currently local sentence-transformers, previously Gemini). Deliberately
    does NOT mock generate_profile_embedding — it needs a real embedding to
    say anything meaningful — and deliberately does NOT assert exact
    similarity scores, since those are expected to shift if the model is
    ever swapped again. It only asserts that semantically related profiles
    outrank unrelated ones, which is the one property any embedding
    provider must preserve for matching to make sense.
    """

    def setUp(self):
        self.founder_user = User.objects.create_user('semantic_founder', password='x')
        self.other_founder_user = User.objects.create_user('semantic_founder2', password='x')
        self.investor_user = User.objects.create_user('semantic_investor', password='x')

    def test_related_profile_outranks_unrelated_profile(self):
        from .services.ai_engine import calculate_similarity

        investor = InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', email='semantic_i@t.com', company_name='ICo',
            investment_focus='Healthcare and biotech startups building novel drug therapies and clinical diagnostics',
            investment_stage='Seed',
        )
        healthcare_founder = Application.objects.create(
            user=self.founder_user, company_name='HealthCo', founder_name='F', email='semantic_f1@t.com',
            description='We develop novel drug therapies and clinical diagnostics for biotech and pharmaceutical research.',
            sector='Healthcare', stage='Seed',
        )
        manufacturing_founder = Application.objects.create(
            user=self.other_founder_user, company_name='SteelCo', founder_name='F2', email='semantic_f2@t.com',
            description='We manufacture industrial steel beams and heavy construction equipment for warehouses.',
            sector='Manufacturing', stage='Seed',
        )

        investor.refresh_from_db()
        healthcare_founder.refresh_from_db()
        manufacturing_founder.refresh_from_db()

        self.assertIsNotNone(investor.focus_vector)
        self.assertIsNotNone(healthcare_founder.description_vector)
        self.assertIsNotNone(manufacturing_founder.description_vector)

        healthcare_score = calculate_similarity(healthcare_founder.description_vector, investor.focus_vector)
        manufacturing_score = calculate_similarity(manufacturing_founder.description_vector, investor.focus_vector)

        self.assertGreater(healthcare_score, manufacturing_score)

    # Golden dataset — a small, hand-picked set of investor-focus vs.
    # founder-pitch pairs spanning verticals actually seen on this
    # marketplace. Not meant to grow into hundreds of cases; the point is a
    # quick, readable sanity check that survives an embedding model swap.
    # Add a case here any time a new vertical becomes common enough to
    # matter, rather than letting the list balloon speculatively.
    GOLDEN_CASES = [
        {
            'investor_focus': 'Healthcare and biotech startups building novel drug therapies and clinical diagnostics',
            'related_pitch': 'A pharmaceutical startup developing novel drug therapies and clinical diagnostics for patients.',
            'unrelated_pitch': 'An industrial manufacturer producing steel beams and heavy construction equipment for warehouses.',
        },
        {
            'investor_focus': 'FinTech companies building payment processing and digital banking infrastructure',
            'related_pitch': 'A payment platform providing digital banking infrastructure and payment processing for merchants.',
            'unrelated_pitch': 'A restaurant chain serving fast casual dining across regional shopping mall food courts.',
        },
        {
            'investor_focus': 'Industrial automation and robotics for manufacturing and warehouse logistics',
            'related_pitch': 'An industrial robotics company automating manufacturing lines and warehouse logistics operations.',
            'unrelated_pitch': 'A health clinic providing outpatient checkups and family medicine consultations for patients.',
        },
        {
            'investor_focus': 'B2B SaaS platforms for enterprise workflow automation and team collaboration',
            'related_pitch': 'A B2B workflow automation platform helping enterprise teams collaborate and manage projects.',
            'unrelated_pitch': 'A real estate brokerage helping homebuyers and sellers negotiate residential property deals.',
        },
    ]

    def test_golden_dataset_ranks_related_pitches_above_unrelated_ones(self):
        from .services.ai_engine import calculate_similarity

        for i, case in enumerate(self.GOLDEN_CASES):
            with self.subTest(case=case['investor_focus'][:40]):
                investor_user = User.objects.create_user(f'golden_investor_{i}', password='x')
                related_user = User.objects.create_user(f'golden_related_{i}', password='x')
                unrelated_user = User.objects.create_user(f'golden_unrelated_{i}', password='x')

                investor = InvestorApplication.objects.create(
                    user=investor_user, full_name='I', email=f'golden_i{i}@t.com', company_name='ICo',
                    investment_focus=case['investor_focus'], investment_stage='Seed',
                )
                related_founder = Application.objects.create(
                    user=related_user, company_name='RelatedCo', founder_name='F', email=f'golden_r{i}@t.com',
                    description=case['related_pitch'], sector='Other', stage='Seed',
                )
                unrelated_founder = Application.objects.create(
                    user=unrelated_user, company_name='UnrelatedCo', founder_name='F2', email=f'golden_u{i}@t.com',
                    description=case['unrelated_pitch'], sector='Other', stage='Seed',
                )

                investor.refresh_from_db()
                related_founder.refresh_from_db()
                unrelated_founder.refresh_from_db()

                related_score = calculate_similarity(related_founder.description_vector, investor.focus_vector)
                unrelated_score = calculate_similarity(unrelated_founder.description_vector, investor.focus_vector)

                self.assertGreater(
                    related_score, unrelated_score,
                    f"Expected '{case['related_pitch'][:40]}...' to outrank "
                    f"'{case['unrelated_pitch'][:40]}...' for investor focus '{case['investor_focus'][:40]}...'"
                )


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ApproximateFoundingYearTests(TestCase):
    """Application.approximate_founding_year — derived display value, no schema change."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('founding_year_founder', password='x')

    def test_returns_none_when_years_in_business_unset(self):
        app = Application.objects.create(
            user=self.founder_user, company_name='FCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.assertIsNone(app.approximate_founding_year)

    def test_computes_current_year_minus_years_in_business(self):
        from django.utils import timezone
        app = Application.objects.create(
            user=self.founder_user, company_name='FCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed', years_in_business=5,
        )
        self.assertEqual(app.approximate_founding_year, timezone.now().year - 5)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class VectorSourceTextCoverageTests(TestCase):
    """
    extra_info/monthly_burn_rate/prior_amount_raised previously fed no
    vector at all — signals.py now folds them into problem_solution_vector
    and capital_plan_vector's source text. Asserts the *text passed to the
    embedding call* includes this content, with mocked embedding output
    (no real model call, fast/deterministic) — a regression guard against
    silently dropping these fields again, not a semantic-quality check
    (that's EmbeddingSemanticOrderingTests' job).
    """

    def setUp(self):
        self.founder_user = User.objects.create_user('vector_coverage_founder', password='x')

    def test_extra_info_included_in_problem_solution_source_text(self):
        with mock.patch('matchmaking.signals.generate_profile_embedding', return_value=[0.1]) as mock_embed:
            Application.objects.create(
                user=self.founder_user, company_name='FCo', founder_name='F', email='f@t.com',
                description='We build developer tools.', extra_info='Backed by three technical co-founders.',
                sector='SaaS', stage='Seed',
            )
            # description_vector and problem_solution_vector both embed text
            # containing "developer tools" (one with extra_info folded in,
            # one without) — find the specific call that combines both.
            calls = [c.args[0] for c in mock_embed.call_args_list]
            combined = [text for text in calls if 'developer tools' in text and 'co-founders' in text]
            self.assertTrue(combined, f"Expected a call embedding description+extra_info combined; got calls: {calls}")

    def test_problem_solution_source_falls_back_to_description_alone_when_extra_info_blank(self):
        with mock.patch('matchmaking.signals.generate_profile_embedding', return_value=[0.1]) as mock_embed:
            Application.objects.create(
                user=self.founder_user, company_name='FCo', founder_name='F', email='f@t.com',
                description='We build developer tools.', sector='SaaS', stage='Seed',
            )
            calls = [c.args[0] for c in mock_embed.call_args_list]
            matching = [text for text in calls if 'developer tools' in text]
            self.assertTrue(matching)
            self.assertEqual(matching[0], 'We build developer tools.')

    def test_burn_rate_and_prior_raised_included_in_capital_plan_source_text(self):
        with mock.patch('matchmaking.signals.generate_profile_embedding', return_value=[0.1]) as mock_embed:
            Application.objects.create(
                user=self.founder_user, company_name='FCo', founder_name='F', email='f@t.com',
                description='test', sector='SaaS', stage='Seed',
                reason_for_capital='Hiring two engineers and scaling ad spend.',
                monthly_burn_rate=45000, prior_amount_raised=200000,
            )
            calls = [c.args[0] for c in mock_embed.call_args_list]
            matching = [text for text in calls if 'Hiring two engineers' in text]
            self.assertTrue(matching, "Expected a call embedding reason_for_capital")
            self.assertIn('$45,000', matching[0])
            self.assertIn('$200,000', matching[0])

    def test_capital_plan_source_falls_back_to_reason_alone_when_financials_blank(self):
        with mock.patch('matchmaking.signals.generate_profile_embedding', return_value=[0.1]) as mock_embed:
            Application.objects.create(
                user=self.founder_user, company_name='FCo', founder_name='F', email='f@t.com',
                description='test', sector='SaaS', stage='Seed',
                reason_for_capital='Hiring two engineers and scaling ad spend.',
            )
            calls = [c.args[0] for c in mock_embed.call_args_list]
            matching = [text for text in calls if 'Hiring two engineers' in text]
            self.assertTrue(matching)
            self.assertEqual(matching[0], 'Hiring two engineers and scaling ad spend.')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class MessageThreadTests(TestCase):
    """
    MessageThread is the local proxy for "have these two users ever
    messaged" — Stream Chat holds the actual messages externally, so this
    just needs one row per unique pair regardless of who initiated or how
    many times they've since messaged again.
    """

    def setUp(self):
        self.user_a = User.objects.create_user('thread_user_a', password='x')
        self.user_b = User.objects.create_user('thread_user_b', password='x')

    def test_log_thread_creates_one_row(self):
        from .models import MessageThread
        MessageThread.log_thread(self.user_a, self.user_b)
        self.assertEqual(MessageThread.objects.count(), 1)

    def test_log_thread_is_order_independent(self):
        from .models import MessageThread
        MessageThread.log_thread(self.user_a, self.user_b)
        MessageThread.log_thread(self.user_b, self.user_a)
        self.assertEqual(MessageThread.objects.count(), 1)

    def test_log_thread_ignores_self_pair(self):
        from .models import MessageThread
        MessageThread.log_thread(self.user_a, self.user_a)
        self.assertEqual(MessageThread.objects.count(), 0)

    def test_log_thread_counts_correctly_for_a_given_user(self):
        from .models import MessageThread
        from django.db.models import Q
        user_c = User.objects.create_user('thread_user_c', password='x')
        MessageThread.log_thread(self.user_a, self.user_b)
        MessageThread.log_thread(self.user_a, user_c)
        count = MessageThread.objects.filter(Q(user_a=self.user_a) | Q(user_b=self.user_a)).count()
        self.assertEqual(count, 2)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PitchVideoTelemetryTests(TestCase):
    """
    record_video_telemetry ingests sendBeacon payloads tracking the
    furthest playback position reached per session — mirrors
    record_deck_telemetry's self-view skip and beacon-with-CSRF pattern.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('video_founder', password='x')
        self.viewer = User.objects.create_user('video_viewer', password='x')
        self.application = Application.objects.create(
            user=self.founder_user, company_name='VidCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )

    def _post_telemetry(self, user, payload):
        self.client.force_login(user)
        return self.client.post(
            reverse('matchmaking:record_video_telemetry', args=[self.application.id]),
            {'payload': json.dumps(payload)},
        )

    def test_creates_a_session_row(self):
        from .models import PitchVideoView
        self._post_telemetry(self.viewer, {
            'client_session_id': 'sess-1', 'watched_seconds': 30, 'video_duration_seconds': 120,
        })
        self.assertEqual(PitchVideoView.objects.count(), 1)
        session = PitchVideoView.objects.first()
        self.assertEqual(session.max_watched_seconds, 30)

    def test_repeated_beacons_track_furthest_position_only(self):
        from .models import PitchVideoView
        self._post_telemetry(self.viewer, {
            'client_session_id': 'sess-1', 'watched_seconds': 30, 'video_duration_seconds': 120,
        })
        self._post_telemetry(self.viewer, {
            'client_session_id': 'sess-1', 'watched_seconds': 20, 'video_duration_seconds': 120,
        })
        session = PitchVideoView.objects.first()
        self.assertEqual(session.max_watched_seconds, 30, "A later, smaller watched_seconds should not move it backward")

    def test_founder_previewing_own_video_is_skipped(self):
        from .models import PitchVideoView
        self._post_telemetry(self.founder_user, {
            'client_session_id': 'sess-1', 'watched_seconds': 30, 'video_duration_seconds': 120,
        })
        self.assertEqual(PitchVideoView.objects.count(), 0)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ProfileDurationTelemetryTests(TestCase):
    """
    record_profile_duration matches a beacon back to the ProfileView row
    accounts.views.profile() creates on page load, keyed by
    viewer+viewed_user+session_key.
    """

    def setUp(self):
        self.viewed_user = User.objects.create_user('duration_viewed', password='x')
        self.viewer = User.objects.create_user('duration_viewer', password='x')

    def test_updates_matching_profile_view_row(self):
        from .models import ProfileView
        self.client.force_login(self.viewer)
        # Visit the profile first so a ProfileView row + session exist.
        self.client.get(reverse('accounts:profile', args=[self.viewed_user.username]))
        session_key = self.client.session.session_key

        response = self.client.post(
            reverse('matchmaking:record_profile_duration', args=[self.viewed_user.username]),
            {'payload': json.dumps({'duration_seconds': 45})},
        )
        self.assertEqual(response.status_code, 200)
        row = ProfileView.objects.get(viewed_user=self.viewed_user, viewer=self.viewer, session_key=session_key)
        self.assertEqual(row.duration_seconds, 45)

    def test_self_view_is_skipped(self):
        self.client.force_login(self.viewed_user)
        response = self.client.post(
            reverse('matchmaking:record_profile_duration', args=[self.viewed_user.username]),
            {'payload': json.dumps({'duration_seconds': 45})},
        )
        self.assertEqual(response.json()['status'], 'skipped')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SearchEventLoggingTests(TestCase):
    """
    SearchEvent powers the Engagement tab's 'searches per user' metric —
    it should only ever log a real, non-empty search, from either the
    filter-based global_search page or the Zelda AI sidebar search.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('search_event_user', password='x')
        self.client.force_login(self.user)

    def test_global_search_with_filters_logs_an_event(self):
        from .models import SearchEvent
        self.client.get(reverse('matchmaking:global_search'), {'industry': 'SaaS'})
        self.assertEqual(SearchEvent.objects.filter(source='filter_search').count(), 1)

    def test_global_search_with_no_filters_does_not_log(self):
        from .models import SearchEvent
        self.client.get(reverse('matchmaking:global_search'))
        self.assertEqual(SearchEvent.objects.count(), 0)

    def test_log_search_event_skips_empty_query(self):
        from django.test import RequestFactory
        from .models import log_search_event, SearchEvent
        request = RequestFactory().get('/')
        request.user = self.user
        request.session = self.client.session
        log_search_event(request, 'zelda_ai_search', '')
        self.assertEqual(SearchEvent.objects.count(), 0)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class UtmSourceCaptureTests(TestCase):
    """
    utm_source is first-touch attribution: captured only on a session's
    very first PageEvent, never overwritten by a later visit.
    """

    def _request_with_session(self, url, session_store=None):
        """
        Builds a bare request with its own session, entirely via
        RequestFactory + SessionStore — deliberately avoids self.client.get()
        for any real page, since pages.views.home_view itself calls
        log_page_event(request, 'landing_view'), which would silently
        create the session's first PageEvent before the test's own call.
        """
        from django.contrib.sessions.backends.db import SessionStore
        from django.test import RequestFactory
        request = RequestFactory().get(url)
        request.session = session_store if session_store is not None else SessionStore()
        if not request.session.session_key:
            request.session.create()
        return request

    def test_utm_source_captured_on_first_landing_view(self):
        from .models import log_page_event, PageEvent
        request = self._request_with_session('/?utm_source=twitter')
        log_page_event(request, 'landing_view')
        event = PageEvent.objects.get(event_type='landing_view')
        self.assertEqual(event.utm_source, 'twitter')

    def test_utm_source_not_overwritten_on_second_session_visit(self):
        from .models import log_page_event, PageEvent
        first_request = self._request_with_session('/?utm_source=twitter')
        log_page_event(first_request, 'landing_view')

        second_request = self._request_with_session('/?utm_source=reddit', session_store=first_request.session)
        log_page_event(second_request, 'signup_started')

        signup_event = PageEvent.objects.get(event_type='signup_started')
        self.assertEqual(signup_event.utm_source, '')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DashboardViewTrackingTests(TestCase):
    """dashboard_view PageEvent feeds the Feature Adoption tab's 'viewed match list' row."""

    def setUp(self):
        _mock_embedding_generation(self)

    def test_founder_dashboard_visit_logs_dashboard_view(self):
        from .models import PageEvent
        user = User.objects.create_user('dash_founder', password='x')
        Application.objects.create(
            user=user, company_name='Co', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.client.force_login(user)
        self.client.get(reverse('matchmaking:founder_dashboard'))
        self.assertTrue(PageEvent.objects.filter(event_type='dashboard_view', role='founder', user=user).exists())

    def test_investor_dashboard_visit_logs_dashboard_view(self):
        from .models import PageEvent
        user = User.objects.create_user('dash_investor', password='x')
        InvestorApplication.objects.create(
            user=user, full_name='I', company_name='Fund', email='i@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.client.force_login(user)
        self.client.get(reverse('matchmaking:investor_dashboard'))
        self.assertTrue(PageEvent.objects.filter(event_type='dashboard_view', role='investor', user=user).exists())


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class GrowthMetricsTests(TestCase):
    """
    Fixture-driven correctness checks for matchmaking/growth_metrics.py —
    each function backs one tab on platform_metrics (Acquisition/
    Activation/Engagement/Value Creation/Feature Adoption).
    """

    def setUp(self):
        _mock_embedding_generation(self)

    def test_feature_adoption_percentages(self):
        from . import growth_metrics
        founder_with_deck = User.objects.create_user('adopt_founder_1', password='x')
        founder_without_deck = User.objects.create_user('adopt_founder_2', password='x')
        Application.objects.create(
            user=founder_with_deck, company_name='WithDeck', founder_name='F', email='f1@t.com',
            description='test', sector='SaaS', stage='Seed', pitch_deck='decks/x.pdf',
        )
        Application.objects.create(
            user=founder_without_deck, company_name='NoDeck', founder_name='F', email='f2@t.com',
            description='test', sector='SaaS', stage='Seed',
        )

        rows = growth_metrics.get_feature_adoption_metrics()
        deck_row = next(r for r in rows if r['label'] == 'Uploaded pitch deck')
        self.assertEqual(deck_row['adopted_count'], 1)
        self.assertEqual(deck_row['eligible_count'], 2)
        self.assertEqual(deck_row['adoption_pct'], 50.0)
        self.assertEqual(deck_row['ignored_pct'], 50.0)

    def test_weekly_active_users_excludes_stale_logins(self):
        from . import growth_metrics
        recent_user = User.objects.create_user('wau_recent', password='x')
        stale_user = User.objects.create_user('wau_stale', password='x')
        Application.objects.create(
            user=recent_user, company_name='Recent', founder_name='F', email='r@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        Application.objects.create(
            user=stale_user, company_name='Stale', founder_name='F', email='s@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        recent_user.last_login = timezone.now() - timedelta(days=1)
        recent_user.save()
        stale_user.last_login = timezone.now() - timedelta(days=30)
        stale_user.save()

        metrics = growth_metrics.get_engagement_metrics()
        self.assertEqual(metrics['wau']['founder'], 1)

    def test_value_creation_counts_funded_and_accepted_connections(self):
        from . import growth_metrics
        founder_user = User.objects.create_user('vc_founder', password='x')
        investor_user = User.objects.create_user('vc_investor', password='x')
        founder = Application.objects.create(
            user=founder_user, company_name='VCCo', founder_name='F', email='vc@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        investor = InvestorApplication.objects.create(
            user=investor_user, full_name='I', company_name='Fund', email='vci@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        Connection.objects.create(investor=investor, founder=founder, status='FUNDED', initiated_by='INVESTOR')

        metrics = growth_metrics.get_value_creation_metrics()
        self.assertEqual(metrics['completed_deals'], 1)
        self.assertEqual(metrics['introductions_made'], 1)


class ProfileTrustBadgesTests(TestCase):
    """
    matchmaking/growth_metrics.py::get_profile_trust_badges — thresholded,
    distinct-investor-gated booleans only. No raw counts should ever leak
    into the returned dict, and a single investor spamming events must
    never flip a badge on.
    """

    def setUp(self):
        _mock_embedding_generation(self)

    def _make_founder(self, username):
        user = User.objects.create_user(username, password='x')
        return Application.objects.create(
            user=user, company_name=f'{username}Co', founder_name='F', email=f'{username}@t.com',
            description='test', sector='SaaS', stage='Seed',
        )

    def _make_investor(self, username):
        user = User.objects.create_user(username, password='x')
        return user, InvestorApplication.objects.create(
            user=user, full_name='I', company_name='Fund', email=f'{username}@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )

    def test_no_badges_with_no_activity(self):
        from . import growth_metrics
        founder = self._make_founder('badge_quiet_founder')
        badges = growth_metrics.get_profile_trust_badges(founder)
        self.assertEqual(badges, {'trending': False, 'frequently_analyzed': False})

    def test_none_application_returns_false_badges(self):
        from . import growth_metrics
        badges = growth_metrics.get_profile_trust_badges(None)
        self.assertEqual(badges, {'trending': False, 'frequently_analyzed': False})

    def test_single_viewer_does_not_trigger_trending(self):
        from . import growth_metrics
        from .models import InvestorInterestEvent
        founder = self._make_founder('badge_one_viewer_founder')
        investor_user, _ = self._make_investor('badge_one_viewer_investor')
        for _ in range(10):
            InvestorInterestEvent.objects.create(investor=investor_user, founder=founder, event_type='view')

        badges = growth_metrics.get_profile_trust_badges(founder)
        self.assertFalse(badges['trending'])

    def test_trending_true_once_distinct_viewer_threshold_met(self):
        from . import growth_metrics
        from .models import InvestorInterestEvent
        founder = self._make_founder('badge_trending_founder')
        for i in range(growth_metrics.TRENDING_MIN_UNIQUE_VIEWERS):
            investor_user, _ = self._make_investor(f'badge_trending_investor_{i}')
            InvestorInterestEvent.objects.create(investor=investor_user, founder=founder, event_type='view')

        badges = growth_metrics.get_profile_trust_badges(founder)
        self.assertTrue(badges['trending'])

    def test_trending_ignores_views_outside_window(self):
        from . import growth_metrics
        from .models import InvestorInterestEvent
        founder = self._make_founder('badge_stale_founder')
        old_time = timezone.now() - timedelta(days=growth_metrics.TRENDING_WINDOW_DAYS + 1)
        for i in range(growth_metrics.TRENDING_MIN_UNIQUE_VIEWERS):
            investor_user, _ = self._make_investor(f'badge_stale_investor_{i}')
            event = InvestorInterestEvent.objects.create(investor=investor_user, founder=founder, event_type='view')
            InvestorInterestEvent.objects.filter(pk=event.pk).update(created_at=old_time)

        badges = growth_metrics.get_profile_trust_badges(founder)
        self.assertFalse(badges['trending'])

    def test_frequently_analyzed_requires_distinct_analysts(self):
        from . import growth_metrics
        from .models import InvestorInterestEvent
        founder = self._make_founder('badge_analyzed_founder')
        investor_user, _ = self._make_investor('badge_analyzed_investor')
        for _ in range(10):
            InvestorInterestEvent.objects.create(investor=investor_user, founder=founder, event_type='analyze')

        badges = growth_metrics.get_profile_trust_badges(founder)
        self.assertFalse(badges['frequently_analyzed'])

        for i in range(growth_metrics.FREQUENTLY_ANALYZED_MIN_UNIQUE_ANALYSTS - 1):
            other_investor, _ = self._make_investor(f'badge_analyzed_other_{i}')
            InvestorInterestEvent.objects.create(investor=other_investor, founder=founder, event_type='analyze')

        badges = growth_metrics.get_profile_trust_badges(founder)
        self.assertTrue(badges['frequently_analyzed'])


class CompanyDomainMatchTests(TestCase):
    """
    matchmaking/models.py::company_matches_email_domain — lenient
    normalized matching for the business-email verification flow.
    """

    def test_exact_match(self):
        from .models import company_matches_email_domain
        self.assertTrue(company_matches_email_domain("Interlink Foundry", "jon@interlinkfoundry.com"))

    def test_case_and_punctuation_insensitive(self):
        from .models import company_matches_email_domain
        self.assertTrue(company_matches_email_domain("INTERLINK-Foundry, Inc.", "jon@interlinkfoundry.com"))

    def test_suffix_stripped_from_company_name(self):
        from .models import company_matches_email_domain
        self.assertTrue(company_matches_email_domain("Interlink Foundry Inc", "jon@interlinkfoundry.com"))

    def test_domain_is_superset_of_company(self):
        from .models import company_matches_email_domain
        self.assertTrue(company_matches_email_domain("Interlink", "jon@interlinkfoundry.com"))

    def test_company_is_superset_of_domain_from_spec_example(self):
        from .models import company_matches_email_domain
        self.assertTrue(company_matches_email_domain("Interlink Foundry", "jon@foundryinc.com"))

    def test_non_match(self):
        from .models import company_matches_email_domain
        self.assertFalse(company_matches_email_domain("Acme Robotics", "jon@interlinkfoundry.com"))

    def test_empty_or_malformed_input_returns_false_not_exception(self):
        from .models import company_matches_email_domain
        self.assertFalse(company_matches_email_domain("", "jon@interlinkfoundry.com"))
        self.assertFalse(company_matches_email_domain("Interlink Foundry", ""))
        self.assertFalse(company_matches_email_domain("Interlink Foundry", "not-an-email"))
        self.assertFalse(company_matches_email_domain(None, "jon@interlinkfoundry.com"))
        self.assertFalse(company_matches_email_domain("Interlink Foundry", "jon@nodot"))


class BusinessEmailVerificationModelTests(TestCase):
    """matchmaking/models.py::BusinessEmailVerification — code generation and expiry on save()."""

    def setUp(self):
        _mock_embedding_generation(self)

    def test_code_is_six_digits(self):
        from .models import BusinessEmailVerification
        user = User.objects.create_user('bev_code_user', password='x')
        verification = BusinessEmailVerification.objects.create(user=user, business_email='jon@interlinkfoundry.com')
        self.assertEqual(len(verification.code), 6)
        self.assertTrue(verification.code.isdigit())

    def test_codes_are_not_all_identical(self):
        from .models import BusinessEmailVerification
        user = User.objects.create_user('bev_random_user', password='x')
        codes = {
            BusinessEmailVerification.objects.create(user=user, business_email='jon@interlinkfoundry.com').code
            for _ in range(5)
        }
        self.assertGreater(len(codes), 1)

    def test_expires_at_set_thirty_minutes_out(self):
        from .models import BusinessEmailVerification
        user = User.objects.create_user('bev_expiry_user', password='x')
        verification = BusinessEmailVerification.objects.create(user=user, business_email='jon@interlinkfoundry.com')
        delta = verification.expires_at - verification.created_at
        self.assertAlmostEqual(delta.total_seconds(), timedelta(minutes=30).total_seconds(), delta=5)


class PlatformInsightsTests(TestCase):
    """
    matchmaking/growth_metrics.py::get_platform_insights — cohort-gated,
    correlational observations. Below-threshold cohorts must produce no
    insight at all, never a claim computed from a handful of founders.
    """

    def setUp(self):
        _mock_embedding_generation(self)

    def _make_founders(self, count, prefix, **extra_fields):
        founders = []
        for i in range(count):
            user = User.objects.create_user(f'{prefix}_{i}', password='x')
            founders.append(Application.objects.create(
                user=user, company_name=f'{prefix}Co{i}', founder_name='F', email=f'{prefix}{i}@t.com',
                description='test', sector='SaaS', stage='Seed', **extra_fields
            ))
        return founders

    def test_no_insights_below_minimum_cohort_size(self):
        from . import growth_metrics
        self._make_founders(3, 'tiny_complete', description_vector=[0.1, 0.2])
        self._make_founders(3, 'tiny_incomplete')

        insights = growth_metrics.get_platform_insights()
        self.assertEqual(insights, [])

    def test_profile_completeness_insight_appears_once_threshold_met(self):
        from . import growth_metrics
        n = growth_metrics.PLATFORM_INSIGHT_MIN_COHORT_SIZE
        self._make_founders(n, 'complete_founder', description_vector=[0.1, 0.2])
        self._make_founders(n, 'incomplete_founder')

        insights = growth_metrics.get_platform_insights()
        self.assertEqual(len(insights), 1)
        self.assertIn('completed profile', insights[0])
        self.assertIn(f'{n * 2} founders', insights[0])

    def test_insight_is_framed_as_observation_not_causal_instruction(self):
        from . import growth_metrics
        n = growth_metrics.PLATFORM_INSIGHT_MIN_COHORT_SIZE
        self._make_founders(n, 'complete_founder2', description_vector=[0.1, 0.2])
        self._make_founders(n, 'incomplete_founder2')

        insights = growth_metrics.get_platform_insights()
        self.assertIn('so far', insights[0])


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TimeToValueMetricsTests(TestCase):
    """
    get_time_to_value_metrics/get_conversation_speed_retention_insight/
    get_marketplace_liquidity_funnel — added after the ChatGPT-suggested
    time-to-value + marketplace-liquidity metrics. Medians specifically
    (not averages) so one very slow outlier can't drag the whole figure.
    """

    def setUp(self):
        _mock_embedding_generation(self)

    def test_median_resists_outlier_unlike_average(self):
        from . import growth_metrics
        from .models import InvestorInterestEvent
        founder_a = User.objects.create_user('ttv_founder_a', password='x')
        founder_b = User.objects.create_user('ttv_founder_b', password='x')
        founder_c = User.objects.create_user('ttv_founder_c', password='x')
        investor_user = User.objects.create_user('ttv_investor', password='x')

        signup_time = timezone.now() - timedelta(days=200)
        apps = []
        for u in (founder_a, founder_b, founder_c):
            app = Application.objects.create(
                user=u, company_name='Co', founder_name='F', email=f'{u.username}@t.com',
                description='test', sector='SaaS', stage='Seed',
            )
            Application.objects.filter(pk=app.pk).update(created_at=signup_time)
            apps.append(app)

        # 2h, 4h, and a 400h outlier — mean would be skewed to ~135h; median should stay at 4h.
        offsets = [timedelta(hours=2), timedelta(hours=4), timedelta(hours=400)]
        for app, offset in zip(apps, offsets):
            event = InvestorInterestEvent.objects.create(investor=investor_user, founder=app, event_type='view')
            InvestorInterestEvent.objects.filter(pk=event.pk).update(created_at=signup_time + offset)

        rows = growth_metrics.get_time_to_value_metrics()
        founder_row = next(r for r in rows if r['label'] == 'Founder')
        match_stage = next(s for s in founder_row['stages'] if s['label'] == 'First Match Viewed')
        self.assertEqual(match_stage['n'], 3)
        self.assertEqual(match_stage['median'], 4.0)

    def test_stage_with_no_data_reports_none_not_zero(self):
        from . import growth_metrics
        User.objects.create_user('ttv_lonely_founder', password='x')
        Application.objects.create(
            user=User.objects.get(username='ttv_lonely_founder'), company_name='Co', founder_name='F',
            email='lonely@t.com', description='test', sector='SaaS', stage='Seed',
        )
        rows = growth_metrics.get_time_to_value_metrics()
        founder_row = next(r for r in rows if r['label'] == 'Founder')
        conversation_stage = next(s for s in founder_row['stages'] if s['label'] == 'First Conversation')
        self.assertIsNone(conversation_stage['median'])
        self.assertEqual(conversation_stage['n'], 0)

    def test_conversation_speed_retention_splits_cohorts_correctly(self):
        from . import growth_metrics
        from .models import InvestorInterestEvent
        investor_user = User.objects.create_user('ttv_investor2', password='x')
        fast_returner = User.objects.create_user('ttv_fast_returner', password='x')
        fast_non_returner = User.objects.create_user('ttv_fast_non_returner', password='x')
        slow_returner = User.objects.create_user('ttv_slow_returner', password='x')

        signup_time = timezone.now() - timedelta(days=30)

        def _make_founder(user, conversation_offset, last_login_offset):
            app = Application.objects.create(
                user=user, company_name='Co', founder_name='F', email=f'{user.username}@t.com',
                description='test', sector='SaaS', stage='Seed',
            )
            Application.objects.filter(pk=app.pk).update(created_at=signup_time)
            event = InvestorInterestEvent.objects.create(investor=investor_user, founder=app, event_type='message_sent')
            InvestorInterestEvent.objects.filter(pk=event.pk).update(created_at=signup_time + conversation_offset)
            if last_login_offset is not None:
                user.last_login = signup_time + last_login_offset
                user.save()

        _make_founder(fast_returner, timedelta(hours=10), timedelta(days=10))
        _make_founder(fast_non_returner, timedelta(hours=20), None)
        _make_founder(slow_returner, timedelta(hours=72), timedelta(days=10))

        result = growth_metrics.get_conversation_speed_retention_insight()
        self.assertEqual(result['within_48h']['total'], 2)
        self.assertEqual(result['within_48h']['returned'], 1)
        self.assertEqual(result['after_48h']['total'], 1)
        self.assertEqual(result['after_48h']['returned'], 1)

    def test_liquidity_funnel_percent_of_starting_cohort(self):
        from . import growth_metrics
        from .models import InvestorInterestEvent
        investor_user = User.objects.create_user('liq_investor', password='x')
        viewed_founder_user = User.objects.create_user('liq_founder_viewed', password='x')
        unviewed_founder_user = User.objects.create_user('liq_founder_unviewed', password='x')

        viewed_app = Application.objects.create(
            user=viewed_founder_user, company_name='Viewed', founder_name='F', email='v@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        Application.objects.create(
            user=unviewed_founder_user, company_name='Unviewed', founder_name='F', email='u@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        InvestorInterestEvent.objects.create(investor=investor_user, founder=viewed_app, event_type='view')

        funnel = growth_metrics.get_marketplace_liquidity_funnel()
        joined_stage = next(s for s in funnel['founder'] if s['label'] == 'Founders Joined')
        viewed_stage = next(s for s in funnel['founder'] if s['label'] == 'Were Viewed')
        self.assertEqual(joined_stage['count'], 2)
        self.assertEqual(viewed_stage['count'], 1)
        self.assertEqual(viewed_stage['pct_of_starting_cohort'], 50.0)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class DataRoomModelTests(TestCase):
    """matchmaking/models.py::DataRoomDocument — validators + storage cleanup on delete()."""

    def setUp(self):
        _mock_embedding_generation(self)
        founder_user = User.objects.create_user('dr_model_founder', password='x')
        self.founder = Application.objects.create(
            user=founder_user, company_name='DR Model Co', founder_name='F', email='drm@t.com',
            description='test', sector='SaaS', stage='Seed',
        )

    def test_rejects_bad_extension(self):
        from django.core.exceptions import ValidationError
        from .models import DataRoomDocument
        doc = DataRoomDocument(
            founder=self.founder, label='Bad File', category='OTHER',
            file=SimpleUploadedFile('malware.exe', b'x' * 10, content_type='application/octet-stream'),
        )
        with self.assertRaises(ValidationError):
            doc.full_clean()

    def test_rejects_oversized_file(self):
        from django.core.exceptions import ValidationError
        from .models import DataRoomDocument
        doc = DataRoomDocument(
            founder=self.founder, label='Too Big', category='OTHER',
            file=SimpleUploadedFile('big.pdf', b'x' * (26 * 1024 * 1024), content_type='application/pdf'),
        )
        with self.assertRaises(ValidationError):
            doc.full_clean()

    def test_delete_removes_file_from_storage(self):
        from .models import DataRoomDocument
        doc = DataRoomDocument.objects.create(
            founder=self.founder, label='Cap Table', category='CAP_TABLE',
            file=SimpleUploadedFile('captable.csv', b'a,b,c', content_type='text/csv'),
        )
        storage, path = doc.file.storage, doc.file.name
        self.assertTrue(storage.exists(path))
        doc.delete()
        self.assertFalse(storage.exists(path))

    def test_cascade_delete_via_founder_also_removes_file_from_storage(self):
        """
        Regression test: a model delete() override is skipped when Django's
        cascade collector bulk-deletes related rows (e.g. deleting the
        founder Application cascades to DataRoomDocument) — only a
        post_delete signal (matchmaking/signals.py::delete_data_room_file_from_storage)
        fires reliably for every deletion path. Caught live during manual
        verification: deleting a demo founder account left an orphaned file
        in media/data_room/ before this was switched from delete() to a signal.
        """
        from .models import DataRoomDocument
        doc = DataRoomDocument.objects.create(
            founder=self.founder, label='Cascade Test', category='OTHER',
            file=SimpleUploadedFile('cascade.csv', b'x,y,z', content_type='text/csv'),
        )
        storage, path = doc.file.storage, doc.file.name
        self.assertTrue(storage.exists(path))

        self.founder.user.delete()  # cascades: User -> Application -> DataRoomDocument

        self.assertFalse(storage.exists(path))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class UploadedFileStorageCleanupTests(TestCase):
    """
    matchmaking/signals.py's post_delete receivers for Application
    (pitch_deck/pitch_video), Document (deal room), and SellerApplication
    (cim_document) — the same orphaned-file-on-delete gap found and fixed
    for DataRoomDocument also existed for these older upload fields, since
    none of them had any storage cleanup on row delete before this.
    """

    def setUp(self):
        _mock_embedding_generation(self)

    def test_deleting_application_removes_pitch_deck_and_pitch_video(self):
        user = User.objects.create_user('cleanup_founder', password='x')
        app = Application.objects.create(
            user=user, company_name='CleanupCo', founder_name='F', email='cleanup@t.com',
            description='test', sector='SaaS', stage='Seed',
            pitch_deck=SimpleUploadedFile('deck.pdf', b'x' * 10, content_type='application/pdf'),
            pitch_video=SimpleUploadedFile('pitch.mp4', b'x' * 10, content_type='video/mp4'),
        )
        deck_storage, deck_path = app.pitch_deck.storage, app.pitch_deck.name
        video_storage, video_path = app.pitch_video.storage, app.pitch_video.name
        self.assertTrue(deck_storage.exists(deck_path))
        self.assertTrue(video_storage.exists(video_path))

        app.delete()

        self.assertFalse(deck_storage.exists(deck_path))
        self.assertFalse(video_storage.exists(video_path))

    def test_cascade_deleting_user_removes_pitch_deck(self):
        user = User.objects.create_user('cleanup_founder_cascade', password='x')
        app = Application.objects.create(
            user=user, company_name='CleanupCascadeCo', founder_name='F', email='cleanup2@t.com',
            description='test', sector='SaaS', stage='Seed',
            pitch_deck=SimpleUploadedFile('deck2.pdf', b'x' * 10, content_type='application/pdf'),
        )
        storage, path = app.pitch_deck.storage, app.pitch_deck.name
        self.assertTrue(storage.exists(path))

        user.delete()  # cascades: User -> Application

        self.assertFalse(storage.exists(path))

    def test_deleting_deal_room_document_removes_file(self):
        from .models import DealRoom, Document
        founder_user = User.objects.create_user('cleanup_dr_founder', password='x')
        investor_user = User.objects.create_user('cleanup_dr_investor', password='x')
        founder = Application.objects.create(
            user=founder_user, company_name='DRCo', founder_name='F', email='drf@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        investor = InvestorApplication.objects.create(
            user=investor_user, full_name='I', email='dri@t.com', company_name='ICo',
        )
        connection = Connection.objects.create(investor=investor, founder=founder, status='ACCEPTED')
        deal_room = DealRoom.objects.create(connection=connection, is_active=True)
        doc = Document.objects.create(
            deal_room=deal_room, title='Term Sheet',
            file=SimpleUploadedFile('terms.pdf', b'x' * 10, content_type='application/pdf'),
        )
        storage, path = doc.file.storage, doc.file.name
        self.assertTrue(storage.exists(path))

        doc.delete()

        self.assertFalse(storage.exists(path))

    def test_deleting_seller_application_removes_cim_document(self):
        from .models import SellerApplication
        user = User.objects.create_user('cleanup_seller', password='x')
        seller = SellerApplication.objects.create(
            user=user, company_name='SellerCo', seller_name='S', email='seller_cleanup@t.com',
            description='test', industry='SaaS',
            cim_document=SimpleUploadedFile('cim.pdf', b'x' * 10, content_type='application/pdf'),
        )
        storage, path = seller.cim_document.storage, seller.cim_document.name
        self.assertTrue(storage.exists(path))

        seller.delete()

        self.assertFalse(storage.exists(path))


class FounderDescriptionWordCountTests(TestCase):
    """
    matchmaking/models.py::founder_description_meets_word_count and its use
    as the gate on description_vector generation — "profile complete" is
    read everywhere as description_vector__isnull=False, so a placeholder
    one-word description ("test", "TBD") should no longer count as complete.
    """

    def setUp(self):
        _mock_embedding_generation(self)

    def test_helper_rejects_below_threshold(self):
        from .models import founder_description_meets_word_count, MIN_FOUNDER_DESCRIPTION_WORDS
        self.assertFalse(founder_description_meets_word_count('test'))
        self.assertFalse(founder_description_meets_word_count(''))
        self.assertFalse(founder_description_meets_word_count(None))
        self.assertFalse(founder_description_meets_word_count('one two three four five'))
        self.assertEqual(MIN_FOUNDER_DESCRIPTION_WORDS, 10)

    def test_helper_accepts_realistic_short_description(self):
        from .models import founder_description_meets_word_count
        self.assertTrue(founder_description_meets_word_count(
            'We develop novel drug therapies and clinical diagnostics for biotech and pharmaceutical research.'
        ))

    def test_placeholder_description_does_not_get_a_vector(self):
        user = User.objects.create_user('wc_placeholder_founder', password='x')
        app = Application.objects.create(
            user=user, company_name='PlaceholderCo', founder_name='F', email='wcp@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        app.refresh_from_db()
        self.assertIsNone(app.description_vector)

    def test_real_description_gets_a_vector(self):
        # _mock_embedding_generation's return_value=[] is falsy by design (so
        # other test classes never pay for vector churn), which would mask
        # the gate actually letting a real description through — so this one
        # test patches a truthy embedding directly instead of using it.
        with mock.patch('matchmaking.signals.generate_profile_embedding', return_value=[0.1, 0.2, 0.3]):
            user = User.objects.create_user('wc_real_founder', password='x')
            app = Application.objects.create(
                user=user, company_name='RealCo', founder_name='F', email='wcr@t.com',
                description='We build infrastructure tooling that helps mid-market SaaS teams automate deploys end to end.',
                sector='SaaS', stage='Seed',
            )
        app.refresh_from_db()
        self.assertIsNotNone(app.description_vector)


class DataRoomAccessControlTests(TestCase):
    """
    matchmaking/models.py::can_view_data_room (titles-list gate) and
    can_download_data_room_document (per-document approval gate) — same
    access matrix convention as zelda_api's ICMemoTests.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('dr_ac_founder', password='x')
        self.founder = Application.objects.create(
            user=self.founder_user, company_name='DR AC Co', founder_name='F', email='drac@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.staff_user = User.objects.create_user('dr_ac_staff', password='x', is_staff=True)

        self.accepted_investor_user = User.objects.create_user('dr_ac_accepted_investor', password='x')
        self.accepted_investor = InvestorApplication.objects.create(
            user=self.accepted_investor_user, full_name='I', company_name='AcceptedFund', email='draca@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        Connection.objects.create(investor=self.accepted_investor, founder=self.founder, status='ACCEPTED', initiated_by='INVESTOR')

        self.pending_investor_user = User.objects.create_user('dr_ac_pending_investor', password='x')
        self.pending_investor = InvestorApplication.objects.create(
            user=self.pending_investor_user, full_name='I', company_name='PendingFund', email='dracp@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        Connection.objects.create(investor=self.pending_investor, founder=self.founder, status='PENDING', initiated_by='INVESTOR')

        self.unrelated_investor_user = User.objects.create_user('dr_ac_unrelated_investor', password='x')
        InvestorApplication.objects.create(
            user=self.unrelated_investor_user, full_name='I', company_name='UnrelatedFund', email='dracu@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )

    def test_can_view_data_room_matrix(self):
        from .models import can_view_data_room
        self.assertTrue(can_view_data_room(self.founder_user, self.founder))
        self.assertTrue(can_view_data_room(self.staff_user, self.founder))
        self.assertTrue(can_view_data_room(self.accepted_investor_user, self.founder))
        self.assertFalse(can_view_data_room(self.pending_investor_user, self.founder))
        self.assertFalse(can_view_data_room(self.unrelated_investor_user, self.founder))

        from django.contrib.auth.models import AnonymousUser
        self.assertFalse(can_view_data_room(AnonymousUser(), self.founder))

    def test_can_download_requires_approved_request_not_just_connection(self):
        from .models import DataRoomDocument, DataRoomAccessRequest, can_download_data_room_document
        document = DataRoomDocument.objects.create(
            founder=self.founder, label='Financials', category='FINANCIALS',
            file=SimpleUploadedFile('fin.csv', b'a,b,c', content_type='text/csv'),
        )
        # Owner/staff always
        self.assertTrue(can_download_data_room_document(self.founder_user, document))
        self.assertTrue(can_download_data_room_document(self.staff_user, document))
        # Accepted-connection investor still can't download without an APPROVED request
        self.assertFalse(can_download_data_room_document(self.accepted_investor_user, document))

        DataRoomAccessRequest.objects.create(document=document, investor=self.accepted_investor, status='APPROVED')
        self.assertTrue(can_download_data_room_document(self.accepted_investor_user, document))

        document.delete()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class DataRoomViewTests(TestCase):
    """accounts-facing view flow: list, upload, delete, request/decide access, serve."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('dr_view_founder', password='x')
        self.founder = Application.objects.create(
            user=self.founder_user, company_name='DR View Co', founder_name='F', email='drv@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.investor_user = User.objects.create_user('dr_view_investor', password='x')
        self.investor = InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='ViewFund', email='drvi@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        Connection.objects.create(investor=self.investor, founder=self.founder, status='ACCEPTED', initiated_by='INVESTOR')

        self.stranger_user = User.objects.create_user('dr_view_stranger', password='x')

        from .models import DataRoomDocument
        self.document = DataRoomDocument.objects.create(
            founder=self.founder, label='Cap Table', category='CAP_TABLE',
            file=SimpleUploadedFile('captable.csv', b'a,b,c', content_type='text/csv'),
        )

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(reverse('matchmaking:data_room', args=[self.founder_user.username]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url)

    def test_stranger_gets_404(self):
        self.client.force_login(self.stranger_user)
        response = self.client.get(reverse('matchmaking:data_room', args=[self.founder_user.username]))
        self.assertEqual(response.status_code, 404)

    def test_owner_sees_upload_form_and_can_upload(self):
        self.client.force_login(self.founder_user)
        response = self.client.post(reverse('matchmaking:data_room_upload', args=[self.founder_user.username]), {
            'category': 'FINANCIALS', 'label': 'Q4 Financials',
            'file': SimpleUploadedFile('q4.pdf', b'x' * 100, content_type='application/pdf'),
        })
        self.assertEqual(response.status_code, 302)
        from .models import DataRoomDocument
        self.assertTrue(DataRoomDocument.objects.filter(founder=self.founder, label='Q4 Financials').exists())

    def test_non_owner_cannot_upload(self):
        self.client.force_login(self.investor_user)
        response = self.client.post(reverse('matchmaking:data_room_upload', args=[self.founder_user.username]), {
            'category': 'OTHER', 'label': 'Sneaky', 'file': SimpleUploadedFile('x.pdf', b'x', content_type='application/pdf'),
        })
        self.assertEqual(response.status_code, 403)

    def test_non_owner_cannot_delete(self):
        self.client.force_login(self.investor_user)
        response = self.client.post(reverse('matchmaking:data_room_delete', args=[self.document.id]))
        self.assertEqual(response.status_code, 403)

    def test_owner_can_delete(self):
        self.client.force_login(self.founder_user)
        response = self.client.post(reverse('matchmaking:data_room_delete', args=[self.document.id]))
        self.assertEqual(response.status_code, 302)
        from .models import DataRoomDocument
        self.assertFalse(DataRoomDocument.objects.filter(id=self.document.id).exists())

    def test_investor_request_access_creates_pending_row(self):
        from .models import DataRoomAccessRequest
        self.client.force_login(self.investor_user)
        self.client.post(reverse('matchmaking:data_room_request_access', args=[self.document.id]))
        access_request = DataRoomAccessRequest.objects.get(document=self.document, investor=self.investor)
        self.assertEqual(access_request.status, 'PENDING')

    def test_founder_approve_then_investor_can_download_and_view_logged(self):
        from .models import DataRoomAccessRequest, DataRoomDocumentView
        self.client.force_login(self.investor_user)
        self.client.post(reverse('matchmaking:data_room_request_access', args=[self.document.id]))
        access_request = DataRoomAccessRequest.objects.get(document=self.document, investor=self.investor)

        self.client.force_login(self.founder_user)
        self.client.post(reverse('matchmaking:data_room_decide_request', args=[access_request.id]), {'decision': 'APPROVE'})
        access_request.refresh_from_db()
        self.assertEqual(access_request.status, 'APPROVED')

        self.client.force_login(self.investor_user)
        response = self.client.get(reverse('matchmaking:data_room_document_serve', args=[self.document.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DataRoomDocumentView.objects.filter(document=self.document, viewer=self.investor_user).count(), 1)

    def test_founder_deny_blocks_download(self):
        from .models import DataRoomAccessRequest
        self.client.force_login(self.investor_user)
        self.client.post(reverse('matchmaking:data_room_request_access', args=[self.document.id]))
        access_request = DataRoomAccessRequest.objects.get(document=self.document, investor=self.investor)

        self.client.force_login(self.founder_user)
        self.client.post(reverse('matchmaking:data_room_decide_request', args=[access_request.id]), {'decision': 'DENY'})

        self.client.force_login(self.investor_user)
        response = self.client.get(reverse('matchmaking:data_room_document_serve', args=[self.document.id]))
        self.assertEqual(response.status_code, 404)

    def test_stranger_cannot_download_even_with_direct_url(self):
        self.client.force_login(self.stranger_user)
        response = self.client.get(reverse('matchmaking:data_room_document_serve', args=[self.document.id]))
        self.assertEqual(response.status_code, 404)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PitchVideosSectionTests(TestCase):
    """
    Pitch Videos section — matchmaking/views.py::pitch_videos_section and
    the like/save/comment/settings-toggle endpoints. Covers ranking,
    privacy filtering, the per-video engagement settings, and the
    comment-notification side effect.
    """

    def setUp(self):
        _mock_embedding_generation(self)

    def _founder(self, username, **kwargs):
        u = User.objects.create_user(username, password='x')
        defaults = dict(
            company_name=f'{username}Co', founder_name='F', email=f'{username}@t.com',
            description='test', sector='SaaS', stage='Seed',
            pitch_video=SimpleUploadedFile('pitch.mp4', b'x' * 10, content_type='video/mp4'),
        )
        defaults.update(kwargs)
        return Application.objects.create(user=u, **defaults)

    def _seller(self, username, **kwargs):
        u = User.objects.create_user(username, password='x')
        defaults = dict(
            company_name=f'{username}Co', seller_name='S', email=f'{username}@t.com',
            description='test', industry='Manufacturing',
            pitch_video=SimpleUploadedFile('pitch.mp4', b'x' * 10, content_type='video/mp4'),
        )
        defaults.update(kwargs)
        return SellerApplication.objects.create(user=u, **defaults)

    # --- section view ---

    def test_only_profiles_with_a_video_are_listed(self):
        self._founder('hasvideo')
        no_video_user = User.objects.create_user('novideo', password='x')
        Application.objects.create(
            user=no_video_user, company_name='NoVideoCo', founder_name='F', email='nv@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        response = self.client.get(reverse('matchmaking:pitch_videos'))
        usernames = [f.user.username for f in response.context['founders']]
        self.assertIn('hasvideo', usernames)
        self.assertNotIn('novideo', usernames)

    def test_private_founder_excluded(self):
        self._founder('privatefounder', is_private=True)
        response = self.client.get(reverse('matchmaking:pitch_videos'))
        self.assertNotIn('privatefounder', [f.user.username for f in response.context['founders']])

    def test_null_pitch_video_does_not_crash_the_page(self):
        """
        Regression test: pitch_video is null=True, blank=True — a row with
        an explicit NULL (as opposed to '') used to slip past
        exclude(pitch_video='') (three-valued SQL logic doesn't match NULL
        against that comparison) and crash FieldFile.url in the template
        with "The 'pitch_video' attribute has no file associated with it."
        Caught live: real rows with NULL pitch_video exist in practice.
        """
        self._founder('hasvideonull_control')
        Application.objects.create(
            user=User.objects.create_user('nullvideofounder', password='x'),
            company_name='NullVideoCo', founder_name='F', email='nullvideo@t.com',
            description='test', sector='SaaS', stage='Seed', pitch_video=None,
        )
        response = self.client.get(reverse('matchmaking:pitch_videos'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('nullvideofounder', [f.user.username for f in response.context['founders']])

    def test_denied_seller_excluded(self):
        self._seller('deniedseller', review_status='DENIED')
        response = self.client.get(reverse('matchmaking:pitch_videos'))
        self.assertNotIn('deniedseller', [s.user.username for s in response.context['sellers']])

    # --- pitch_video_visibility ---

    def test_site_wide_is_default_and_visible_to_anonymous(self):
        self._founder('defaultvisfounder')
        response = self.client.get(reverse('matchmaking:pitch_videos'))
        self.assertIn('defaultvisfounder', [f.user.username for f in response.context['founders']])

    def test_profile_only_video_excluded_from_section_for_everyone(self):
        self._founder('profileonlyfounder', pitch_video_visibility='PROFILE_ONLY')
        investor_user = User.objects.create_user('profileonly_investor', password='x')
        InvestorApplication.objects.create(
            user=investor_user, full_name='I', email='poi@t.com', company_name='Fund',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.client.force_login(investor_user)
        response = self.client.get(reverse('matchmaking:pitch_videos'))
        self.assertNotIn('profileonlyfounder', [f.user.username for f in response.context['founders']])

    def test_role_only_founder_video_hidden_from_anonymous(self):
        self._founder('roleonlyfounder', pitch_video_visibility='ROLE_ONLY')
        response = self.client.get(reverse('matchmaking:pitch_videos'))
        self.assertNotIn('roleonlyfounder', [f.user.username for f in response.context['founders']])

    def test_role_only_founder_video_hidden_from_non_investor(self):
        self._founder('roleonlyfounder2', pitch_video_visibility='ROLE_ONLY')
        plain_user = User.objects.create_user('plainviewer', password='x')
        self.client.force_login(plain_user)
        response = self.client.get(reverse('matchmaking:pitch_videos'))
        self.assertNotIn('roleonlyfounder2', [f.user.username for f in response.context['founders']])

    def test_role_only_founder_video_visible_to_investor(self):
        self._founder('roleonlyfounder3', pitch_video_visibility='ROLE_ONLY')
        investor_user = User.objects.create_user('roleonly_investor', password='x')
        InvestorApplication.objects.create(
            user=investor_user, full_name='I', email='roi@t.com', company_name='Fund',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.client.force_login(investor_user)
        response = self.client.get(reverse('matchmaking:pitch_videos'))
        self.assertIn('roleonlyfounder3', [f.user.username for f in response.context['founders']])

    def test_role_only_seller_video_hidden_from_non_buyer_visible_to_buyer(self):
        self._seller('roleonlyseller', pitch_video_visibility='ROLE_ONLY')

        anon_response = self.client.get(reverse('matchmaking:pitch_videos'))
        self.assertNotIn('roleonlyseller', [s.user.username for s in anon_response.context['sellers']])

        buyer_user = User.objects.create_user('roleonly_buyer', password='x')
        BuyerApplication.objects.create(
            user=buyer_user, full_name='B', email='rob@t.com', company_name='Acq LLC',
            acquisition_thesis='We acquire manufacturing businesses',
            budget_min=100_000, budget_max=1_000_000,
        )
        self.client.force_login(buyer_user)
        buyer_response = self.client.get(reverse('matchmaking:pitch_videos'))
        self.assertIn('roleonlyseller', [s.user.username for s in buyer_response.context['sellers']])

    def test_featured_founder_ranks_above_higher_match_non_featured(self):
        self._founder('bettermatch', stage='Series C')
        self._founder('featured', stage='Seed', is_staff_featured=True)

        investor_user = User.objects.create_user('rank_investor', password='x')
        InvestorApplication.objects.create(
            user=investor_user, full_name='I', email='i@t.com', company_name='Fund',
            investment_focus='SaaS', investment_stage='Series C',
        )
        self.client.force_login(investor_user)

        response = self.client.get(reverse('matchmaking:pitch_videos'))
        usernames = [f.user.username for f in response.context['founders']]
        self.assertEqual(usernames[0], 'featured')

    def test_highlighted_founder_ranks_above_featured(self):
        """An active monthly highlight outranks plain staff/premium Featured — see _rank_pitch_video_profiles."""
        self._founder('featured2', is_staff_featured=True)
        highlighted = self._founder('highlighted2', is_premium=True, last_highlight_at=timezone.now())

        response = self.client.get(reverse('matchmaking:pitch_videos'))
        usernames = [f.user.username for f in response.context['founders']]
        self.assertEqual(usernames[0], 'highlighted2')

    def test_expired_highlight_does_not_rank_above_featured(self):
        # stalehighlight is deliberately neither premium nor staff-featured,
        # so this isolates "does an expired highlight still boost ranking"
        # from the separate is_premium/is_staff_featured tiebreak — with
        # both flags set it would tie with featured3 and fall through to
        # the recency tiebreaker instead, masking what this test checks.
        self._founder('featured3', is_staff_featured=True)
        self._founder('stalehighlight', last_highlight_at=timezone.now() - timedelta(hours=25))

        response = self.client.get(reverse('matchmaking:pitch_videos'))
        usernames = [f.user.username for f in response.context['founders']]
        self.assertEqual(usernames[0], 'featured3')

    def test_anonymous_visitor_can_view_section(self):
        self._founder('publicfounder')
        response = self.client.get(reverse('matchmaking:pitch_videos'))
        self.assertEqual(response.status_code, 200)

    # --- like ---

    def test_toggle_like_adds_then_removes(self):
        founder = self._founder('likefounder')
        liker = User.objects.create_user('liker', password='x')
        self.client.force_login(liker)
        url = reverse('matchmaking:toggle_pitch_video_like', args=['founder', founder.id])

        response = self.client.post(url)
        data = response.json()
        self.assertTrue(data['liked'])
        self.assertEqual(data['like_count'], 1)

        response = self.client.post(url)
        self.assertFalse(response.json()['liked'])
        founder.refresh_from_db()
        self.assertEqual(founder.pitch_video_likes.count(), 0)

    def test_like_count_hidden_when_show_like_count_disabled(self):
        founder = self._founder('hiddencount', pitch_video_show_like_count=False)
        liker = User.objects.create_user('hiddenliker', password='x')
        self.client.force_login(liker)
        response = self.client.post(reverse('matchmaking:toggle_pitch_video_like', args=['founder', founder.id]))
        self.assertIsNone(response.json()['like_count'])

    def test_like_requires_authentication(self):
        founder = self._founder('anonlikefounder')
        response = self.client.post(reverse('matchmaking:toggle_pitch_video_like', args=['founder', founder.id]))
        self.assertIn(response.status_code, (302, 401, 403))

    # --- save ---

    def test_toggle_save_adds_then_removes(self):
        seller = self._seller('saveseller')
        saver = User.objects.create_user('saver', password='x')
        self.client.force_login(saver)
        url = reverse('matchmaking:toggle_pitch_video_save', args=['seller', seller.id])

        self.assertTrue(self.client.post(url).json()['saved'])
        self.assertFalse(self.client.post(url).json()['saved'])

    # --- comments ---

    def test_comment_posted_when_enabled(self):
        founder = self._founder('commentablefounder')
        commenter = User.objects.create_user('commenter', password='x')
        self.client.force_login(commenter)
        response = self.client.post(
            reverse('matchmaking:post_pitch_video_comment', args=['founder', founder.id]),
            {'body': 'Great pitch!'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(PitchVideoComment.objects.filter(founder=founder, author=commenter, body='Great pitch!').exists())

    def test_comment_rejected_when_disabled(self):
        founder = self._founder('nocommentsfounder', pitch_video_comments_enabled=False)
        commenter = User.objects.create_user('blockedcommenter', password='x')
        self.client.force_login(commenter)
        response = self.client.post(
            reverse('matchmaking:post_pitch_video_comment', args=['founder', founder.id]),
            {'body': 'Nice!'},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(PitchVideoComment.objects.filter(founder=founder).exists())

    def test_empty_comment_rejected(self):
        founder = self._founder('emptycommentfounder')
        commenter = User.objects.create_user('emptycommenter', password='x')
        self.client.force_login(commenter)
        response = self.client.post(
            reverse('matchmaking:post_pitch_video_comment', args=['founder', founder.id]),
            {'body': '   '},
        )
        self.assertEqual(response.status_code, 400)

    def test_comment_notifies_owner_when_enabled(self):
        from notifications.models import Notification
        founder = self._founder('notifyfounder', pitch_video_notify_on_comments=True)
        commenter = User.objects.create_user('notifycommenter', password='x')
        self.client.force_login(commenter)
        self.client.post(
            reverse('matchmaking:post_pitch_video_comment', args=['founder', founder.id]),
            {'body': 'Interested in this.'},
        )
        self.assertTrue(
            Notification.objects.filter(recipient=founder.user, notification_type='PITCH_VIDEO_COMMENT').exists()
        )

    def test_comment_does_not_notify_when_disabled(self):
        from notifications.models import Notification
        founder = self._founder('nonotifyfounder', pitch_video_notify_on_comments=False)
        commenter = User.objects.create_user('nonotifycommenter', password='x')
        self.client.force_login(commenter)
        self.client.post(
            reverse('matchmaking:post_pitch_video_comment', args=['founder', founder.id]),
            {'body': 'Nice work.'},
        )
        self.assertFalse(
            Notification.objects.filter(recipient=founder.user, notification_type='PITCH_VIDEO_COMMENT').exists()
        )

    def test_comment_author_can_delete_own_comment(self):
        founder = self._founder('deletecommentfounder')
        commenter = User.objects.create_user('deletingcommenter', password='x')
        comment = PitchVideoComment.objects.create(founder=founder, author=commenter, body='delete me')
        self.client.force_login(commenter)
        response = self.client.post(reverse('matchmaking:delete_pitch_video_comment', args=[comment.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PitchVideoComment.objects.filter(id=comment.id).exists())

    def test_video_owner_can_delete_others_comment(self):
        founder = self._founder('ownerdeletefounder')
        commenter = User.objects.create_user('strangecommenter', password='x')
        comment = PitchVideoComment.objects.create(founder=founder, author=commenter, body='delete me too')
        self.client.force_login(founder.user)
        response = self.client.post(reverse('matchmaking:delete_pitch_video_comment', args=[comment.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PitchVideoComment.objects.filter(id=comment.id).exists())

    def test_stranger_cannot_delete_someone_elses_comment(self):
        founder = self._founder('protectedfounder')
        commenter = User.objects.create_user('protectedcommenter', password='x')
        stranger = User.objects.create_user('deletestranger', password='x')
        comment = PitchVideoComment.objects.create(founder=founder, author=commenter, body='cannot delete')
        self.client.force_login(stranger)
        response = self.client.post(reverse('matchmaking:delete_pitch_video_comment', args=[comment.id]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(PitchVideoComment.objects.filter(id=comment.id).exists())

    # --- settings toggle ---

    def test_owner_can_disable_comments_via_settings(self):
        founder = self._founder('settingsfounder')
        self.client.force_login(founder.user)
        response = self.client.post(
            reverse('matchmaking:toggle_pitch_video_setting'),
            {'setting': 'comments_enabled', 'enabled': 'false'},
        )
        self.assertEqual(response.status_code, 200)
        founder.refresh_from_db()
        self.assertFalse(founder.pitch_video_comments_enabled)

    def test_settings_toggle_requires_a_founder_or_seller_profile(self):
        plain_user = User.objects.create_user('noprofileuser', password='x')
        self.client.force_login(plain_user)
        response = self.client.post(
            reverse('matchmaking:toggle_pitch_video_setting'),
            {'setting': 'comments_enabled', 'enabled': 'false'},
        )
        self.assertEqual(response.status_code, 404)

    def test_unknown_setting_name_rejected(self):
        founder = self._founder('unknownsettingfounder')
        self.client.force_login(founder.user)
        response = self.client.post(
            reverse('matchmaking:toggle_pitch_video_setting'),
            {'setting': 'not_a_real_setting', 'enabled': 'true'},
        )
        self.assertEqual(response.status_code, 400)

    # --- visibility setting ---

    def test_owner_can_set_visibility_to_role_only(self):
        founder = self._founder('visibilityfounder')
        self.client.force_login(founder.user)
        response = self.client.post(
            reverse('matchmaking:set_pitch_video_visibility'), {'visibility': 'ROLE_ONLY'},
        )
        self.assertEqual(response.status_code, 200)
        founder.refresh_from_db()
        self.assertEqual(founder.pitch_video_visibility, 'ROLE_ONLY')

    def test_owner_can_set_visibility_on_seller_profile(self):
        seller = self._seller('visibilityseller')
        self.client.force_login(seller.user)
        response = self.client.post(
            reverse('matchmaking:set_pitch_video_visibility'), {'visibility': 'PROFILE_ONLY'},
        )
        self.assertEqual(response.status_code, 200)
        seller.refresh_from_db()
        self.assertEqual(seller.pitch_video_visibility, 'PROFILE_ONLY')

    def test_invalid_visibility_value_rejected(self):
        founder = self._founder('invalidvisibilityfounder')
        self.client.force_login(founder.user)
        response = self.client.post(
            reverse('matchmaking:set_pitch_video_visibility'), {'visibility': 'NOT_A_REAL_VALUE'},
        )
        self.assertEqual(response.status_code, 400)

    def test_visibility_requires_a_founder_or_seller_profile(self):
        plain_user = User.objects.create_user('novisibilityprofileuser', password='x')
        self.client.force_login(plain_user)
        response = self.client.post(
            reverse('matchmaking:set_pitch_video_visibility'), {'visibility': 'ROLE_ONLY'},
        )
        self.assertEqual(response.status_code, 404)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PitchVideoPlayLoggingTests(TestCase):
    """
    matchmaking/views.py::log_pitch_video_play — top of the Video ->
    Profile Conversion funnel. Same role-gating as the 'view' event logged
    in accounts.views.profile: only counts plays by an investor watching a
    founder's video, or a buyer watching a seller's video, and never counts
    the owner watching their own video.
    """

    def setUp(self):
        _mock_embedding_generation(self)

    def _founder(self, username):
        u = User.objects.create_user(username, password='x')
        return Application.objects.create(
            user=u, company_name=f'{username}Co', founder_name='F', email=f'{username}@t.com',
            description='test', sector='SaaS', stage='Seed',
            pitch_video=SimpleUploadedFile('pitch.mp4', b'x' * 10, content_type='video/mp4'),
        )

    def _seller(self, username):
        u = User.objects.create_user(username, password='x')
        return SellerApplication.objects.create(
            user=u, company_name=f'{username}Co', seller_name='S', email=f'{username}@t.com',
            description='test', industry='Manufacturing',
            pitch_video=SimpleUploadedFile('pitch.mp4', b'x' * 10, content_type='video/mp4'),
        )

    def _investor(self, username):
        u = User.objects.create_user(username, password='x')
        return InvestorApplication.objects.create(
            user=u, full_name='I', company_name='Fund', email=f'{username}@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )

    def _buyer(self, username):
        u = User.objects.create_user(username, password='x')
        return BuyerApplication.objects.create(
            user=u, full_name='B', email=f'{username}@t.com', company_name='Acq LLC',
            acquisition_thesis='We acquire manufacturing businesses',
            budget_min=100_000, budget_max=1_000_000,
        )

    def test_investor_playing_founder_video_logs_event(self):
        founder = self._founder('playfounder')
        investor = self._investor('playinvestor')
        self.client.force_login(investor.user)
        response = self.client.post(reverse('matchmaking:log_pitch_video_play', args=['founder', founder.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            InvestorInterestEvent.objects.filter(founder=founder, event_type='video_play').count(), 1
        )

    def test_buyer_playing_seller_video_logs_event(self):
        seller = self._seller('playseller')
        buyer = self._buyer('playbuyer')
        self.client.force_login(buyer.user)
        response = self.client.post(reverse('matchmaking:log_pitch_video_play', args=['seller', seller.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            AcquisitionInterestEvent.objects.filter(seller=seller, event_type='video_play').count(), 1
        )

    def test_anonymous_play_is_not_logged_but_still_succeeds(self):
        founder = self._founder('anonplayfounder')
        response = self.client.post(reverse('matchmaking:log_pitch_video_play', args=['founder', founder.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(InvestorInterestEvent.objects.filter(founder=founder).count(), 0)

    def test_owner_playing_own_video_is_not_logged(self):
        # Gives the founder an investor profile too, so the role check alone
        # would pass — this isolates the separate owner-vs-viewer check.
        founder = self._founder('ownplayfounder')
        InvestorApplication.objects.create(
            user=founder.user, full_name='I', company_name='Fund', email='ownplayfounder_inv@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.client.force_login(founder.user)
        response = self.client.post(reverse('matchmaking:log_pitch_video_play', args=['founder', founder.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(InvestorInterestEvent.objects.filter(founder=founder).count(), 0)

    def test_non_investor_viewer_play_is_not_logged(self):
        founder = self._founder('peerplayfounder')
        other_founder = self._founder('peerviewerfounder')
        self.client.force_login(other_founder.user)
        response = self.client.post(reverse('matchmaking:log_pitch_video_play', args=['founder', founder.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(InvestorInterestEvent.objects.filter(founder=founder).count(), 0)

    def test_unknown_role_404s(self):
        response = self.client.post(reverse('matchmaking:log_pitch_video_play', args=['buyer', 1]))
        self.assertEqual(response.status_code, 404)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PitchVideoFunnelTests(TestCase):
    """
    matchmaking/growth_metrics.py::get_pitch_video_funnel — each stage is
    the video-viewer cohort intersected with that event type, so a
    non-viewer's activity (however extensive) must never inflate the
    funnel, and every percentage must stay within 0-100.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('funnelfounder', password='x')
        self.founder = Application.objects.create(
            user=self.founder_user, company_name='FunnelCo', founder_name='F', email='ff@t.com',
            description='test', sector='SaaS', stage='Seed',
            pitch_video=SimpleUploadedFile('pitch.mp4', b'x' * 10, content_type='video/mp4'),
        )

    def _investor(self, username):
        u = User.objects.create_user(username, password='x')
        return InvestorApplication.objects.create(
            user=u, full_name='I', company_name='Fund', email=f'{username}@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )

    def test_empty_funnel_has_zero_counts_and_no_rates(self):
        from . import growth_metrics
        funnel = growth_metrics.get_pitch_video_funnel(self.founder, 'founder')
        self.assertEqual(funnel['plays'], 0)
        self.assertIsNone(funnel['profile_open_pct'])

    def test_funnel_only_counts_viewers_who_also_played_the_video(self):
        from . import growth_metrics
        i1, i2, i3 = (self._investor(f'funnelinv{n}').user for n in range(3))
        # i1 played the video and went all the way to an intro request.
        InvestorInterestEvent.objects.create(investor=i1, founder=self.founder, event_type='video_play')
        InvestorInterestEvent.objects.create(investor=i1, founder=self.founder, event_type='view')
        InvestorInterestEvent.objects.create(investor=i1, founder=self.founder, event_type='analyze')
        InvestorInterestEvent.objects.create(investor=i1, founder=self.founder, event_type='intro_request')
        # i2 played the video but did nothing further.
        InvestorInterestEvent.objects.create(investor=i2, founder=self.founder, event_type='video_play')
        # i3 never played the video, but did everything else — must be excluded entirely.
        InvestorInterestEvent.objects.create(investor=i3, founder=self.founder, event_type='view')
        InvestorInterestEvent.objects.create(investor=i3, founder=self.founder, event_type='analyze')
        InvestorInterestEvent.objects.create(investor=i3, founder=self.founder, event_type='intro_request')
        InvestorInterestEvent.objects.create(investor=i3, founder=self.founder, event_type='message_sent')

        funnel = growth_metrics.get_pitch_video_funnel(self.founder, 'founder')
        self.assertEqual(funnel['plays'], 2)
        self.assertEqual(funnel['profile_opens'], 1)
        self.assertEqual(funnel['analyses'], 1)
        self.assertEqual(funnel['intro_requests'], 1)
        self.assertEqual(funnel['conversations'], 0)
        self.assertEqual(funnel['profile_open_pct'], 50.0)
        self.assertEqual(funnel['analysis_pct'], 50.0)
        self.assertEqual(funnel['intro_request_pct'], 50.0)
        self.assertEqual(funnel['conversation_pct'], 0.0)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PitchVideoSocialSignalInsightsTests(TestCase):
    """
    matchmaking/growth_metrics.py::get_pitch_video_social_signal_insights —
    same cohort-gating discipline as PlatformInsightsTests: below-threshold
    cohorts must never produce a claim.
    """

    def setUp(self):
        _mock_embedding_generation(self)

    def _founder_with_video(self, username, liked=False):
        u = User.objects.create_user(username, password='x')
        app = Application.objects.create(
            user=u, company_name=f'{username}Co', founder_name='F', email=f'{username}@t.com',
            description='test', sector='SaaS', stage='Seed',
            pitch_video=SimpleUploadedFile('pitch.mp4', b'x' * 10, content_type='video/mp4'),
        )
        if liked:
            liker = User.objects.create_user(f'{username}_liker', password='x')
            app.pitch_video_likes.add(liker)
        return app

    def test_no_insight_below_minimum_cohort_size(self):
        from . import growth_metrics
        self._founder_with_video('tinyliked', liked=True)
        self._founder_with_video('tinyunliked', liked=False)

        insights = growth_metrics.get_pitch_video_social_signal_insights()
        self.assertEqual(insights, [])

    def test_like_correlation_insight_appears_once_threshold_met(self):
        from . import growth_metrics
        n = growth_metrics.PLATFORM_INSIGHT_MIN_COHORT_SIZE
        liked = [self._founder_with_video(f'likedf{i}', liked=True) for i in range(n)]
        unliked = [self._founder_with_video(f'unlikedf{i}', liked=False) for i in range(n)]

        # Every liked founder gets an intro request; no unliked founder does.
        for app in liked:
            investor_user = User.objects.create_user(f'{app.user.username}_inv', password='x')
            InvestorInterestEvent.objects.create(investor=investor_user, founder=app, event_type='intro_request')

        insights = growth_metrics.get_pitch_video_social_signal_insights()
        like_insight = next(i for i in insights if 'like' in i)
        self.assertIn('100.0%', like_insight)
        self.assertIn('0.0%', like_insight)
        self.assertIn('so far', like_insight)


class AIMatchCacheTests(TestCase):
    """
    matchmaking/match_cache.py — the cache the weekly digest reads instead
    of recomputing scores at send time. Covers the pure cache functions
    directly, plus that profile saves / milestones actually dispatch the
    refresh tasks. Mocks pass explicit new= rather than letting mock.patch
    auto-spec off the original — see zelda_api.tests.AICreditsQuotaTests
    for why: auto-specing off one of these same Celery tasks hung
    indefinitely in this environment when not given one.
    """

    def setUp(self):
        _mock_embedding_generation(self)

    def _founder(self, username, vector=None):
        u = User.objects.create_user(username, password='x')
        app = Application.objects.create(
            user=u, company_name=f'{username}Co', founder_name='F', email=f'{username}@t.com',
            description='A sufficiently long description for testing purposes here today.',
            sector='SaaS', stage='Seed',
        )
        if vector is not None:
            Application.objects.filter(pk=app.pk).update(description_vector=vector)
            app.refresh_from_db()
        return app

    def _investor(self, username, vector=None):
        u = User.objects.create_user(username, password='x')
        inv = InvestorApplication.objects.create(user=u, investment_focus='SaaS infrastructure')
        if vector is not None:
            InvestorApplication.objects.filter(pk=inv.pk).update(focus_vector=vector)
            inv.refresh_from_db()
        return inv

    def test_upsert_match_creates_new_row(self):
        from .match_cache import upsert_match
        app = self._founder('mcf1', vector=[1.0, 0.0])
        inv = self._investor('mci1', vector=[1.0, 0.0])
        match = upsert_match(inv, app, 'test reason')
        self.assertIsNotNone(match)
        self.assertAlmostEqual(float(match.score), 100.0, places=1)
        self.assertEqual(match.change_reason, 'test reason')
        self.assertIsNotNone(match.last_changed_at)

    def test_upsert_match_skips_pair_without_both_vectors(self):
        from .match_cache import upsert_match
        from .models import AIMatch
        app = self._founder('mcf2')  # no vector
        inv = self._investor('mci2', vector=[1.0, 0.0])
        result = upsert_match(inv, app, 'test reason')
        self.assertIsNone(result)
        self.assertFalse(AIMatch.objects.exists())

    def test_upsert_match_updates_existing_row_not_duplicate(self):
        from .match_cache import upsert_match
        from .models import AIMatch
        app = self._founder('mcf3', vector=[1.0, 0.0])
        inv = self._investor('mci3', vector=[1.0, 0.0])
        upsert_match(inv, app, 'first pass')
        upsert_match(inv, app, 'second pass')
        self.assertEqual(AIMatch.objects.filter(investor=inv, application=app).count(), 1)

    def test_small_score_change_does_not_bump_last_changed_at(self):
        from .match_cache import upsert_match
        app = self._founder('mcf4', vector=[1.0, 0.0])
        inv = self._investor('mci4', vector=[1.0, 0.0])
        first = upsert_match(inv, app, 'first pass')
        first_changed_at = first.last_changed_at

        # Recomputing the identical pair should produce the identical score
        # (100.0) — last_changed_at/change_reason must not move.
        second = upsert_match(inv, app, 'noise pass')
        second.refresh_from_db()
        self.assertEqual(second.last_changed_at, first_changed_at)
        self.assertEqual(second.change_reason, 'first pass')

    def test_score_generated_at_bumps_on_every_recompute_even_without_a_real_change(self):
        """
        score_generated_at answers "when was this number last verified,"
        which is a different question from last_changed_at's "when did
        something happen worth telling the user about" — it must move
        every time upsert_match runs, even when the score doesn't.
        """
        from .match_cache import upsert_match
        app = self._founder('mcf4b', vector=[1.0, 0.0])
        inv = self._investor('mci4b', vector=[1.0, 0.0])

        with mock.patch('matchmaking.match_cache.timezone.now', return_value=timezone.datetime(2026, 1, 1, tzinfo=timezone.get_current_timezone())):
            first = upsert_match(inv, app, 'first pass')

        with mock.patch('matchmaking.match_cache.timezone.now', return_value=timezone.datetime(2026, 1, 8, tzinfo=timezone.get_current_timezone())):
            second = upsert_match(inv, app, 'noise pass')

        self.assertEqual(second.last_changed_at, first.last_changed_at)  # unchanged — no real score movement
        self.assertNotEqual(second.score_generated_at, first.score_generated_at)  # bumped anyway
        self.assertEqual(second.score_generated_at, timezone.datetime(2026, 1, 8, tzinfo=timezone.get_current_timezone()))

    def test_score_change_above_epsilon_bumps_last_changed_at_and_reason(self):
        from .match_cache import upsert_match
        app = self._founder('mcf5', vector=[1.0, 0.0])
        inv = self._investor('mci5', vector=[1.0, 0.0])
        first = upsert_match(inv, app, 'first pass')
        first_changed_at = first.last_changed_at

        # Orthogonal vector -> cosine similarity drops from 100 to 0, well past epsilon.
        Application.objects.filter(pk=app.pk).update(description_vector=[0.0, 1.0])
        app.refresh_from_db()
        second = upsert_match(inv, app, 'vector changed')
        self.assertNotEqual(second.last_changed_at, first_changed_at)
        self.assertEqual(second.change_reason, 'vector changed')

    def test_refresh_matches_for_founder_scores_against_every_eligible_investor(self):
        from .match_cache import refresh_matches_for_founder
        from .models import AIMatch
        app = self._founder('mcf6', vector=[1.0, 0.0])
        self._investor('mci6a', vector=[1.0, 0.0])
        self._investor('mci6b', vector=[0.0, 1.0])
        refresh_matches_for_founder(app, 'founder updated')
        self.assertEqual(AIMatch.objects.filter(application=app).count(), 2)

    def test_refresh_matches_for_investor_scores_against_every_eligible_founder(self):
        from .match_cache import refresh_matches_for_investor
        from .models import AIMatch
        inv = self._investor('mci7', vector=[1.0, 0.0])
        self._founder('mcf7a', vector=[1.0, 0.0])
        self._founder('mcf7b', vector=[0.0, 1.0])
        refresh_matches_for_investor(inv, 'investor updated')
        self.assertEqual(AIMatch.objects.filter(investor=inv).count(), 2)

    def test_mark_milestone_change_only_touches_existing_pairs(self):
        from .match_cache import upsert_match, mark_milestone_change
        app = self._founder('mcf8', vector=[1.0, 0.0])
        inv = self._investor('mci8', vector=[1.0, 0.0])
        match = upsert_match(inv, app, 'first pass')
        original_score = match.score

        mark_milestone_change(app, 'Hit $1M ARR')

        match.refresh_from_db()
        self.assertEqual(match.change_reason, 'Founder completed a milestone: Hit $1M ARR')
        self.assertEqual(match.score, original_score)  # milestone doesn't change the score

    def test_founder_save_with_fresh_vector_dispatches_refresh_task(self):
        with mock.patch('matchmaking.signals.generate_profile_embedding', return_value=[1.0, 0.0]), \
             mock.patch('matchmaking.tasks.refresh_matches_for_founder_task.delay', new=mock.Mock()) as mock_delay:
            app = Application.objects.create(
                user=User.objects.create_user('mcf9', password='x'),
                company_name='MCF9Co', founder_name='F', email='mcf9@t.com',
                description='A sufficiently long founder description for vector generation testing purposes.',
                sector='SaaS', stage='Seed',
            )
        mock_delay.assert_called_once_with(app.pk, "Founder updated their profile")

    def test_investor_save_with_fresh_vector_dispatches_refresh_task(self):
        with mock.patch('matchmaking.signals.generate_profile_embedding', return_value=[1.0, 0.0]), \
             mock.patch('matchmaking.tasks.refresh_matches_for_investor_task.delay', new=mock.Mock()) as mock_delay:
            inv = InvestorApplication.objects.create(
                user=User.objects.create_user('mci9', password='x'),
                investment_focus='B2B SaaS infrastructure',
            )
        mock_delay.assert_called_once_with(inv.pk, "Investor updated their thesis")

    def test_milestone_creation_dispatches_milestone_task(self):
        from .models import FounderMilestone
        app = self._founder('mcf10')
        with mock.patch('matchmaking.tasks.mark_milestone_change_task.delay', new=mock.Mock()) as mock_delay:
            FounderMilestone.objects.create(founder=app, milestone_type='revenue', title='Hit $1M ARR')
        mock_delay.assert_called_once_with(app.pk, 'Hit $1M ARR')


class WeeklyDigestHeroCardTests(TestCase):
    """
    matchmaking/digest.py + the rewired _send_weekly_digests_body — one
    hero match per side, read from the AIMatch cache, anonymized for free
    viewers and full detail for Premium, with a freshness line when the
    cached match changed recently. Replaces the old generic-count digest
    entirely, so this also covers that a user with no eligible cached
    match gets nothing (not an empty/generic notification).
    """

    def setUp(self):
        _mock_embedding_generation(self)

    def _founder(self, username, is_premium=False, raising_amount=0):
        u = User.objects.create_user(username, password='x')
        app = Application.objects.create(
            user=u, company_name=f'{username}Co', founder_name='F', email=f'{username}@t.com',
            description='A sufficiently long description for testing purposes here today.',
            sector='SaaS', stage='Seed', raising_amount=raising_amount, is_premium=is_premium,
        )
        return app

    def _investor(self, username, is_premium=False, ticket_min=None, ticket_max=None):
        u = User.objects.create_user(username, password='x', email=f'{username}@t.com')
        return InvestorApplication.objects.create(
            user=u, investment_focus='SaaS infrastructure', is_premium=is_premium,
            ticket_size_min=ticket_min, ticket_size_max=ticket_max,
        )

    def _match(self, investor, application, score, change_reason='', last_changed_at=None):
        from .models import AIMatch
        return AIMatch.objects.create(
            investor=investor, application=application, score=score, confidence_score=score,
            change_reason=change_reason, last_changed_at=last_changed_at,
        )

    # -- pure helpers --

    def test_amount_bucket_thresholds(self):
        from .digest import _amount_bucket
        self.assertIsNone(_amount_bucket(0))
        self.assertEqual(_amount_bucket(100_000), "Under $250K")
        self.assertEqual(_amount_bucket(500_000), "$250K–$1M")
        self.assertEqual(_amount_bucket(2_000_000), "$1M–$5M")
        self.assertEqual(_amount_bucket(10_000_000), "$5M+")

    def test_freshness_reason_omitted_once_stale(self):
        from .digest import _freshness_reason, FRESHNESS_WINDOW_DAYS
        app = self._founder('fresh1')
        inv = self._investor('freshinv1')
        stale_match = self._match(
            inv, app, 90.0, change_reason='Founder updated their profile',
            last_changed_at=timezone.now() - timedelta(days=FRESHNESS_WINDOW_DAYS + 1),
        )
        self.assertIsNone(_freshness_reason(stale_match))

        fresh_match = self._match(
            inv, self._founder('fresh2'), 90.0, change_reason='Founder updated their profile',
            last_changed_at=timezone.now() - timedelta(days=1),
        )
        self.assertEqual(_freshness_reason(fresh_match), 'Founder updated their profile')

    # -- card building / anonymization --

    def test_free_investor_card_omits_company_name(self):
        from .digest import build_investor_digest_card
        app = self._founder('divf1', raising_amount=500_000)
        inv = self._investor('divi1', is_premium=False)
        self._match(inv, app, 85.0)

        card = build_investor_digest_card(inv)
        self.assertIsNotNone(card)
        self.assertNotIn('company_name', card)
        self.assertEqual(card['sector'], 'SaaS')
        self.assertEqual(card['raising_bucket'], "$250K–$1M")

    def test_premium_investor_card_includes_company_name(self):
        from .digest import build_investor_digest_card
        app = self._founder('divf2', raising_amount=500_000)
        inv = self._investor('divi2', is_premium=True)
        self._match(inv, app, 85.0)

        card = build_investor_digest_card(inv)
        self.assertEqual(card['company_name'], 'divf2Co')

    def test_free_founder_card_omits_investor_name(self):
        from .digest import build_founder_digest_card
        app = self._founder('divf3', is_premium=False)
        inv = self._investor('divi3', ticket_min=250_000, ticket_max=1_000_000)
        self._match(inv, app, 78.0)

        card = build_founder_digest_card(app)
        self.assertIsNotNone(card)
        self.assertNotIn('investor_name', card)
        self.assertEqual(card['ticket_range'], "$250,000–$1,000,000")

    def test_premium_founder_card_still_omits_investor_name(self):
        """
        Asymmetric by design (see digest.py's module docstring): a premium
        founder still never sees the investor's identity in their digest —
        unlike the investor side, which does reveal company_name to Premium.
        Prevents founders from soliciting a specific matched investor
        directly, off-platform. Founder Premium's perk is the monthly
        highlight boost instead (see JourneyHighlightTests).
        """
        from .digest import build_founder_digest_card
        app = self._founder('divf4', is_premium=True)
        inv = self._investor('divi4')
        self._match(inv, app, 78.0)

        card = build_founder_digest_card(app)
        self.assertNotIn('investor_name', card)

    def test_no_card_below_digest_min_score(self):
        from .digest import build_investor_digest_card, DIGEST_MIN_SCORE
        app = self._founder('divf5')
        inv = self._investor('divi5')
        self._match(inv, app, DIGEST_MIN_SCORE - 1)

        self.assertIsNone(build_investor_digest_card(inv))

    def test_message_upsells_free_viewer_not_premium(self):
        from .digest import build_investor_digest_card, investor_digest_message
        app = self._founder('divf6')
        free_inv = self._investor('divi6free')
        premium_inv = self._investor('divi6prem', is_premium=True)
        self._match(free_inv, app, 90.0)
        self._match(premium_inv, app, 90.0)

        free_message = investor_digest_message(build_investor_digest_card(free_inv))
        premium_message = investor_digest_message(build_investor_digest_card(premium_inv))
        self.assertIn('Upgrade', free_message)
        self.assertNotIn('Upgrade', premium_message)
        self.assertIn('divf6Co', premium_message)
        self.assertNotIn('divf6Co', free_message)

    # -- integration: the rewired digest task body --

    def test_digest_body_sends_notification_and_email_for_eligible_investor(self):
        from django.core import mail
        from notifications.models import Notification
        from .models import DigestEngagementEvent
        from .tasks import _send_weekly_digests_body

        app = self._founder('bodyf1')
        inv = self._investor('bodyi1')
        self._match(inv, app, 90.0)

        result = _send_weekly_digests_body()

        self.assertGreaterEqual(result['digests_sent'], 1)
        notif = Notification.objects.get(recipient=inv.user, notification_type='WEEKLY_DIGEST')
        self.assertIn('90%', notif.message)
        sent_email = next(m for m in mail.outbox if m.to == [inv.user.email])
        self.assertIn('best match', sent_email.subject.lower())

        # The HTML alternative carries the click link + open pixel; the
        # plain-text body stays just the message for clients that can't render HTML.
        html_body = sent_email.alternatives[0][0]
        self.assertIn('<img src=', html_body)
        self.assertIn('View your best match', html_body)
        self.assertEqual(sent_email.body, notif.message)

        sent_event = DigestEngagementEvent.objects.get(recipient=inv.user, event_type='sent')
        self.assertIn(str(sent_event.token), html_body)

    def test_digest_body_sends_nothing_for_investor_with_no_eligible_match(self):
        from notifications.models import Notification
        from .tasks import _send_weekly_digests_body

        inv = self._investor('bodyi2')  # no AIMatch rows at all

        _send_weekly_digests_body()

        self.assertFalse(Notification.objects.filter(recipient=inv.user, notification_type='WEEKLY_DIGEST').exists())

    def test_digest_body_also_sends_reverse_digest_to_founder(self):
        """
        No "Upgrade to see which investor" copy here regardless of premium
        status — the founder-side digest never reveals investor identity,
        Premium or not (see digest.py's module docstring for why); Founder
        Premium's perk is the monthly highlight instead.
        """
        from notifications.models import Notification
        from .tasks import _send_weekly_digests_body

        app = self._founder('bodyf3')
        inv = self._investor('bodyi3')
        self._match(inv, app, 82.0)

        _send_weekly_digests_body()

        notif = Notification.objects.get(recipient=app.user, notification_type='WEEKLY_DIGEST')
        self.assertIn('82%', notif.message)
        self.assertNotIn('Upgrade', notif.message)


class BackfillAIMatchesCommandTests(TestCase):
    """matchmaking/management/commands/backfill_ai_matches.py — the one-time
    catch-up so the digest has data on day one instead of waiting for the
    next organic profile save."""

    def setUp(self):
        _mock_embedding_generation(self)

    def test_backfill_populates_cache_for_every_eligible_pair(self):
        from django.core.management import call_command
        from .models import AIMatch

        founder_user = User.objects.create_user('backfillf', password='x')
        app = Application.objects.create(
            user=founder_user, company_name='BackfillCo', founder_name='F', email='bf@t.com',
            description='A sufficiently long description for testing purposes here today.',
            sector='SaaS', stage='Seed',
        )
        Application.objects.filter(pk=app.pk).update(description_vector=[1.0, 0.0])

        investor_user = User.objects.create_user('backfilli', password='x')
        inv = InvestorApplication.objects.create(user=investor_user, investment_focus='SaaS infrastructure')
        InvestorApplication.objects.filter(pk=inv.pk).update(focus_vector=[1.0, 0.0])

        call_command('backfill_ai_matches')

        self.assertTrue(AIMatch.objects.filter(investor_id=inv.pk, application_id=app.pk).exists())


class DigestEngagementTrackingTests(TestCase):
    """
    matchmaking/views.py::digest_open_pixel/digest_click_redirect +
    matchmaking/funnel.py — the funnel instrumentation added because the
    digest email previously had no link at all and no way to know if
    anyone ever opened it.
    """

    def setUp(self):
        _mock_embedding_generation(self)

    def test_open_pixel_records_event_once_and_returns_image(self):
        from .models import DigestEngagementEvent

        u = User.objects.create_user('pixeluser', password='x')
        sent = DigestEngagementEvent.objects.create(recipient=u, event_type='sent')

        response = self.client.get(reverse('matchmaking:digest_open_pixel', args=[sent.token]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertTrue(DigestEngagementEvent.objects.filter(token=sent.token, event_type='opened').exists())

        # Hitting the pixel again (e.g. email client re-fetching images) must not double-count.
        self.client.get(reverse('matchmaking:digest_open_pixel', args=[sent.token]))
        self.assertEqual(DigestEngagementEvent.objects.filter(token=sent.token, event_type='opened').count(), 1)

    def test_open_pixel_with_unknown_token_still_returns_image(self):
        response = self.client.get(reverse('matchmaking:digest_open_pixel', args=[uuid.uuid4()]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')

    def test_click_redirect_records_event_and_redirects_to_investor_dashboard(self):
        from .models import DigestEngagementEvent

        u = User.objects.create_user('clickinvestor', password='x')
        sent = DigestEngagementEvent.objects.create(recipient=u, event_type='sent')

        response = self.client.get(reverse('matchmaking:digest_click_redirect', args=[sent.token, 'investor']))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('matchmaking:investor_dashboard'))
        self.assertTrue(DigestEngagementEvent.objects.filter(token=sent.token, event_type='clicked').exists())

    def test_click_redirect_routes_founder_destination_to_founder_dashboard(self):
        from .models import DigestEngagementEvent

        u = User.objects.create_user('clickfounder', password='x')
        sent = DigestEngagementEvent.objects.create(recipient=u, event_type='sent')

        response = self.client.get(reverse('matchmaking:digest_click_redirect', args=[sent.token, 'founder']))
        self.assertEqual(response.url, reverse('matchmaking:founder_dashboard'))

    def test_click_redirect_does_not_double_count_repeat_clicks(self):
        from .models import DigestEngagementEvent

        u = User.objects.create_user('clicktwice', password='x')
        sent = DigestEngagementEvent.objects.create(recipient=u, event_type='sent')

        self.client.get(reverse('matchmaking:digest_click_redirect', args=[sent.token, 'investor']))
        self.client.get(reverse('matchmaking:digest_click_redirect', args=[sent.token, 'investor']))
        self.assertEqual(DigestEngagementEvent.objects.filter(token=sent.token, event_type='clicked').count(), 1)


class FunnelSummaryTests(TestCase):
    """matchmaking/funnel.py::funnel_summary — simple aggregate counts per
    funnel stage over a rolling window, reusing existing models rather than
    a new parallel event log wherever one already exists."""

    def setUp(self):
        _mock_embedding_generation(self)

    def test_counts_only_include_events_within_the_window(self):
        from .models import DigestEngagementEvent
        from .funnel import funnel_summary

        u = User.objects.create_user('funnelu', password='x')
        in_window = DigestEngagementEvent.objects.create(recipient=u, event_type='sent')
        stale = DigestEngagementEvent.objects.create(recipient=u, event_type='sent')
        DigestEngagementEvent.objects.filter(pk=stale.pk).update(created_at=timezone.now() - timedelta(days=30))

        summary = funnel_summary(days=7)
        self.assertEqual(summary['digests_sent'], 1)

    def test_open_and_click_rates_computed_against_sent(self):
        from .models import DigestEngagementEvent
        from .funnel import funnel_summary

        u1 = User.objects.create_user('funnelu1', password='x')
        u2 = User.objects.create_user('funnelu2', password='x')
        DigestEngagementEvent.objects.create(recipient=u1, event_type='sent')
        s2 = DigestEngagementEvent.objects.create(recipient=u2, event_type='sent')
        DigestEngagementEvent.objects.create(recipient=u2, event_type='opened', token=s2.token)

        summary = funnel_summary(days=7)
        self.assertEqual(summary['digests_sent'], 2)
        self.assertEqual(summary['digests_opened'], 1)
        self.assertEqual(summary['open_rate_pct'], 50.0)

    def test_rates_are_none_not_a_crash_when_nothing_sent(self):
        from .funnel import funnel_summary
        summary = funnel_summary(days=7)
        self.assertEqual(summary['digests_sent'], 0)
        self.assertIsNone(summary['open_rate_pct'])

    def test_subscriptions_started_counts_only_active_in_window(self):
        from billing.models import Subscription
        from .funnel import funnel_summary

        u = User.objects.create_user('subu', password='x')
        Subscription.objects.create(
            user=u, plan=Subscription.Plan.INVESTOR_PREMIUM, stripe_customer_id='cus_1',
            stripe_subscription_id='sub_1', status=Subscription.Status.ACTIVE,
        )
        Subscription.objects.create(
            user=u, plan=Subscription.Plan.INVESTOR_PREMIUM, stripe_customer_id='cus_2',
            stripe_subscription_id='sub_2', status=Subscription.Status.CANCELED,
        )

        summary = funnel_summary(days=7)
        self.assertEqual(summary['subscriptions_started'], 1)

    def test_intros_sent_counts_connection_not_connection_request(self):
        """
        Regression test for a real bug: funnel_summary originally counted
        ConnectionRequest, a separate model nothing in the app ever
        creates — request_intro/request_intro_from_founder both create
        Connection rows, so intros_sent was silently always zero.
        """
        from .models import Connection
        from .funnel import funnel_summary

        founder_user = User.objects.create_user('intro_founder', password='x')
        app = Application.objects.create(
            user=founder_user, company_name='IntroCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        investor_user = User.objects.create_user('intro_investor', password='x')
        inv = InvestorApplication.objects.create(user=investor_user)
        Connection.objects.create(investor=inv, founder=app, initiated_by='INVESTOR')

        summary = funnel_summary(days=7)
        self.assertEqual(summary['intros_sent'], 1)

    def test_deal_rooms_created_counts_accepted_connections_in_window(self):
        """
        DealRoom is never instantiated outside tests — the real chat
        channel is created client-side the moment a Connection reaches
        'ACCEPTED', so that's the closest available proxy.
        """
        from .models import Connection
        from .funnel import funnel_summary

        founder_user = User.objects.create_user('accept_founder', password='x')
        app = Application.objects.create(
            user=founder_user, company_name='AcceptCo', founder_name='F', email='f2@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        investor_user = User.objects.create_user('accept_investor', password='x')
        inv = InvestorApplication.objects.create(user=investor_user)
        Connection.objects.create(investor=inv, founder=app, initiated_by='INVESTOR', status='pending')

        pending_founder = User.objects.create_user('pending_founder', password='x')
        pending_app = Application.objects.create(
            user=pending_founder, company_name='PendingCo', founder_name='F', email='f3@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        Connection.objects.create(investor=inv, founder=pending_app, initiated_by='INVESTOR', status='pending')

        summary_before = funnel_summary(days=7)
        self.assertEqual(summary_before['deal_rooms_created'], 0)

        Connection.objects.filter(founder=app).update(status='ACCEPTED')

        summary_after = funnel_summary(days=7)
        self.assertEqual(summary_after['deal_rooms_created'], 1)


class RequestIntroEmailCopyTests(TestCase):
    """
    matchmaking/views.py::request_intro — regression coverage for a real
    bug: the admin-facing FYI email (sent to ADMIN_EMAIL, not the founder
    or investor — the founder's own accurate in-app Notification is
    separate) used to claim "Action Required: Navigate to the admin
    workspace to process and approve this platform handshake" even though
    connection_action_view is a direct two-party accept/decline with no
    staff step anywhere in the code path.

    Also covers a second, separate real bug found while writing this test:
    with ADMIN_EMAIL unset (empty string — its actual default), the old
    `getattr(settings, 'ADMIN_EMAIL', DEFAULT_FROM_EMAIL)` never fell
    back, since getattr's default only applies when an attribute is
    *missing*, not when it's falsy. recipient_list ended up as [''],
    which EmailMessage.recipients() silently filters out — so this email
    was failing to send with no exception and nothing in the outbox
    whenever ADMIN_EMAIL wasn't configured. Fixed with `or` instead of
    getattr's default.
    """

    def setUp(self):
        _mock_embedding_generation(self)

    def test_admin_email_no_longer_implies_manual_approval(self):
        from django.conf import settings
        from django.core import mail

        founder_user = User.objects.create_user('emailfounder', password='x')
        app = Application.objects.create(
            user=founder_user, company_name='EmailCo', founder_name='F', email='ef@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        investor_user = User.objects.create_user('emailinvestor', password='x')
        inv = InvestorApplication.objects.create(user=investor_user, investment_stage='Seed')
        self.client.force_login(investor_user)

        self.assertEqual(settings.ADMIN_EMAIL, '')  # the scenario that was silently broken
        self.client.post(reverse('matchmaking:request_intro', args=[app.id, inv.id]))

        self.assertEqual(len(mail.outbox), 1)
        admin_email = mail.outbox[0]
        self.assertEqual(admin_email.to, [settings.DEFAULT_FROM_EMAIL])  # falls back correctly now
        self.assertNotIn('admin workspace', admin_email.body.lower())
        self.assertNotIn('approve this platform handshake', admin_email.body.lower())
        self.assertIn('no action needed', admin_email.body.lower())


class InsightsEngineTests(TestCase):
    """
    matchmaking/insights_engine.py — turns the interest-event stream into
    the Premium-gated Founder/Seller Insights analytics (funnel, trending,
    Marketplace Score, opportunity alerts, recommendations, timeline, and
    the investor/buyer focus breakdowns). Pure computation, no view/HTTP
    layer involved.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('insights_founder', password='x')
        self.app = Application.objects.create(
            user=self.founder_user, company_name='InsightsCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed', is_verified=False,
        )

    def _investor_view(self, event_type='view'):
        from .models import InvestorInterestEvent
        investor = User.objects.create_user(f'insights_investor_{InvestorInterestEvent.objects.count()}', password='x')
        InvestorInterestEvent.objects.create(investor=investor, founder=self.app, event_type=event_type)
        return investor

    def test_funnel_stats_orders_stages_and_computes_drop_pct(self):
        from .insights_engine import get_funnel_stats
        from .models import InvestorInterestEvent
        for _ in range(10):
            self._investor_view('view')
        for _ in range(4):
            self._investor_view('memo_view')

        events = InvestorInterestEvent.objects.filter(founder=self.app)
        funnel = get_funnel_stats(events)

        self.assertEqual(funnel[0]['event_type'], 'view')
        self.assertEqual(funnel[0]['count'], 10)
        self.assertIsNone(funnel[0]['drop_pct'])
        self.assertEqual(funnel[1]['event_type'], 'memo_view')
        self.assertEqual(funnel[1]['count'], 4)
        self.assertEqual(funnel[1]['drop_pct'], 60)

    def test_conversion_rates_computed_from_funnel_stages(self):
        from .insights_engine import get_funnel_stats, get_conversion_rates
        from .models import InvestorInterestEvent
        for _ in range(10):
            self._investor_view('view')
        for _ in range(5):
            self._investor_view('memo_view')
        for _ in range(1):
            self._investor_view('intro_request')

        funnel = get_funnel_stats(InvestorInterestEvent.objects.filter(founder=self.app))
        rates = get_conversion_rates(funnel)

        self.assertEqual(rates['view_to_memo'], 50)
        self.assertIsNone(rates['truth_delta_to_intro'])  # zero truth_delta_view base

    def test_conversion_rate_is_none_when_base_stage_is_zero(self):
        from .insights_engine import get_funnel_stats, get_conversion_rates
        from .models import InvestorInterestEvent
        funnel = get_funnel_stats(InvestorInterestEvent.objects.filter(founder=self.app))
        rates = get_conversion_rates(funnel)
        self.assertIsNone(rates['view_to_memo'])

    def test_trending_stats_pct_change_none_with_zero_baseline(self):
        from .insights_engine import get_trending_stats
        from .models import InvestorInterestEvent
        self._investor_view('view')
        trend = get_trending_stats(InvestorInterestEvent.objects.filter(founder=self.app))
        self.assertEqual(trend['today']['current'], 1)
        self.assertIsNone(trend['today']['pct_change'])

    def test_trending_stats_pct_change_computed_against_prior_window(self):
        from .insights_engine import get_trending_stats
        from .models import InvestorInterestEvent
        old_investor = self._investor_view('view')
        old_event = InvestorInterestEvent.objects.get(investor=old_investor)
        old_event.created_at = timezone.now() - timedelta(days=10)
        old_event.save(update_fields=['created_at'])
        for _ in range(2):
            self._investor_view('view')

        trend = get_trending_stats(InvestorInterestEvent.objects.filter(founder=self.app))
        self.assertEqual(trend['last_7_days']['current'], 2)
        self.assertEqual(trend['last_7_days']['pct_change'], 100)  # 2 vs. 1 prior = +100%

    def test_engagement_score_saturates_at_100(self):
        from .insights_engine import get_funnel_stats, get_engagement_score
        from .models import InvestorInterestEvent
        for _ in range(100):
            self._investor_view('view')
        self.app.is_verified = True
        self.app.save()

        funnel = get_funnel_stats(InvestorInterestEvent.objects.filter(founder=self.app))
        score = get_engagement_score(funnel, self.app)
        self.assertEqual(score['visibility'], 100)

    def test_engagement_score_zero_with_no_events(self):
        from .insights_engine import get_funnel_stats, get_engagement_score
        from .models import InvestorInterestEvent
        funnel = get_funnel_stats(InvestorInterestEvent.objects.filter(founder=self.app))
        score = get_engagement_score(funnel, self.app)
        self.assertEqual(score['visibility'], 0)
        self.assertEqual(score['interest'], 0)
        self.assertEqual(score['responsiveness'], 0)

    def test_ai_insights_reports_no_views_when_empty(self):
        from .insights_engine import get_funnel_stats, get_trending_stats, get_ai_insights
        from .models import InvestorInterestEvent
        events = InvestorInterestEvent.objects.filter(founder=self.app)
        funnel = get_funnel_stats(events)
        trending = get_trending_stats(events)
        insights = get_ai_insights(funnel, trending)
        self.assertEqual(len(insights), 1)
        self.assertIn("hasn't been viewed yet", insights[0])

    def test_ai_insights_flags_high_memo_drop_off(self):
        from .insights_engine import get_funnel_stats, get_trending_stats, get_ai_insights
        from .models import InvestorInterestEvent
        for _ in range(10):
            self._investor_view('view')
        self._investor_view('memo_view')  # 1 of 10 = 90% drop-off

        events = InvestorInterestEvent.objects.filter(founder=self.app)
        funnel = get_funnel_stats(events)
        trending = get_trending_stats(events)
        insights = get_ai_insights(funnel, trending)
        self.assertTrue(any('drop-off' in insight for insight in insights))

    def test_interest_timeline_excludes_unlisted_event_types(self):
        from .insights_engine import get_interest_timeline
        from .models import InvestorInterestEvent
        self._investor_view('view')
        self._investor_view('video_play')  # not in TIMELINE_EVENT_TYPES
        timeline = get_interest_timeline(InvestorInterestEvent.objects.filter(founder=self.app))
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]['label'], 'Profile viewed')

    def test_opportunity_alert_for_stale_profile(self):
        from .insights_engine import get_funnel_stats, get_trending_stats, get_opportunity_alerts
        from .models import InvestorInterestEvent
        # updated_at is auto_now=True, so a normal .save() always overwrites
        # it with the current time regardless of what's assigned — bypass
        # via a queryset .update(), which auto_now doesn't intercept.
        Application.objects.filter(pk=self.app.pk).update(updated_at=timezone.now() - timedelta(days=50))
        self.app.refresh_from_db()

        events = InvestorInterestEvent.objects.filter(founder=self.app)
        funnel = get_funnel_stats(events)
        trending = get_trending_stats(events)
        alerts = get_opportunity_alerts(funnel, trending, events, self.app)
        self.assertTrue(any('50 days' in alert for alert in alerts))

    def test_opportunity_alert_for_unviewed_truth_delta(self):
        from .insights_engine import get_funnel_stats, get_trending_stats, get_opportunity_alerts
        from .models import InvestorInterestEvent
        self._investor_view('view')
        self._investor_view('memo_view')

        events = InvestorInterestEvent.objects.filter(founder=self.app)
        funnel = get_funnel_stats(events)
        trending = get_trending_stats(events)
        alerts = get_opportunity_alerts(funnel, trending, events, self.app)
        self.assertTrue(any('Truth Delta' in alert for alert in alerts))

    def test_recommendations_flags_unverified_and_no_pitch_materials(self):
        from .insights_engine import get_funnel_stats, get_recommendations
        from .models import InvestorInterestEvent
        funnel = get_funnel_stats(InvestorInterestEvent.objects.filter(founder=self.app))
        recs = get_recommendations(funnel, self.app)
        actions = [r['action'] for r in recs]
        self.assertIn('Complete Verification', actions)
        self.assertIn('Upload a Pitch Deck or Video', actions)
        for rec in recs:
            self.assertIn(rec['impact'], ('High', 'Medium'))

    def test_investor_focus_breakdown_counts_unique_viewers_by_stage_and_focus(self):
        from .insights_engine import get_investor_focus_breakdown
        from .models import InvestorInterestEvent
        inv1 = self._investor_view('view')
        InvestorApplication.objects.create(user=inv1, investment_stage='Seed', investment_focus='SaaS')
        inv2 = self._investor_view('view')
        InvestorApplication.objects.create(user=inv2, investment_stage='Seed', investment_focus='Healthcare')

        events = InvestorInterestEvent.objects.filter(founder=self.app)
        breakdown = get_investor_focus_breakdown(events)
        self.assertEqual(breakdown['unique_viewers'], 2)
        self.assertEqual(breakdown['by_stage'], {'Seed': 2})
        self.assertEqual(breakdown['by_focus'], {'SaaS': 1, 'Healthcare': 1})

    def test_buyer_deal_structure_breakdown_counts_unique_viewers(self):
        from .insights_engine import get_buyer_deal_structure_breakdown
        from .models import AcquisitionInterestEvent, SellerApplication, BuyerApplication
        seller_user = User.objects.create_user('insights_seller', password='x')
        seller = SellerApplication.objects.create(
            user=seller_user, company_name='SellCo', seller_name='S', email='s@t.com', description='test',
        )
        buyer1 = User.objects.create_user('insights_buyer1', password='x')
        BuyerApplication.objects.create(user=buyer1, full_name='B1', email='b1@t.com', company_name='B1Co', acquisition_thesis='t', preferred_deal_structure='ASSET_PURCHASE')
        AcquisitionInterestEvent.objects.create(buyer=buyer1, seller=seller, event_type='view')

        events = AcquisitionInterestEvent.objects.filter(seller=seller)
        breakdown = get_buyer_deal_structure_breakdown(events)
        self.assertEqual(breakdown['unique_viewers'], 1)
        self.assertEqual(breakdown['by_deal_structure'], {'ASSET_PURCHASE': 1})
