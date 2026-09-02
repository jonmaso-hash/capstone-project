"""
Coverage for the social-login integration point: post_login_router (the
LOGIN_REDIRECT_URL target allauth's social-login flow consults) and
choose_role (the role-picker a first-time social-login user with no
Founder/Investor/Seller/Buyer profile lands on).
"""
import tempfile
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.forms import ApplicationForm, CommaFormattedNumberInput
from matchmaking.models import Application, InvestorApplication
from matchmaking.tests import _mock_embedding_generation

User = get_user_model()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SignupViewTests(TestCase):
    """
    Regression coverage for signup_view actually completing a real signup
    POST — allauth's AUTHENTICATION_BACKENDS addition (ModelBackend +
    allauth's backend) means auth_login() must be given an explicit backend
    for a freshly form.save()'d user (who has no .backend attribute the way
    authenticate()'d users do), or Django raises ValueError.
    """
    def test_signup_post_creates_user_and_logs_in(self):
        response = self.client.post(reverse('accounts:signup'), {
            'username': 'signup_regression_user',
            'password1': 'TempAudit!2026xyz',
            'password2': 'TempAudit!2026xyz',
            'role': 'buyer',
        })

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username='signup_regression_user')

        # the real signal auth_login() succeeded — session is tied to this user
        self.assertEqual(self.client.session['_auth_user_id'], str(user.id))

    def test_signup_creates_the_platform_disclaimer_notification(self):
        """The 'no money changes hands on-platform / not a broker, escrow,
        or trustee' disclosure must reach every new password-signup user as
        their first notification — see PLATFORM_DISCLAIMER_MESSAGE."""
        from accounts.views import PLATFORM_DISCLAIMER_MESSAGE
        from notifications.models import Notification
        self.client.post(reverse('accounts:signup'), {
            'username': 'disclaimer_signup_user',
            'password1': 'TempAudit!2026xyz',
            'password2': 'TempAudit!2026xyz',
            'role': 'founder',
        })
        user = User.objects.get(username='disclaimer_signup_user')
        notif = Notification.objects.get(recipient=user, notification_type='SYSTEM')
        self.assertEqual(notif.message, PLATFORM_DISCLAIMER_MESSAGE)
        self.assertIn('not a broker-dealer, escrow agent, or trustee', notif.message)
        self.assertIn('off-platform', notif.message)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PostLoginRouterTests(TestCase):
    def setUp(self):
        _mock_embedding_generation(self)

    def test_founder_routes_to_founder_dashboard(self):
        user = User.objects.create_user('router_founder', password='x')
        Application.objects.create(
            user=user, founder_name='F', email='f@t.com', company_name='FCo',
            sector='SaaS', stage='Seed', description='test', is_private=False,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('accounts:post_login_router'))

        self.assertRedirects(response, reverse('matchmaking:founder_dashboard'))

    def test_investor_routes_to_investor_dashboard(self):
        user = User.objects.create_user('router_investor', password='x')
        InvestorApplication.objects.create(
            user=user, full_name='I', email='i@t.com', company_name='ICo',
            investment_focus='SaaS', investment_stage='Seed', is_private=False,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('accounts:post_login_router'))

        self.assertRedirects(response, reverse('matchmaking:investor_dashboard'))

    def test_bare_user_routes_to_choose_role(self):
        user = User.objects.create_user('router_bare', password='x')
        self.client.force_login(user)

        response = self.client.get(reverse('accounts:post_login_router'))

        self.assertRedirects(response, reverse('accounts:choose_role'))

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse('accounts:post_login_router'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)


class ChooseRoleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('choose_role_user', password='x')
        self.client.force_login(self.user)

    def test_get_renders_role_cards(self):
        response = self.client.get(reverse('accounts:choose_role'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'roleSelector')

    def test_post_founder_redirects_to_edit_founder_profile(self):
        response = self.client.post(reverse('accounts:choose_role'), {'role': 'founder'})
        self.assertRedirects(response, reverse('usersettings:edit_founder_profile'))

    def test_post_buyer_redirects_to_edit_buyer_profile(self):
        response = self.client.post(reverse('accounts:choose_role'), {'role': 'buyer'})
        self.assertRedirects(response, reverse('usersettings:edit_buyer_profile'))

    def test_post_invalid_role_rejected(self):
        response = self.client.post(reverse('accounts:choose_role'), {'role': 'admin'}, follow=True)
        self.assertContains(response, "pick Founder, Investor, Seller, or Buyer")

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('accounts:choose_role'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_choosing_a_role_creates_the_platform_disclaimer_notification(self):
        """Social-login signups never go through signup_view (no username/
        password form), so choose_role is the only place they'd otherwise
        see the same disclosure password-signup users get — see
        PLATFORM_DISCLAIMER_MESSAGE and SignupViewTests' equivalent check."""
        from accounts.views import PLATFORM_DISCLAIMER_MESSAGE
        from notifications.models import Notification
        self.client.post(reverse('accounts:choose_role'), {'role': 'founder'})
        notif = Notification.objects.get(recipient=self.user, notification_type='SYSTEM')
        self.assertEqual(notif.message, PLATFORM_DISCLAIMER_MESSAGE)

    def test_revisiting_choose_role_does_not_duplicate_the_notification(self):
        from notifications.models import Notification
        self.client.post(reverse('accounts:choose_role'), {'role': 'founder'})
        self.client.post(reverse('accounts:choose_role'), {'role': 'founder'})
        self.assertEqual(Notification.objects.filter(recipient=self.user, notification_type='SYSTEM').count(), 1)


class CommaFormattedNumberInputTests(TestCase):
    """
    CommaFormattedNumberInput: comma-formatted display + comma-stripping on
    submit for raising_amount/prior_amount_raised/current_revenue/
    monthly_burn_rate. value_from_datadict has to strip commas (not a
    clean_<field> method) since DecimalField.to_python raises on a
    comma-containing string before clean_<field> would ever run.
    """

    def test_format_value_adds_commas(self):
        widget = CommaFormattedNumberInput()
        self.assertEqual(widget.format_value(500000), '500,000')

    def test_format_value_handles_none_and_empty(self):
        widget = CommaFormattedNumberInput()
        self.assertEqual(widget.format_value(None), '')
        self.assertEqual(widget.format_value(''), '')

    def test_value_from_datadict_strips_commas(self):
        widget = CommaFormattedNumberInput()
        value = widget.value_from_datadict({'amount': '1,500,000'}, {}, 'amount')
        self.assertEqual(value, '1500000')

    def test_value_from_datadict_preserves_decimal_point(self):
        widget = CommaFormattedNumberInput()
        value = widget.value_from_datadict({'amount': '1,234.50'}, {}, 'amount')
        self.assertEqual(value, '1234.50')

    @override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
    def test_application_form_accepts_comma_formatted_currency_fields(self):
        with mock.patch('matchmaking.signals.generate_profile_embedding', return_value=[]):
            data = {
                'company_name': 'Test Co', 'founder_name': 'F', 'email': 'commas@t.com',
                'description': 'A test startup description.', 'sector': 'SaaS', 'stage': 'Seed',
                'raising_amount': '1,500,000', 'team_size': '5', 'prior_amount_raised': '250,000',
                'years_in_business': '2', 'current_revenue': '10,000', 'monthly_burn_rate': '5,000',
            }
            form = ApplicationForm(data)
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data['raising_amount'], 1500000)
            self.assertEqual(form.cleaned_data['prior_amount_raised'], 250000)
            self.assertEqual(form.cleaned_data['current_revenue'], 10000)
            self.assertEqual(form.cleaned_data['monthly_burn_rate'], 5000)


class ApplicationFormLabelTests(TestCase):
    def test_years_in_business_relabeled(self):
        form = ApplicationForm()
        self.assertEqual(form.fields['years_in_business'].label, 'Years Since Founding')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ProfileAnalysisAccessTests(TestCase):
    """
    Profile Analysis (the renamed, merged Deck Analytics) is strictly
    owner-only — unlike the old deck_analytics view, staff get no bypass.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.owner = User.objects.create_user('analysis_owner', password='x')
        self.other_user = User.objects.create_user('analysis_other', password='x')
        self.staff_user = User.objects.create_user('analysis_staff', password='x', is_staff=True)
        Application.objects.create(
            user=self.owner, company_name='AnalysisCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )

    def test_owner_can_view_their_own_analysis(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('accounts:profile_analysis', args=[self.owner.username]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Founder Insights')

    def test_other_user_is_redirected_away(self):
        self.client.force_login(self.other_user)
        response = self.client.get(reverse('accounts:profile_analysis', args=[self.owner.username]))
        self.assertRedirects(response, reverse('accounts:profile', args=[self.owner.username]))

    def test_staff_gets_no_bypass(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('accounts:profile_analysis', args=[self.owner.username]))
        self.assertRedirects(response, reverse('accounts:profile', args=[self.owner.username]))

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse('accounts:profile_analysis', args=[self.owner.username]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ProfileAnalysisPaywallTests(TestCase):
    """
    Founder/Seller Insights — profile_analysis's Premium-gated funnel,
    trending, Marketplace Score, Zelda Insights, opportunity alerts,
    recommendations, and interest timeline (matchmaking.insights_engine).
    Free tier gets exactly three numbers (Profile Views, Intro Requests,
    Thumbs Up) and nothing else from the marketplace-interest section;
    Investor/Buyer's own (much smaller) analytics were never gated and
    must keep working exactly as before.
    """

    def setUp(self):
        _mock_embedding_generation(self)

    def _founder(self, username, is_premium):
        user = User.objects.create_user(username, password='x')
        app = Application.objects.create(
            user=user, company_name=f'{username}Co', founder_name='F', email=f'{username}@t.com',
            description='test', sector='SaaS', stage='Seed', is_premium=is_premium,
        )
        return user, app

    def test_free_founder_sees_only_three_basic_numbers(self):
        from matchmaking.models import InvestorInterestEvent
        user, app = self._founder('paywall_free_founder', is_premium=False)
        investor = User.objects.create_user('paywall_free_investor', password='x')
        InvestorInterestEvent.objects.create(investor=investor, founder=app, event_type='view')
        InvestorInterestEvent.objects.create(investor=investor, founder=app, event_type='memo_view')
        self.client.force_login(user)

        response = self.client.get(reverse('accounts:profile_analysis', args=[user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['is_premium_insights'])
        self.assertContains(response, 'Unlock Founder Insights')
        self.assertNotContains(response, 'Marketplace Score')
        self.assertNotContains(response, 'Profile Funnel')
        self.assertNotContains(response, 'Zelda Insights')
        self.assertNotContains(response, 'Next Best Actions')
        # Memo Views is a premium-only stat — must not leak into the free view.
        self.assertNotContains(response, 'Memo Views')

    def test_premium_founder_sees_full_insights_suite(self):
        from matchmaking.models import InvestorInterestEvent
        user, app = self._founder('paywall_premium_founder', is_premium=True)
        investor = User.objects.create_user('paywall_premium_investor', password='x')
        InvestorInterestEvent.objects.create(investor=investor, founder=app, event_type='view')
        InvestorInterestEvent.objects.create(investor=investor, founder=app, event_type='memo_view')
        self.client.force_login(user)

        response = self.client.get(reverse('accounts:profile_analysis', args=[user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_premium_insights'])
        self.assertContains(response, 'Marketplace Score')
        self.assertContains(response, 'Profile Funnel')
        self.assertContains(response, 'Conversion Rates')
        self.assertContains(response, 'Zelda Insights')
        self.assertContains(response, 'Next Best Actions')
        self.assertIn('funnel_stats', response.context)
        self.assertIn('engagement_score', response.context)

    def test_premium_founder_sees_investor_focus_breakdown(self):
        from matchmaking.models import InvestorInterestEvent
        user, app = self._founder('paywall_focus_founder', is_premium=True)
        investor_user = User.objects.create_user('paywall_focus_investor', password='x')
        InvestorApplication.objects.create(user=investor_user, investment_stage='Seed', investment_focus='SaaS')
        InvestorInterestEvent.objects.create(investor=investor_user, founder=app, event_type='view')
        self.client.force_login(user)

        response = self.client.get(reverse('accounts:profile_analysis', args=[user.username]))

        self.assertEqual(response.context['focus_breakdown']['unique_viewers'], 1)
        self.assertEqual(response.context['focus_breakdown']['by_stage'], {'Seed': 1})
        self.assertContains(response, "Who's Interested")

    def test_free_seller_sees_only_three_basic_numbers(self):
        from matchmaking.models import SellerApplication
        user = User.objects.create_user('paywall_free_seller', password='x')
        SellerApplication.objects.create(
            user=user, company_name='SellerCo', seller_name='S', email='s@t.com',
            description='test business', is_premium=False,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('accounts:profile_analysis', args=[user.username]))

        self.assertFalse(response.context['is_premium_insights'])
        self.assertContains(response, 'Unlock Seller Insights')
        self.assertNotContains(response, 'Marketplace Score')

    def test_premium_seller_sees_full_insights_suite(self):
        from matchmaking.models import SellerApplication
        user = User.objects.create_user('paywall_premium_seller', password='x')
        SellerApplication.objects.create(
            user=user, company_name='SellerCo', seller_name='S', email='s@t.com',
            description='test business', is_premium=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('accounts:profile_analysis', args=[user.username]))

        self.assertTrue(response.context['is_premium_insights'])
        self.assertContains(response, 'Marketplace Score')

    def test_investor_analytics_unaffected_by_paywall(self):
        """Investor/Buyer's own outbound-activity stats were never gated — must keep rendering exactly as before."""
        user = User.objects.create_user('paywall_investor_unaffected', password='x')
        InvestorApplication.objects.create(user=user, investment_stage='Seed', investment_focus='SaaS')
        self.client.force_login(user)

        response = self.client.get(reverse('accounts:profile_analysis', args=[user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['has_analytics_paywall'])
        self.assertContains(response, 'Profile Analysis')
        # Narrower than a bare 'Unlock' substring check — the sidebar's
        # globally-included Zelda widget script now contains that word in
        # its own (unrelated) locked-memo-card JS string literal, so a
        # page-wide substring match isn't a reliable signal anymore.
        self.assertNotContains(response, 'Unlock Founder Insights')
        self.assertNotContains(response, 'Unlock Seller Insights')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ProfileViewCountToggleTests(TestCase):
    """
    show_profile_view_count controls whether OTHER visitors see the badge
    on profile.html — the owner always sees their own count regardless.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.owner = User.objects.create_user('count_toggle_owner', password='x')
        self.viewer = User.objects.create_user('count_toggle_viewer', password='x')
        Application.objects.create(
            user=self.owner, company_name='ToggleCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        from matchmaking.models import InvestorInterestEvent
        InvestorInterestEvent.objects.create(investor=self.viewer, founder=self.owner.match_founder_profile, event_type='view')

    def test_visible_to_other_viewer_by_default(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('accounts:profile', args=[self.owner.username]))
        self.assertContains(response, 'profile view')

    def test_hidden_from_other_viewer_when_toggled_off(self):
        from usersettings.models import UserSettings
        settings_obj = UserSettings.for_user(self.owner)
        settings_obj.show_profile_view_count = False
        settings_obj.save()

        self.client.force_login(self.viewer)
        response = self.client.get(reverse('accounts:profile', args=[self.owner.username]))
        self.assertNotContains(response, 'profile view')

    def test_owner_always_sees_their_own_count_even_when_toggled_off(self):
        from usersettings.models import UserSettings
        settings_obj = UserSettings.for_user(self.owner)
        settings_obj.show_profile_view_count = False
        settings_obj.save()

        self.client.force_login(self.owner)
        response = self.client.get(reverse('accounts:profile', args=[self.owner.username]))
        self.assertContains(response, 'profile view')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class InvestorBuyerProfileViewTrackingTests(TestCase):
    """
    Investor/buyer profiles had zero view tracking before ProfileView —
    accounts.views.profile() now logs one row per non-owner authenticated
    visit, and profile_analysis() reads the count back from it.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.investor_user = User.objects.create_user('view_tracking_investor', password='x')
        self.founder_user = User.objects.create_user('view_tracking_founder', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='Inv', company_name='Firm', email='i@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )

    def test_viewing_investor_profile_creates_a_profile_view_row(self):
        from matchmaking.models import ProfileView
        self.client.force_login(self.founder_user)
        self.client.get(reverse('accounts:profile', args=[self.investor_user.username]))
        self.assertEqual(ProfileView.objects.filter(viewed_user=self.investor_user).count(), 1)

    def test_self_view_does_not_create_a_profile_view_row(self):
        from matchmaking.models import ProfileView
        self.client.force_login(self.investor_user)
        self.client.get(reverse('accounts:profile', args=[self.investor_user.username]))
        self.assertEqual(ProfileView.objects.filter(viewed_user=self.investor_user).count(), 0)

    def test_investor_profile_analysis_reports_view_count_from_profile_view(self):
        self.client.force_login(self.founder_user)
        self.client.get(reverse('accounts:profile', args=[self.investor_user.username]))

        self.client.force_login(self.investor_user)
        response = self.client.get(reverse('accounts:profile_analysis', args=[self.investor_user.username]))
        self.assertEqual(response.context['total_views'], 1)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class BusinessVerificationViewTests(TestCase):
    """
    accounts/views.py::business_verification / _request / _confirm — the
    self-serve flow that flips is_verified on whichever role profile(s) a
    user has. EMAIL_BACKEND is overridden to locmem so the real Gmail SMTP
    configured in settings is never hit by the test suite.
    """

    def setUp(self):
        cache.clear()
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('bev_founder', password='x')
        self.founder = Application.objects.create(
            user=self.founder_user, company_name='Interlink Foundry', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(reverse('accounts:business_verification'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url)

        response = self.client.post(reverse('accounts:business_verification_request'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url)

        response = self.client.post(reverse('accounts:business_verification_confirm'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url)

    def test_matching_domain_creates_pending_row_and_sends_mail(self):
        from django.core import mail
        from matchmaking.models import BusinessEmailVerification
        self.client.force_login(self.founder_user)
        response = self.client.post(reverse('accounts:business_verification_request'), {
            'business_email': 'jon@interlinkfoundry.com',
        })
        self.assertEqual(response.status_code, 302)
        verification = BusinessEmailVerification.objects.get(user=self.founder_user)
        self.assertEqual(verification.status, 'PENDING')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(verification.code, mail.outbox[0].body)

    def test_mismatched_domain_creates_no_row_and_sends_no_mail(self):
        from django.core import mail
        from matchmaking.models import BusinessEmailVerification
        self.client.force_login(self.founder_user)
        self.client.post(reverse('accounts:business_verification_request'), {
            'business_email': 'jon@totallyunrelated.com',
        })
        self.assertEqual(BusinessEmailVerification.objects.filter(user=self.founder_user).count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_user_with_no_role_profile_gets_clean_error(self):
        from matchmaking.models import BusinessEmailVerification
        bare_user = User.objects.create_user('bev_bare', password='x')
        self.client.force_login(bare_user)
        self.client.post(reverse('accounts:business_verification_request'), {
            'business_email': 'jon@anything.com',
        })
        self.assertEqual(BusinessEmailVerification.objects.filter(user=bare_user).count(), 0)

    def test_resend_cooldown_blocks_immediate_second_request(self):
        from matchmaking.models import BusinessEmailVerification
        self.client.force_login(self.founder_user)
        self.client.post(reverse('accounts:business_verification_request'), {'business_email': 'jon@interlinkfoundry.com'})
        self.client.post(reverse('accounts:business_verification_request'), {'business_email': 'jon@interlinkfoundry.com'})
        self.assertEqual(BusinessEmailVerification.objects.filter(user=self.founder_user).count(), 1)

    def test_correct_code_verifies_all_of_a_multi_role_users_profiles(self):
        from matchmaking.models import BusinessEmailVerification, InvestorApplication
        InvestorApplication.objects.create(
            user=self.founder_user, full_name='F', company_name='Interlink Foundry', email='f2@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.client.force_login(self.founder_user)
        self.client.post(reverse('accounts:business_verification_request'), {'business_email': 'jon@interlinkfoundry.com'})
        verification = BusinessEmailVerification.objects.get(user=self.founder_user)

        self.client.post(reverse('accounts:business_verification_confirm'), {'code': verification.code})

        verification.refresh_from_db()
        self.assertEqual(verification.status, 'VERIFIED')
        self.assertIsNotNone(verification.verified_at)
        self.founder.refresh_from_db()
        self.assertTrue(self.founder.is_verified)
        self.assertTrue(InvestorApplication.objects.get(user=self.founder_user).is_verified)

    def test_wrong_code_does_not_verify_and_increments_attempts(self):
        from matchmaking.models import BusinessEmailVerification
        self.client.force_login(self.founder_user)
        self.client.post(reverse('accounts:business_verification_request'), {'business_email': 'jon@interlinkfoundry.com'})
        verification = BusinessEmailVerification.objects.get(user=self.founder_user)

        self.client.post(reverse('accounts:business_verification_confirm'), {'code': '000000'})

        verification.refresh_from_db()
        self.assertEqual(verification.status, 'PENDING')
        self.assertEqual(verification.attempts, 1)
        self.founder.refresh_from_db()
        self.assertFalse(self.founder.is_verified)

    def test_fifth_wrong_attempt_locks_the_row(self):
        from matchmaking.models import BusinessEmailVerification
        self.client.force_login(self.founder_user)
        self.client.post(reverse('accounts:business_verification_request'), {'business_email': 'jon@interlinkfoundry.com'})
        verification = BusinessEmailVerification.objects.get(user=self.founder_user)

        for _ in range(BusinessEmailVerification.MAX_ATTEMPTS):
            self.client.post(reverse('accounts:business_verification_confirm'), {'code': '000000'})

        verification.refresh_from_db()
        self.assertEqual(verification.status, 'LOCKED')

        # even the correct code is now rejected — there's no PENDING row left
        self.client.post(reverse('accounts:business_verification_confirm'), {'code': verification.code})
        self.founder.refresh_from_db()
        self.assertFalse(self.founder.is_verified)

    def test_expired_row_is_rejected_and_flips_to_expired(self):
        from matchmaking.models import BusinessEmailVerification
        self.client.force_login(self.founder_user)
        self.client.post(reverse('accounts:business_verification_request'), {'business_email': 'jon@interlinkfoundry.com'})
        verification = BusinessEmailVerification.objects.get(user=self.founder_user)
        BusinessEmailVerification.objects.filter(pk=verification.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        self.client.post(reverse('accounts:business_verification_confirm'), {'code': verification.code})

        verification.refresh_from_db()
        self.assertEqual(verification.status, 'EXPIRED')
        self.founder.refresh_from_db()
        self.assertFalse(self.founder.is_verified)

    def test_confirm_with_no_pending_row_is_a_clean_error_not_a_500(self):
        self.client.force_login(self.founder_user)
        response = self.client.post(reverse('accounts:business_verification_confirm'), {'code': '123456'})
        self.assertEqual(response.status_code, 302)


class VerificationHistoryProfileTests(TestCase):
    """
    accounts.views.profile()'s verification_history context — the trust
    trend across every Truth Delta run for a founder/seller's documents,
    surfaced on their public profile. Same viewer gate as the underlying
    single-document Truth Delta page (owner, any investor/buyer, or
    staff) — deliberately not connection-gated like IC Memo, since this
    aggregates data already viewable one document at a time.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        from zelda_api.vector_models import DocumentSource
        from zelda_api.truth_delta_models import TruthDeltaReport

        self.founder_user = User.objects.create_user('vh_founder', password='x')
        self.application = Application.objects.create(
            user=self.founder_user, company_name='VHCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed', is_premium=True,
        )
        doc1 = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='seed_deck.pdf', source_entity='VHCo', document_type='pitch_deck',
        )
        doc2 = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='series_a_deck.pdf', source_entity='VHCo', document_type='pitch_deck',
        )
        self.older_report = TruthDeltaReport.objects.create(
            document=doc1, overall_truth_score=90.0, credibility_risk='low', summary='Seed round claims check out.',
        )
        self.newer_report = TruthDeltaReport.objects.create(
            document=doc2, overall_truth_score=82.0, credibility_risk='medium', summary='Series A claims mostly check out.',
        )

        self.investor_user = User.objects.create_user('vh_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='Fund', email='i@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.stranger_user = User.objects.create_user('vh_stranger', password='x')

    def test_owner_sees_full_history_most_recent_first(self):
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('accounts:profile', args=[self.founder_user.username]))
        history = list(response.context['verification_history'])
        self.assertEqual(history, [self.newer_report, self.older_report])

    def test_investor_viewer_sees_history(self):
        self.client.force_login(self.investor_user)
        response = self.client.get(reverse('accounts:profile', args=[self.founder_user.username]))
        self.assertEqual(len(response.context['verification_history']), 2)

    def test_viewer_with_no_role_sees_no_history(self):
        """A stranger with no investor/buyer/staff role and not the owner shouldn't see verification data at all."""
        self.client.force_login(self.stranger_user)
        response = self.client.get(reverse('accounts:profile', args=[self.founder_user.username]))
        self.assertEqual(response.context['verification_history'], [])

    def test_trend_and_stats_are_attached_to_each_report(self):
        """
        The two reports in setUp have empty `details`, so this exercises
        the wiring itself (report.stats/.trend exist and are the right
        shape) — TruthDeltaReportRollupAndTrendTests in zelda_api/tests.py
        covers the underlying diff/rollup logic with real per_claim data.
        """
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('accounts:profile', args=[self.founder_user.username]))
        history = list(response.context['verification_history'])
        newest, oldest = history[0], history[1]
        self.assertEqual(newest.stats, {'total': 0, 'verified': 0, 'pct': None})
        self.assertEqual(newest.trend, {'newly_verified': [], 'lost_verification': []})
        self.assertIsNone(oldest.trend, "the oldest report has no prior report to diff against")

    def test_anonymous_visitor_is_redirected_to_login(self):
        """profile() is @login_required — confirms there's no anonymous path that could leak verification_history."""
        response = self.client.get(reverse('accounts:profile', args=[self.founder_user.username]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_founder_with_no_documents_has_empty_history_not_an_error(self):
        empty_founder = User.objects.create_user('vh_empty_founder', password='x')
        Application.objects.create(
            user=empty_founder, company_name='EmptyCo', founder_name='F', email='e@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.client.force_login(empty_founder)
        response = self.client.get(reverse('accounts:profile', args=[empty_founder.username]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['verification_history'], [])


class VerifiedFundedSoldBadgeProfileTests(TestCase):
    """
    profile()'s has_verified_funded/has_verified_sold context — FUNDED/CLOSED
    is a two-sided, counterparty-confirmed state (see
    matchmaking.views.connection_action_view/acquisition_connection_action_view
    and matchmaking.tests.LogTrainingExampleTests /
    AcquisitionFundedClosedConfirmationTests for the confirmation flow itself),
    so it's safe to surface as a trust badge here. This only checks the
    badge appears for the genuine terminal state, not the self-reported
    _PENDING one.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        from matchmaking.models import Connection, SellerApplication, BuyerApplication, AcquisitionConnection
        self.Connection = Connection
        self.AcquisitionConnection = AcquisitionConnection

        self.founder_user = User.objects.create_user('vfb_founder', password='x')
        self.application = Application.objects.create(
            user=self.founder_user, company_name='FundedCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.investor_user = User.objects.create_user('vfb_investor', password='x')
        self.investor = InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='Fund', email='i@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )

        self.seller_user = User.objects.create_user('vfb_seller', password='x')
        self.seller = SellerApplication.objects.create(
            user=self.seller_user, company_name='SoldCo', seller_name='S', email='s@t.com',
            description='test', industry='SaaS',
        )
        self.buyer_user = User.objects.create_user('vfb_buyer', password='x')
        self.buyer = BuyerApplication.objects.create(
            user=self.buyer_user, full_name='B', company_name='Acquirer', email='b@t.com',
        )

    def test_funded_connection_shows_verified_funded_badge(self):
        self.Connection.objects.create(founder=self.application, investor=self.investor, status='FUNDED', initiated_by='FOUNDER')
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('accounts:profile', args=[self.founder_user.username]))
        self.assertTrue(response.context['has_verified_funded'])
        self.assertContains(response, 'Verified Funded')

    def test_funded_pending_connection_does_not_show_badge(self):
        """A founder's unilateral claim (FUNDED_PENDING) is not yet a verified fact."""
        self.Connection.objects.create(founder=self.application, investor=self.investor, status='FUNDED_PENDING', initiated_by='FOUNDER')
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('accounts:profile', args=[self.founder_user.username]))
        self.assertFalse(response.context['has_verified_funded'])
        self.assertNotContains(response, 'Verified Funded')

    def test_closed_acquisition_connection_shows_verified_sold_badge(self):
        self.AcquisitionConnection.objects.create(seller=self.seller, buyer=self.buyer, status='CLOSED', initiated_by='SELLER')
        self.client.force_login(self.seller_user)
        response = self.client.get(reverse('accounts:profile', args=[self.seller_user.username]))
        self.assertTrue(response.context['has_verified_sold'])
        self.assertContains(response, 'Verified Sold')

    def test_closed_pending_acquisition_connection_does_not_show_badge(self):
        self.AcquisitionConnection.objects.create(seller=self.seller, buyer=self.buyer, status='CLOSED_PENDING', initiated_by='SELLER')
        self.client.force_login(self.seller_user)
        response = self.client.get(reverse('accounts:profile', args=[self.seller_user.username]))
        self.assertFalse(response.context['has_verified_sold'])
        self.assertNotContains(response, 'Verified Sold')

    def test_founder_with_no_deals_has_no_badge(self):
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('accounts:profile', args=[self.founder_user.username]))
        self.assertFalse(response.context['has_verified_funded'])
        self.assertFalse(response.context['has_verified_sold'])
        self.assertEqual(response.context['verified_track_record'], [])
        self.assertNotContains(response, 'Verified Track Record')

    def test_founder_track_record_shows_investor_company_and_is_drillable(self):
        self.Connection.objects.create(founder=self.application, investor=self.investor, status='FUNDED', initiated_by='FOUNDER')
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('accounts:profile', args=[self.founder_user.username]))
        record = response.context['verified_track_record']
        self.assertEqual(len(record), 1)
        self.assertEqual(record[0]['label'], 'Funded by 1 investor')
        self.assertEqual(record[0]['transactions'][0]['counterparty'], 'Fund')
        self.assertContains(response, 'Verified Track Record')
        self.assertContains(response, 'Funded by 1 investor')
        self.assertContains(response, 'Fund')

    def test_investor_with_funded_connection_shows_verified_funded_badge_and_track_record(self):
        self.Connection.objects.create(founder=self.application, investor=self.investor, status='FUNDED', initiated_by='FOUNDER')
        self.client.force_login(self.investor_user)
        response = self.client.get(reverse('accounts:profile', args=[self.investor_user.username]))
        self.assertTrue(response.context['has_verified_funded'])
        self.assertContains(response, 'Verified Funded')
        record = response.context['verified_track_record']
        self.assertEqual(record[0]['label'], '1 company funded')
        self.assertEqual(record[0]['transactions'][0]['counterparty'], 'FundedCo')

    def test_buyer_with_closed_connection_shows_verified_sold_badge_and_track_record(self):
        self.AcquisitionConnection.objects.create(seller=self.seller, buyer=self.buyer, status='CLOSED', initiated_by='SELLER')
        self.client.force_login(self.buyer_user)
        response = self.client.get(reverse('accounts:profile', args=[self.buyer_user.username]))
        self.assertTrue(response.context['has_verified_sold'])
        self.assertContains(response, 'Verified Sold')
        record = response.context['verified_track_record']
        self.assertEqual(record[0]['label'], '1 company acquired')
        self.assertEqual(record[0]['transactions'][0]['counterparty'], 'SoldCo')


class ProfileShareButtonTests(TestCase):
    """
    "Share Profile" — profile.html's fourth ContentShare entry point (see
    sharing.views._resolve_profile). Visible to any authenticated viewer,
    including the owner viewing their own page (sharing your own profile
    externally is the primary acquisition-loop use case) — the live
    resolver, not this button, is what enforces privacy.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('psb_founder', password='x')
        self.application = Application.objects.create(
            user=self.founder_user, company_name='PSBCo', founder_name='F', email='psb@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.viewer = User.objects.create_user('psb_viewer', password='x')

    def test_share_button_renders_with_correct_content_type_and_id(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('accounts:profile', args=[self.founder_user.username]))
        self.assertContains(response, f"openContentShare('PROFILE', {self.founder_user.id}")
        self.assertContains(response, 'Share Profile')

    def test_owner_sees_the_share_button_on_their_own_profile(self):
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('accounts:profile', args=[self.founder_user.username]))
        self.assertContains(response, 'Share Profile')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class InvestorReadinessCenterTests(TestCase):
    """
    accounts.views._get_investor_readiness — every dimension must come from
    real, already-computed data (confidence_breakdown, TruthDeltaReport,
    is_verified), never a fabricated score. Gated by the same
    can_view_ic_memo rule as the IC Memo itself (owner, staff, or an
    investor with an ACCEPTED Connection) — deliberately reusing that gate
    rather than inventing a second visibility rule for a closely related
    panel.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        from matchmaking.models import Connection
        self.Connection = Connection

        self.founder_user = User.objects.create_user('irc_founder', password='x')
        self.application = Application.objects.create(
            user=self.founder_user, company_name='ReadyCo', founder_name='F', email='irc@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.investor_user = User.objects.create_user('irc_investor', password='x')
        self.investor = InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='Fund', email='irci@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.stranger_investor_user = User.objects.create_user('irc_stranger', password='x')
        InvestorApplication.objects.create(
            user=self.stranger_investor_user, full_name='S', company_name='OtherFund', email='ircs@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.staff_user = User.objects.create_user('irc_staff', password='x', is_staff=True)

    def _profile_url(self):
        return reverse('accounts:profile', args=[self.founder_user.username])

    def test_panel_hidden_for_unrelated_investor(self):
        self.client.force_login(self.stranger_investor_user)
        response = self.client.get(self._profile_url())
        self.assertIsNone(response.context['investor_readiness'])
        self.assertNotContains(response, 'Investor Readiness')

    def test_panel_visible_to_owner(self):
        self.client.force_login(self.founder_user)
        response = self.client.get(self._profile_url())
        self.assertIsNotNone(response.context['investor_readiness'])
        self.assertContains(response, 'Investor Readiness')

    def test_panel_visible_to_staff(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(self._profile_url())
        self.assertIsNotNone(response.context['investor_readiness'])
        self.assertContains(response, 'Investor Readiness')

    def test_panel_visible_to_accepted_investor(self):
        self.Connection.objects.create(founder=self.application, investor=self.investor, status='ACCEPTED', initiated_by='INVESTOR')
        self.client.force_login(self.investor_user)
        response = self.client.get(self._profile_url())
        self.assertIsNotNone(response.context['investor_readiness'])
        self.assertContains(response, 'Investor Readiness')

    def test_no_analyzed_documents_renders_dashes_not_fabricated_zeros(self):
        """A founder who's never uploaded anything gets `None` (rendered as —), not a fake 0%."""
        self.client.force_login(self.founder_user)
        response = self.client.get(self._profile_url())
        readiness = response.context['investor_readiness']
        self.assertIsNone(readiness['market_evidence_pct'])
        self.assertIsNone(readiness['financial_disclosure_pct'])
        self.assertIsNone(readiness['company_verification_pct'])
        self.assertEqual(readiness['founder_verification_pct'], 0)
        self.assertEqual(readiness['materials'], [])
        self.assertContains(response, 'No investor materials available yet.')

    def test_is_verified_founder_shows_100_percent_founder_verification(self):
        self.application.is_verified = True
        self.application.save(update_fields=['is_verified'])
        self.client.force_login(self.founder_user)
        response = self.client.get(self._profile_url())
        self.assertEqual(response.context['investor_readiness']['founder_verification_pct'], 100)

    def test_market_evidence_pct_derives_from_real_insight_confidence(self):
        from zelda_api.vector_models import DocumentSource, IntelligenceInsight
        doc = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='deck.pdf', source_entity='ReadyCo',
            document_type='pitch_deck', status='analyzed',
        )
        IntelligenceInsight.objects.create(
            document=doc, category='Market', insight_text='TAM is $10B', confidence_score=82,
        )
        self.client.force_login(self.founder_user)
        response = self.client.get(self._profile_url())
        self.assertEqual(response.context['investor_readiness']['market_evidence_pct'], 82)

    def test_company_verification_pct_derives_from_real_truth_delta_score(self):
        from zelda_api.vector_models import DocumentSource
        from zelda_api.truth_delta_models import TruthDeltaReport
        doc = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='deck.pdf', source_entity='ReadyCo',
            document_type='pitch_deck', status='analyzed',
        )
        TruthDeltaReport.objects.create(document=doc, overall_truth_score=73.4, credibility_risk='medium')
        self.client.force_login(self.founder_user)
        response = self.client.get(self._profile_url())
        self.assertEqual(response.context['investor_readiness']['company_verification_pct'], 73)

    def test_no_truth_delta_report_leaves_company_verification_none(self):
        from zelda_api.vector_models import DocumentSource
        DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='deck.pdf', source_entity='ReadyCo',
            document_type='pitch_deck', status='analyzed',
        )
        self.client.force_login(self.founder_user)
        response = self.client.get(self._profile_url())
        self.assertIsNone(response.context['investor_readiness']['company_verification_pct'])

    def test_financial_disclosure_pct_derives_from_real_structured_facts(self):
        from zelda_api.vector_models import DocumentSource, IntelligenceInsight
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        doc = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='deck.pdf', source_entity='ReadyCo',
            document_type='pitch_deck', status='analyzed',
        )
        IntelligenceInsight.objects.create(
            document=doc, category='Revenue', insight_text='ARR is $1M', confidence_score=70,
        )
        # 3 of the 7 FINANCIAL_COMPLETENESS_FIELDS disclosed -> 3/7 -> round(42.857) == 43
        facts = {'arr': '$1M', 'raise_amount': '$5M', 'market_size': '$10B'}
        with mock.patch.object(ZeldaIntelligencePipelineV2, '_build_structured_context', return_value=facts):
            self.client.force_login(self.founder_user)
            response = self.client.get(self._profile_url())
        self.assertEqual(response.context['investor_readiness']['financial_disclosure_pct'], 43)

    def test_materials_checklist_only_lists_genuinely_existing_artifacts(self):
        from zelda_api.vector_models import DocumentSource, IntelligenceMemo
        from zelda_api.truth_delta_models import TruthDeltaReport
        from matchmaking.models import DataRoomDocument
        doc = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='deck.pdf', source_entity='ReadyCo',
            document_type='pitch_deck', status='analyzed',
        )
        IntelligenceMemo.objects.create(
            document=doc, executive_summary='x', investment_thesis='x',
        )
        TruthDeltaReport.objects.create(document=doc, overall_truth_score=90.0, credibility_risk='low')
        DataRoomDocument.objects.create(
            founder=self.application, category='CAP_TABLE', label='Cap Table',
            file=SimpleUploadedFile('captable.csv', b'a,b,c', content_type='text/csv'),
        )

        self.client.force_login(self.founder_user)
        response = self.client.get(self._profile_url())
        materials = response.context['investor_readiness']['materials']

        self.assertIn('Zelda Intelligence Report', materials)
        self.assertIn('Truth Delta Verification', materials)
        self.assertIn('Cap Table', materials)
        self.assertNotIn('Pitch Deck', materials)
        for _, label in DataRoomDocument.CATEGORY_CHOICES:
            if label not in ('Cap Table',):
                self.assertNotIn(label, materials)


class VerificationHistoryPaywallTests(TestCase):
    """
    Truth Delta's actual scores/trend are Premium — same founder/seller-
    controlled-asset model as the IC Memo: gated on the founder's own
    Premium, not the viewer's, so it's free for any investor/buyer to view
    once the founder unlocks it. verification_reports_count stays visible
    either way (proof reports exist), only the detailed list is gated.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        from zelda_api.vector_models import DocumentSource
        from zelda_api.truth_delta_models import TruthDeltaReport

        self.founder_user = User.objects.create_user('vhp_founder', password='x')
        self.application = Application.objects.create(
            user=self.founder_user, company_name='VHPCo', founder_name='F', email='f@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        doc = DocumentSource.objects.create(
            uploaded_by=self.founder_user, filename='deck.pdf', source_entity='VHPCo', document_type='pitch_deck',
        )
        TruthDeltaReport.objects.create(document=doc, overall_truth_score=90.0, credibility_risk='low', summary='Checks out.')

        self.investor_user = User.objects.create_user('vhp_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='Fund', email='i@t.com',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.staff_user = User.objects.create_user('vhp_staff', password='x', is_staff=True)

    def test_owner_sees_locked_state_when_not_premium(self):
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('accounts:profile', args=[self.founder_user.username]))
        self.assertFalse(response.context['verification_unlocked'])
        self.assertEqual(response.context['verification_history'], [])
        self.assertEqual(response.context['verification_reports_count'], 1)
        self.assertContains(response, 'Unlock Your Verification History')

    def test_investor_sees_locked_state_when_founder_not_premium(self):
        self.client.force_login(self.investor_user)
        response = self.client.get(reverse('accounts:profile', args=[self.founder_user.username]))
        self.assertFalse(response.context['verification_unlocked'])
        self.assertEqual(response.context['verification_history'], [])
        self.assertContains(response, 'Premium Feature')

    def test_owner_sees_full_history_once_premium(self):
        self.application.is_premium = True
        self.application.save(update_fields=['is_premium'])
        self.client.force_login(self.founder_user)
        response = self.client.get(reverse('accounts:profile', args=[self.founder_user.username]))
        self.assertTrue(response.context['verification_unlocked'])
        self.assertEqual(len(response.context['verification_history']), 1)

    def test_investor_sees_full_history_once_founder_premium_without_own_premium(self):
        self.application.is_premium = True
        self.application.save(update_fields=['is_premium'])
        self.client.force_login(self.investor_user)
        response = self.client.get(reverse('accounts:profile', args=[self.founder_user.username]))
        self.assertTrue(response.context['verification_unlocked'])
        self.assertEqual(len(response.context['verification_history']), 1)

    def test_staff_sees_full_history_regardless_of_premium(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('accounts:profile', args=[self.founder_user.username]))
        self.assertTrue(response.context['verification_unlocked'])
        self.assertEqual(len(response.context['verification_history']), 1)


class ZeldaWidgetLockedMemoInfoIconTests(TestCase):
    """
    templates/includes/zelda_ai_assistant_enhanced.html's renderLockedMemoCard()
    (the floating widget's locked-state card for the Memo tab and Intelligence
    brief) got an info icon matching the one on the unlocked report pages
    (memo_detail.html, ic_memo.html, etc). Since that card is injected via
    innerHTML after page load, base.html's one-time DOMContentLoaded popover
    scan can't see it — this checks the initPopovers() helper and its two
    call sites are actually present in the rendered page, not just the
    static markup (a popover attribute alone would silently do nothing).
    The widget is included on every authenticated page via base.html, so
    any page render exercises this.
    """

    def setUp(self):
        self.user = User.objects.create_user('zwi_user', password='x')

    def test_widget_defines_and_wires_up_popover_init_for_locked_memo_card(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('accounts:profile', args=[self.user.username]))
        html = response.content.decode('utf-8')
        self.assertIn('function initPopovers(root)', html)
        self.assertIn('Save hours of manual research', html)
        self.assertIn('initPopovers(memoContentEl)', html)
        self.assertIn('initPopovers(content)', html)
