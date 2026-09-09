"""
Deep-link continuity across the authentication seam.

`@login_required` sits on 103 views in this project and Django generates
`?next=<path>` for every one of them. Until PR #27 all of those destinations
were discarded at the auth boundary, so a logged-out visitor following any deep
link -- an Explore card, a shared profile, a notification -- landed on their own
profile instead of the thing they clicked.

`accounts/tests.py` already covered `post_login_router` thoroughly: four tests
asserting it routes founders, investors, bare users and anonymous users
correctly. Every one of them calls `force_login` and then requests the router's
URL **directly**. So the router was proven to work when reached, and nothing
proved that logging in ever reached it -- which it did not. That is the same
"both ends pass, the seam is untested" shape that removed the
Next-best-improvement card in PR #23.

These tests therefore exercise whole journeys, never a single function: real
GETs and POSTs through signup, role onboarding and login, asserting where the
visitor actually ends up.
"""
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from matchmaking.models import Application
from matchmaking.tests import _mock_embedding_generation

from .redirects import PENDING_NEXT_SESSION_KEY

User = get_user_model()

PASSWORD = 'Str0ng-Passw0rd-9x'

# Minimum valid role-form payloads. Field lists come from introspecting
# InvestorForm/BuyerForm required fields, not from guesswork -- an incomplete
# payload re-renders the form with a 200 and would silently look like "the
# redirect broke" rather than "the fixture is short a field".
INVESTOR_FORM = {
    'full_name': 'New Comer', 'company_name': 'Newcomer Capital',
    'email': 'newcomer@t.com', 'investment_focus': 'Climate Tech',
    'investment_stage': 'Seed', 'investment_amount': '250000',
    'weight_problem_solution': '0.4', 'weight_capital_plan': '0.3',
    'weight_market_context': '0.3',
}
BUYER_FORM = {
    'full_name': 'Buy Er', 'company_name': 'BuyerCo', 'email': 'buyer@t.com',
    'acquisition_thesis': 'Buy things.', 'budget_min': '100000',
    'budget_max': '500000', 'preferred_deal_structure': 'OPEN',
}

# Destinations that must never be honoured: scheme-relative, absolute to
# another host, and a backslash trick some browsers normalise into an authority.
HOSTILE_DESTINATIONS = [
    '//evil.com',
    'https://evil.com/steal',
    'http://evil.com',
    'https://evil.com\\@localhost',
]


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DeepLinkSurvivesSignupTests(TestCase):
    """The full journey: protected page -> signup -> onboarding -> thank you -> destination."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('dl_founder', password=PASSWORD)
        Application.objects.create(
            user=self.founder_user, company_name='Northwind', founder_name='F',
            email='f@t.com', description='A company.', sector='Climate Tech', stage='Seed')
        self.destination = '/accounts/profile/%s/' % self.founder_user.username

    def test_anonymous_deep_link_bounces_with_its_destination_attached(self):
        # The bounce Django itself generates for any of the 103 protected views.
        bounce = self.client.get(self.destination)
        self.assertEqual(bounce.status_code, 302)
        self.assertEqual(bounce.url, '/accounts/login/?next=%s' % self.destination)

    def test_destination_survives_signup_and_role_onboarding(self):
        signup_url = '%s?next=%s' % (reverse('accounts:signup'), self.destination)

        page = self.client.get(signup_url)
        self.assertContains(page, 'name="next" value="%s"' % self.destination)

        created = self.client.post(signup_url, {
            'role': 'investor',
            'username': 'dl_newcomer',
            'password1': PASSWORD,
            'password2': PASSWORD,
            'next': self.destination,
        })
        # Signup still hands off to the role form -- the destination is not
        # lost, it is waiting in the session.
        self.assertRedirects(created, '/settings/profile/investor/',
                             fetch_redirect_response=False)

        onboarded = self.client.post('/settings/profile/investor/', INVESTOR_FORM)
        thank_you = '%s?next=%s' % (reverse('pages:thank_you'), self.destination)
        self.assertRedirects(onboarded, thank_you, fetch_redirect_response=False)

        # The milestone page still happens, and the original intent is the CTA.
        page = self.client.get(thank_you)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.context['pending_destination'], self.destination)
        self.assertContains(page, 'href="%s"' % self.destination)

        # And it actually resolves for the now-authenticated visitor.
        arrived = self.client.get(self.destination)
        self.assertEqual(arrived.status_code, 200)
        self.assertContains(arrived, 'Northwind')

    def test_destination_is_consumed_exactly_once(self):
        """An abandoned signup must not leak its destination into a later onboarding."""
        self.client.get('%s?next=%s' % (reverse('accounts:signup'), self.destination))
        self.client.post(reverse('accounts:signup'), {
            'role': 'buyer', 'username': 'dl_once', 'password1': PASSWORD,
            'password2': PASSWORD,
        })

        first = self.client.post('/settings/profile/buyer/', BUYER_FORM)
        self.assertIn('next=', first.url)

        # Popped, not merely unused: the key itself is gone from the session.
        self.assertNotIn(PENDING_NEXT_SESSION_KEY, self.client.session)

    def test_signup_without_a_destination_still_reaches_thank_you(self):
        """The ordinary signup is untouched by any of this."""
        self.client.post(reverse('accounts:signup'), {
            'role': 'buyer', 'username': 'dl_plain', 'password1': PASSWORD,
            'password2': PASSWORD,
        })
        onboarded = self.client.post('/settings/profile/buyer/', BUYER_FORM)
        self.assertRedirects(onboarded, reverse('pages:thank_you'),
                             fetch_redirect_response=False)

        page = self.client.get(reverse('pages:thank_you'))
        self.assertIsNone(page.context['pending_destination'])


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DeepLinkSurvivesLoginTests(TestCase):
    """The shorter journey: protected page -> login -> destination."""

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('dl_founder2', password=PASSWORD)
        Application.objects.create(
            user=self.founder_user, company_name='Northwind', founder_name='F',
            email='f2@t.com', description='A company.', sector='Climate Tech', stage='Seed')
        self.destination = '/accounts/profile/%s/' % self.founder_user.username

        self.visitor = User.objects.create_user('dl_visitor', password=PASSWORD)
        Application.objects.create(
            user=self.visitor, company_name='VisitorCo', founder_name='V',
            email='v@t.com', description='Another company.', sector='SaaS', stage='Seed')

    def test_login_returns_the_visitor_to_where_they_were_going(self):
        login_url = '%s?next=%s' % (reverse('accounts:login'), self.destination)

        page = self.client.get(login_url)
        self.assertContains(page, 'name="next" value="%s"' % self.destination)

        landed = self.client.post(login_url, {
            'username': 'dl_visitor', 'password': PASSWORD, 'next': self.destination,
        })
        self.assertRedirects(landed, self.destination, fetch_redirect_response=False)

    def test_login_without_a_destination_uses_the_shared_router(self):
        """
        The case the existing post_login_router tests cannot reach: they call
        the router directly, so they never proved that a login arrives there.
        Before PR #27 this landed on the user's own profile and the router
        never ran at all for password auth.
        """
        landed = self.client.post(reverse('accounts:login'), {
            'username': 'dl_visitor', 'password': PASSWORD,
        })
        self.assertRedirects(landed, reverse('accounts:post_login_router'),
                             fetch_redirect_response=False)

        routed = self.client.get(reverse('accounts:post_login_router'))
        self.assertRedirects(routed, reverse('matchmaking:founder_dashboard'),
                             fetch_redirect_response=False)

    def test_an_already_signed_in_visitor_is_sent_to_the_destination(self):
        """
        A signup or login link followed in a second tab, or after signing in
        elsewhere. The guard used to bounce them to their own profile, losing
        the link they actually clicked.
        """
        self.client.force_login(self.visitor)

        landed = self.client.get('%s?next=%s' % (reverse('accounts:login'), self.destination))
        self.assertRedirects(landed, self.destination, fetch_redirect_response=False)

        landed = self.client.get('%s?next=%s' % (reverse('accounts:signup'), self.destination))
        self.assertRedirects(landed, self.destination, fetch_redirect_response=False)

    def test_an_already_signed_in_visitor_with_no_destination_is_unchanged(self):
        self.client.force_login(self.visitor)
        landed = self.client.get(reverse('accounts:login'))
        self.assertRedirects(landed, '/accounts/profile/dl_visitor/',
                             fetch_redirect_response=False)

    def test_social_login_links_carry_the_destination(self):
        page = self.client.get('%s?next=%s' % (reverse('accounts:login'), self.destination))
        # allauth percent-encodes it into the provider URL.
        encoded = quote(self.destination, safe='')
        self.assertContains(page, '/accounts/google/login/?next=%s' % encoded)
        self.assertContains(page, '/accounts/linkedin_oauth2/login/?next=%s' % encoded)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class HostileDestinationTests(TestCase):
    """
    An attacker-supplied destination is discarded at the door, and the visitor
    still gets a working product -- never an error, never the tampered target.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('hostile_visitor', password=PASSWORD)
        Application.objects.create(
            user=self.user, company_name='HCo', founder_name='H', email='h@t.com',
            description='A company.', sector='SaaS', stage='Seed')

    def test_login_discards_external_destinations(self):
        for hostile in HOSTILE_DESTINATIONS:
            with self.subTest(destination=hostile):
                client = self.client_class()
                landed = client.post(reverse('accounts:login'), {
                    'username': 'hostile_visitor', 'password': PASSWORD, 'next': hostile,
                })
                self.assertRedirects(landed, reverse('accounts:post_login_router'),
                                     fetch_redirect_response=False)

    def test_signup_never_stashes_an_external_destination(self):
        for hostile in HOSTILE_DESTINATIONS:
            with self.subTest(destination=hostile):
                client = self.client_class()
                client.get('%s?next=%s' % (reverse('accounts:signup'), hostile))
                self.assertNotIn(PENDING_NEXT_SESSION_KEY, client.session)

    def test_thank_you_ignores_an_external_destination_in_its_url(self):
        self.client.force_login(self.user)
        for hostile in HOSTILE_DESTINATIONS:
            with self.subTest(destination=hostile):
                page = self.client.get('%s?next=%s' % (reverse('pages:thank_you'), hostile))
                self.assertEqual(page.status_code, 200)
                self.assertIsNone(page.context['pending_destination'])
