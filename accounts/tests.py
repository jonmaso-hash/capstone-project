"""
Coverage for the social-login integration point: post_login_router (the
LOGIN_REDIRECT_URL target allauth's social-login flow consults) and
choose_role (the role-picker a first-time social-login user with no
Founder/Investor/Seller/Buyer profile lands on).
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
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
        self.assertContains(response, 'Profile Analysis')

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
