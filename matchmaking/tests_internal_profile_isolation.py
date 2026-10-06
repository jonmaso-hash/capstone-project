from django.contrib.auth.models import User
from django.test import TestCase

from matchmaking.models import (
    Application,
    InvestorApplication,
    SellerApplication,
    BuyerApplication,
    ProfileVideo,
)


class InternalProfileDiscoveryIsolationTests(TestCase):
    def make_user(self, username):
        return User.objects.create_user(username=username, password="x")

    def test_founder_internal_profile_is_not_discoverable_but_still_directly_accessible(self):
        user = self.make_user("internal_founder")
        founder = Application.objects.create(
            user=user,
            company_name="Internal Audit Founder",
            founder_name="Audit",
            email="audit-founder@example.com",
            description="Internal audit profile only.",
            sector="SaaS",
            stage="Seed",
            is_internal_profile=True,
        )

        self.assertFalse(Application.objects.discoverable().filter(pk=founder.pk).exists())
        self.assertEqual(Application.objects.get(pk=founder.pk), founder)

    def test_investor_internal_profile_is_not_discoverable(self):
        user = self.make_user("internal_investor")
        investor = InvestorApplication.objects.create(
            user=user,
            full_name="Audit Investor",
            email="audit-investor@example.com",
            company_name="Internal Audit Fund",
            investment_focus="SaaS",
            investment_stage="Seed",
            is_internal_profile=True,
        )

        self.assertFalse(
            InvestorApplication.objects.discoverable().filter(pk=investor.pk).exists()
        )
        self.assertEqual(InvestorApplication.objects.get(pk=investor.pk), investor)

    def test_seller_internal_profile_is_not_discoverable(self):
        user = self.make_user("internal_seller")
        seller = SellerApplication.objects.create(
            user=user,
            company_name="Internal Audit Seller",
            seller_name="Audit Seller",
            email="audit-seller@example.com",
            description="Internal seller audit profile only.",
            industry="SaaS",
            is_internal_profile=True,
        )

        self.assertFalse(
            SellerApplication.objects.discoverable().filter(pk=seller.pk).exists()
        )
        self.assertEqual(SellerApplication.objects.get(pk=seller.pk), seller)

    def test_buyer_internal_profile_is_not_discoverable(self):
        user = self.make_user("internal_buyer")
        buyer = BuyerApplication.objects.create(
            user=user,
            full_name="Audit Buyer",
            email="audit-buyer@example.com",
            company_name="Internal Audit Buyer",
            acquisition_thesis="Acquire internal test companies.",
            is_internal_profile=True,
        )

        self.assertFalse(
            BuyerApplication.objects.discoverable().filter(pk=buyer.pk).exists()
        )
        self.assertEqual(BuyerApplication.objects.get(pk=buyer.pk), buyer)

    def test_live_profiles_remain_discoverable_by_default(self):
        user = self.make_user("live_founder")
        founder = Application.objects.create(
            user=user,
            company_name="Live Founder",
            founder_name="Live",
            email="live-founder@example.com",
            description="Real marketplace profile.",
            sector="SaaS",
            stage="Seed",
        )

        self.assertTrue(Application.objects.discoverable().filter(pk=founder.pk).exists())

    def test_internal_founder_elevator_pitch_is_excluded_from_explore_source(self):
        user = self.make_user("internal_video_founder")
        founder = Application.objects.create(
            user=user,
            company_name="Internal Video Founder",
            founder_name="Audit",
            email="audit-video@example.com",
            description="Internal Explore audit profile.",
            sector="SaaS",
            stage="Seed",
            is_internal_profile=True,
        )
        video = ProfileVideo.objects.create(
            founder=founder,
            kind=ProfileVideo.KIND_ELEVATOR_PITCH,
            video="elevator_pitches/internal-test.mp4",
            status=ProfileVideo.STATUS_PUBLISHED,
        )

        self.assertFalse(
            ProfileVideo.objects.visible_elevator_pitches().filter(pk=video.pk).exists()
        )

    def test_live_founder_elevator_pitch_still_appears_in_explore_source(self):
        user = self.make_user("live_video_founder")
        founder = Application.objects.create(
            user=user,
            company_name="Live Video Founder",
            founder_name="Live",
            email="live-video@example.com",
            description="Live Explore marketplace profile.",
            sector="SaaS",
            stage="Seed",
        )
        video = ProfileVideo.objects.create(
            founder=founder,
            kind=ProfileVideo.KIND_ELEVATOR_PITCH,
            video="elevator_pitches/live-test.mp4",
            status=ProfileVideo.STATUS_PUBLISHED,
        )

        self.assertTrue(
            ProfileVideo.objects.visible_elevator_pitches().filter(pk=video.pk).exists()
        )


class InternalProfileAnalyticsIsolationTests(TestCase):
    def make_founder(self, username, *, internal):
        user = User.objects.create_user(username=username, password="x")
        return Application.objects.create(
            user=user,
            company_name=username,
            founder_name=username,
            email=f"{username}@example.com",
            description="Profile used for platform analytics isolation.",
            sector="SaaS",
            stage="Seed",
            is_internal_profile=internal,
        )

    def test_founder_funnel_signup_count_excludes_internal_profiles(self):
        from matchmaking.analytics import get_founder_investor_funnel

        self.make_founder("analytics_live_founder", internal=False)
        self.make_founder("analytics_internal_founder", internal=True)

        funnel = get_founder_investor_funnel()["founder"]
        counts = {row["key"]: row["count"] for row in funnel}

        self.assertEqual(counts["signup_completed"], 1)

    def test_marketplace_liquidity_starting_cohort_excludes_internal_profiles(self):
        from matchmaking.growth_metrics import get_marketplace_liquidity_funnel

        self.make_founder("liquidity_live_founder", internal=False)
        self.make_founder("liquidity_internal_founder", internal=True)

        data = get_marketplace_liquidity_funnel()
        founder_rows = data["founder"]
        joined = next(row for row in founder_rows if row["label"] == "Founders Joined")

        self.assertEqual(joined["count"], 1)
