from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from matchmaking.models import Application

User = get_user_model()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ThankYouPageTests(TestCase):
    """
    thank_you.html now extends base.html (brings in the persistent Zelda
    widget) and only celebrates when the founder's profile is 100% complete
    per Application.completion_percentage.
    """

    def setUp(self):
        patcher = mock.patch('matchmaking.signals.generate_profile_embedding', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_extends_base_and_includes_zelda_widget(self):
        user = User.objects.create_user('thank_you_base_user', password='x')
        self.client.force_login(user)

        response = self.client.get(reverse('pages:thank_you'))

        self.assertContains(response, 'ai-agent-toggle')

    def test_what_happens_next_section_removed(self):
        user = User.objects.create_user('thank_you_copy_user', password='x')
        self.client.force_login(user)

        response = self.client.get(reverse('pages:thank_you'))

        self.assertNotContains(response, 'What happens next')
        # Not "Our team will review your profile shortly" — nothing ever
        # auto-reviews or manually approves a profile (review_status
        # defaults to APPROVED, see matchmaking.models), so that copy was
        # inaccurate the same way the intro-request admin email was.
        self.assertContains(response, 'live and visible in the marketplace')
        self.assertNotContains(response, 'team will review')

    def test_celebration_fires_for_fully_complete_profile(self):
        user = User.objects.create_user('thank_you_complete_user', password='x')
        Application.objects.create(
            user=user, company_name='FullCo', company_website='https://full.co', founder_name='F',
            email='full@t.com', phone_number='555-1234', description='desc', sector='SaaS', stage='Seed',
            raising_amount=500000, current_revenue=1000, pitch_deck='decks/x.pdf',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('pages:thank_you'))

        self.assertContains(response, 'zelda-complete-toast')

    def test_celebration_now_fires_for_partial_profile_too(self):
        """
        Reversed on purpose: celebration used to require
        completion_percentage == 100 (counts optional fields like phone/
        website/current_revenue), so it essentially never fired for a
        founder who filled only the required fields. Reaching this page
        at all means required onboarding is done, so it now celebrates
        unconditionally whenever a profile exists.
        """
        user = User.objects.create_user('thank_you_partial_user', password='x')
        Application.objects.create(
            user=user, company_name='PartialCo', founder_name='F2', email='partial@t.com',
            description='desc', sector='SaaS', stage='Seed', raising_amount=500000,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('pages:thank_you'))

        self.assertContains(response, 'zelda-complete-toast')
        self.assertContains(response, 'Upload a pitch deck to give investors more to review.')

    def test_no_celebration_when_no_application_exists(self):
        user = User.objects.create_user('thank_you_no_app_user', password='x')
        self.client.force_login(user)

        response = self.client.get(reverse('pages:thank_you'))

        self.assertNotContains(response, 'zelda-complete-toast')

    def test_back_to_dashboard_links_to_founder_dashboard_not_home(self):
        """Regression test: this used to be a hardcoded href="/" for every role."""
        user = User.objects.create_user('thank_you_redirect_user', password='x')
        Application.objects.create(
            user=user, company_name='RedirectCo', founder_name='F3', email='redirect@t.com',
            description='desc', sector='SaaS', stage='Seed', raising_amount=500000,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('pages:thank_you'))

        self.assertContains(response, reverse('matchmaking:founder_dashboard'))

    def test_back_to_dashboard_links_to_investor_dashboard_for_investors(self):
        from matchmaking.models import InvestorApplication
        user = User.objects.create_user('thank_you_investor_user', password='x')
        InvestorApplication.objects.create(user=user)
        self.client.force_login(user)

        response = self.client.get(reverse('pages:thank_you'))

        self.assertContains(response, reverse('matchmaking:investor_dashboard'))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ZeldaStageChangeToastTests(TestCase):
    """
    The globally-included Zelda widget shows a fading toast explaining why
    the icon's color changed, sourced from journey-status's headline text
    and only fired when the color actually differs from the last one the
    user saw (tracked in localStorage), not on every page load.
    """

    def setUp(self):
        self.user = User.objects.create_user('stage_toast_user', password='x')
        self.client.force_login(self.user)

    def test_toast_element_and_wiring_present_for_authenticated_user(self):
        response = self.client.get(reverse('pages:thank_you'))

        self.assertContains(response, 'zelda-stage-toast')
        self.assertContains(response, 'showStageChangeToast')
        self.assertContains(response, 'zeldaLastSeenStageColor')

    def test_toast_only_fires_on_color_change_not_every_load(self):
        response = self.client.get(reverse('pages:thank_you'))

        self.assertContains(response, 'data.stage_color !== lastSeenColor')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ZeldaNotificationDeleteButtonTests(TestCase):
    """
    Each notification card in the Zelda widget's Notifications tab renders a
    small "X" (zelda-notif-delete) so the user can dismiss one they've
    already read. Click handling is delegated on #notifications-list so it
    keeps working after loadNotifications() re-renders the list's innerHTML.
    """

    def setUp(self):
        self.user = User.objects.create_user('notif_delete_button_user', password='x')
        self.client.force_login(self.user)

    def test_delete_button_wiring_present_for_authenticated_user(self):
        response = self.client.get(reverse('pages:thank_you'))

        self.assertContains(response, 'zelda-notif-delete')
        self.assertContains(response, "/notifications/api/${delBtn.dataset.id}/delete/")
        self.assertContains(response, "notifications-list').addEventListener('click'")


class HomepageMembershipCopyTests(TestCase):
    """
    The four plan cards on the homepage source their AI-analyses and
    intro/CRM limit numbers from the real constants (zelda_api.quotas,
    matchmaking.views) rather than hardcoding them, so this copy can't
    silently drift out of sync the way the funnel metric and intro-email
    copy did earlier this session.
    """

    def test_homepage_shows_real_ai_credit_and_limit_numbers(self):
        from zelda_api.quotas import FREE_CREDITS, PREMIUM_CREDITS
        from matchmaking.views import DAILY_INTRO_REQUEST_LIMIT, FREE_CRM_LEAD_LIMIT

        response = self.client.get(reverse('pages:home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"{PREMIUM_CREDITS} monthly Zelda AI analyses (free: {FREE_CREDITS})")
        self.assertContains(response, f"free: {DAILY_INTRO_REQUEST_LIMIT}/day")
        self.assertContains(response, f"free: {FREE_CRM_LEAD_LIMIT}")

    def test_homepage_shows_current_prices(self):
        response = self.client.get(reverse('pages:home'))

        self.assertContains(response, "$99/mo")
        self.assertContains(response, "$250/mo")

    def test_homepage_founder_and_seller_cards_show_highlight_perk(self):
        response = self.client.get(reverse('pages:home'))

        self.assertContains(response, "Monthly Highlight")

    def test_homepage_shows_real_valuation_numbers(self):
        from zelda_api.quotas import (
            VALUATION_INVESTOR_BUYER_MONTHLY_LIMIT, VALUATION_OVERAGE_PRICE_USD,
            VALUATION_REPORT_PRICE_USD,
        )

        response = self.client.get(reverse('pages:home'))

        self.assertContains(
            response,
            f"{VALUATION_INVESTOR_BUYER_MONTHLY_LIMIT} business valuations/month included "
            f"(${VALUATION_OVERAGE_PRICE_USD:.2f}/report after that)",
        )
        self.assertContains(
            response,
            f"Business valuations for ${VALUATION_REPORT_PRICE_USD:.2f}/report (pay-per-use, not bundled)",
        )


class HomepagePositioningCopyTests(TestCase):
    """
    Homepage rewrite from "AI-powered matching marketplace" to "evidence-
    grounded business intelligence and decision infrastructure" (backlog
    #10). Locks in the two messaging principles the rewrite was approved
    on: Truth Delta (claim evaluation) and Verified Funded/Sold
    (counterparty-confirmed transaction outcome) stay explicitly distinct,
    and nothing claims a capability that isn't actually shipped (#8
    competitive benchmarking, #7 expert review).
    """

    def test_hero_leads_with_decision_making_not_audience_actions(self):
        """
        "Make better decisions about businesses." is the primary <h1> —
        AI/audience-actions language is secondary, not the headline. The
        "Raise capital. Source deals. Buy or sell a business." line is
        intentionally still present (per the approved refinement) as a
        secondary tagline naming what you can actually do here, subordinate
        to the decision-making headline — so this checks structure (what's
        IN the h1) rather than the phrase's absence from the page.
        """
        import re
        response = self.client.get(reverse('pages:home'))
        content = response.content.decode('utf-8')
        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', content, re.DOTALL)
        self.assertIsNotNone(h1_match)
        h1_text = h1_match.group(1)
        self.assertIn('Make better decisions', h1_text)
        self.assertNotIn('Raise capital', h1_text)

        self.assertContains(response, 'evidence-grounded intelligence, semantic matching, and verified deal outcomes')
        self.assertContains(response, 'Raise capital. Source deals. Buy or sell a business.')
        self.assertNotContains(response, 'reads the deal before you do')

    def test_zelda_section_positions_intelligence_layer_not_matching_engine(self):
        response = self.client.get(reverse('pages:home'))
        self.assertContains(response, 'Meet Zelda.')
        self.assertContains(response, 'The Intelligence Layer')
        self.assertNotContains(response, 'Meet the Zelda Engine.')
        self.assertNotContains(response, 'Proprietary AI Layer')

    def test_four_stage_pipeline_present_in_order(self):
        response = self.client.get(reverse('pages:home'))
        self.assertContains(response, 'Information')
        self.assertContains(response, 'Matching')
        self.assertContains(response, 'Intelligence')
        self.assertContains(response, 'Verified Outcomes')
        self.assertContains(response, '1. Understand the Business')
        self.assertContains(response, '2. Find the Right Opportunities')
        self.assertContains(response, '3. Analyze the Evidence')
        self.assertContains(response, '4. Build a Verified Track Record')

    def test_verified_outcomes_tile_present_in_what_you_get(self):
        response = self.client.get(reverse('pages:home'))
        self.assertContains(response, 'Verified Funded / Verified Sold')
        self.assertContains(response, 'both sides confirm it')

    def test_truth_delta_and_verified_outcomes_stay_distinct_not_blurred(self):
        """The approved messaging principle: Truth Delta evaluates claims/
        evidence; Verified Funded/Sold confirms an actual transaction. The
        page must describe both without merging them into generic "AI
        verification" language."""
        response = self.client.get(reverse('pages:home'))
        content = response.content.decode('utf-8')
        self.assertIn('Truth Delta separates disclosed claims from verified or unsupported information', content)
        self.assertIn('both sides confirm the outcome', content)

    def test_no_unshipped_capabilities_advertised(self):
        """#8 (competitive benchmarking) and #7 (expert review) aren't
        built yet — the homepage must not claim them."""
        response = self.client.get(reverse('pages:home'))
        content = response.content.decode('utf-8')
        self.assertNotIn('competitor', content.lower())
        self.assertNotIn('benchmark', content.lower())
        self.assertNotIn('expert review', content.lower())
        self.assertNotIn('percentile', content.lower())

    def test_no_role_specific_landing_pages_introduced(self):
        """Explicitly out of scope for this copy pass — no /founders,
        /investors, /buyers, /sellers routes."""
        response = self.client.get(reverse('pages:home'))
        content = response.content.decode('utf-8')
        for path in ('href="/founders', 'href="/investors', 'href="/buyers', 'href="/sellers'):
            self.assertNotIn(path, content)
