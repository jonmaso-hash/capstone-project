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
    """Homepage quotes current subscription prices but leaves detailed
    entitlements and one-time Zelda pricing to the billing/product surfaces."""

    def test_homepage_shows_current_subscription_prices(self):
        response = self.client.get(reverse('pages:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "$99/mo")
        self.assertContains(response, "$250/mo")

    def test_homepage_says_membership_and_report_purchases_are_separate(self):
        response = self.client.get(reverse('pages:home'))
        self.assertContains(
            response,
            "Membership and individual Zelda report purchases are separate product concepts.",
        )
        self.assertContains(response, "Current benefits, report prices")
        self.assertContains(response, "billing terms are shown before checkout")


class HomepagePositioningCopyTests(TestCase):
    """Public positioning stays neutral: discovery, evidence and workflow
    are distinct from advice, transaction execution and outcome promises."""

    @staticmethod
    def _squeeze(text):
        return ' '.join(text.lower().split())

    def _home(self):
        response = self.client.get(reverse('pages:home'))
        self.assertEqual(response.status_code, 200)
        return response

    def test_hero_leads_with_relationship_context(self):
        import re
        response = self._home()
        content = response.content.decode('utf-8')
        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', content, re.DOTALL)
        self.assertIsNotNone(h1_match)
        self.assertIn('Build business relationships with better context.', h1_match.group(1))
        self.assertContains(response, 'Neutral business networking + Zelda intelligence')
        self.assertContains(response, 'without telling you what decision to make')

    def test_regulatory_boundary_is_visible_and_linked(self):
        response = self._home()
        self.assertContains(response, 'It does not provide')
        self.assertContains(response, 'investment recommendations')
        self.assertContains(response, 'execute, negotiate, or guarantee securities or business transactions')
        self.assertContains(response, reverse('pages:regulatory_positioning'))

    def test_zelda_advantage_is_personalized_and_non_directive(self):
        response = self._home()
        self.assertContains(response, 'The Zelda Advantage')
        self.assertContains(response, 'Personalized guidance, grounded in your activity.')
        self.assertContains(response, 'Keep the decision with the user.')
        self.assertContains(response, 'does not recommend whether to invest, buy, sell, or raise')

    def test_four_roles_use_discovery_and_relationship_language(self):
        response = self._home()
        for phrase in (
            'Build investor relationships',
            'Organize company discovery',
            'Present a business clearly',
            'Review acquisition opportunities',
        ):
            with self.subTest(phrase=phrase):
                self.assertContains(response, phrase)
        self.assertContains(response, 'Alignment is a discovery signal')
        self.assertContains(response, 'not an endorsement')

    def test_featured_placement_is_not_presented_as_alignment(self):
        # The section only renders when staff-featured profiles exist, so pin
        # the template contract rather than manufacturing a featured company
        # just to make conditional marketing copy visible in this test.
        from pathlib import Path
        from django.conf import settings
        content = (Path(settings.BASE_DIR) / 'templates' / 'pages' / 'home.html').read_text(encoding='utf-8')
        self.assertIn('Featured placement is promotional visibility only.', content)
        self.assertIn('not a recommendation, endorsement', content)
        self.assertIn('or indication of stronger alignment', content)

    def test_zelda_section_keeps_evidence_states_and_private_company_limit(self):
        response = self._home()
        content = response.content.decode('utf-8')
        self.assertIn('Meet Zelda.', content)
        self.assertIn('The Intelligence Layer', content)
        self.assertIn(
            'labels each one verified, contradicted, or not established — with the reason',
            content,
        )
        self.assertIn(
            'For most private companies, public sources report little, so many claims will read '
            '&lsquo;not established&rsquo;; that is a statement about the evidence, not about the company.',
            content,
        )

    def test_alignment_example_uses_band_not_percentage(self):
        response = self._home()
        content = response.content.decode('utf-8')
        self.assertIn('Stated-criteria band:', content)
        self.assertIn('NOTABLE', content)
        self.assertNotIn('94.2% SEMANTIC MATCH', content)
        self.assertNotIn('94.2% MATCH', content)
        self.assertIn('Alignment reflects similarity between stated criteria.', content)
        self.assertIn('not investment advice', content)

    def test_confirmed_outcomes_are_mutual_confirmation_not_verification_claims(self):
        response = self._home()
        content = response.content.decode('utf-8')
        self.assertIn('Record confirmed outcomes', content)
        self.assertIn('both counterparties confirm a funding or sale outcome', content)
        for retired in ('Verified Track Record', 'Verified Funded', 'Verified Sold', 'verified deal outcomes'):
            with self.subTest(retired=retired):
                self.assertNotIn(retired, content)

    def test_business_valuation_states_its_limits(self):
        response = self._home()
        self.assertContains(response, 'Model-based valuation output with assumptions and limitations.')
        self.assertContains(response, 'not an appraisal, fairness opinion, or transaction price')

    def test_no_transaction_or_advisory_marketing_claims(self):
        content = self._squeeze(self._home().content.decode('utf-8'))
        for phrase in (
            'find the right opportunities',
            'raise capital. source deals.',
            'verified deal outcomes',
            'build a verified track record',
            'best-fit founders',
            'best opportunities',
            'investment analyst',
            'diligence associate',
            'like a deal team',
            'true fit',
            'true-fit',
            'scored by fit',
            'due-diligence-ready',
            'bank-grade',
            'military-grade',
            'fully secure',
        ):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, content)

    def test_no_unshipped_capabilities_advertised(self):
        content = self._home().content.decode('utf-8').lower()
        for phrase in ('competitor', 'benchmark', 'expert review', 'percentile'):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, content)

    def test_authenticated_home_has_personalized_progress_hook(self):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user('homepage_progress', password='x')
        self.client.force_login(user)
        response = self.client.get(reverse('pages:home'))
        self.assertContains(response, 'Welcome back')
        self.assertContains(response, 'home-journey-loading')
        self.assertContains(response, '/api/v1/zelda/journey-status/')
        self.assertContains(response, 'home-next-action')

    def test_no_role_specific_landing_pages_introduced(self):
        content = self._home().content.decode('utf-8')
        for path in ('href="/founders', 'href="/investors', 'href="/buyers', 'href="/sellers'):
            self.assertNotIn(path, content)

