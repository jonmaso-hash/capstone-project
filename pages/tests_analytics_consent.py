"""
Google Analytics loads after consent, or not at all.

The tag is rendered server-side, gated on a stored choice, so "GA is off until
you agree" is a fact about the HTML rather than a promise about JavaScript. A
consent library that loads gtag and then asks it not to track is a different,
weaker thing: the request has already been made.

Boundaries this pins:

- nothing when GA_MEASUREMENT_ID is unset, so a fresh checkout and CI are silent
- nothing before a choice is made, and nothing after a decline
- nothing in DEBUG, so local development never writes into the property
- nothing on signed-in pages -- GA is for the public acquisition surface, and
  the database is the source of truth for what members do
- one exception, deliberate: a completed signup fires its conversion event on
  the next page even though the visitor is now authenticated, otherwise the
  funnel ends one step before the thing worth measuring
"""
from django.test import TestCase, override_settings
from django.urls import reverse

from django.contrib.auth import get_user_model

User = get_user_model()

MEASUREMENT_ID = 'G-TESTID0000'
GA_SRC = 'googletagmanager.com/gtag/js'
CONSENT_COOKIE = 'analytics_consent'


@override_settings(GA_MEASUREMENT_ID=MEASUREMENT_ID, DEBUG=False)
class TheTagWaitsForConsentTests(TestCase):

    def _home(self):
        return self.client.get(reverse('pages:home')).content.decode()

    def test_nothing_loads_before_a_choice_is_made(self):
        html = self._home()
        self.assertNotIn(GA_SRC, html)
        self.assertNotIn(MEASUREMENT_ID, html)

    def test_the_banner_asks(self):
        self.assertIn('analytics', self._home().lower())
        self.assertContains(self.client.get(reverse('pages:home')), 'Accept analytics')

    def test_accepting_loads_it(self):
        self.client.cookies[CONSENT_COOKIE] = 'granted'
        html = self._home()
        self.assertIn(GA_SRC, html)
        self.assertIn(MEASUREMENT_ID, html)

    def test_declining_keeps_it_off_and_stops_asking(self):
        self.client.cookies[CONSENT_COOKIE] = 'denied'
        html = self._home()
        self.assertNotIn(GA_SRC, html)
        self.assertNotIn('Accept analytics', html)


@override_settings(GA_MEASUREMENT_ID='', DEBUG=False)
class WithoutAMeasurementIdNothingHappensTests(TestCase):

    def test_no_tag_and_no_banner_even_with_consent(self):
        self.client.cookies[CONSENT_COOKIE] = 'granted'
        html = self.client.get(reverse('pages:home')).content.decode()
        self.assertNotIn(GA_SRC, html)
        self.assertNotIn('Accept analytics', html)


@override_settings(GA_MEASUREMENT_ID=MEASUREMENT_ID, DEBUG=True)
class DevelopmentNeverWritesToThePropertyTests(TestCase):

    def test_debug_suppresses_the_tag(self):
        self.client.cookies[CONSENT_COOKIE] = 'granted'
        self.assertNotIn(GA_SRC, self.client.get(reverse('pages:home')).content.decode())


@override_settings(GA_MEASUREMENT_ID=MEASUREMENT_ID, DEBUG=False)
class ChoosingAndChangingYourMindTests(TestCase):

    def test_accepting_persists_across_requests(self):
        self.client.post(reverse('pages:analytics_consent'), {'choice': 'accept'})
        self.assertEqual(self.client.cookies[CONSENT_COOKIE].value, 'granted')
        self.assertIn(GA_SRC, self.client.get(reverse('pages:home')).content.decode())

    def test_withdrawing_stops_it_loading_again(self):
        self.client.post(reverse('pages:analytics_consent'), {'choice': 'accept'})
        self.client.post(reverse('pages:analytics_consent'), {'choice': 'decline'})
        self.assertEqual(self.client.cookies[CONSENT_COOKIE].value, 'denied')
        self.assertNotIn(GA_SRC, self.client.get(reverse('pages:home')).content.decode())

    def test_it_returns_you_where_you_were_without_trusting_the_url(self):
        response = self.client.post(
            reverse('pages:analytics_consent'), {'choice': 'accept', 'next': '//evil.example.com/'})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('evil.example.com', response.url)

    def test_the_privacy_page_offers_a_way_to_change_it(self):
        html = self.client.get(reverse('pages:privacy')).content.decode()
        self.assertIn('Google Analytics', html)
        self.assertRegex(html, r'withdraw|change your choice|turn (it|analytics) off')


@override_settings(GA_MEASUREMENT_ID=MEASUREMENT_ID, DEBUG=False)
class SignedInPagesAreNotTrackedTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('ga_member', password='Analytics!2026xyz')
        self.client.cookies[CONSENT_COOKIE] = 'granted'

    def test_a_members_dashboard_carries_no_tag(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse('billing:billing_page')).content.decode()
        self.assertNotIn(GA_SRC, html)

    def test_the_public_pages_still_carry_it_for_signed_out_visitors(self):
        self.assertIn(GA_SRC, self.client.get(reverse('pages:home')).content.decode())


@override_settings(GA_MEASUREMENT_ID=MEASUREMENT_ID, DEBUG=False)
class TheFunnelEventsTests(TestCase):
    """
    The events GA4 Enhanced Measurement cannot infer: discovery views and the
    steps into the funnel. Outbound clicks, scrolls, downloads and video are
    left to Enhanced Measurement rather than duplicated here.
    """

    def setUp(self):
        self.client.cookies[CONSENT_COOKIE] = 'granted'

    def test_the_explore_feed_carries_the_tag_and_announces_itself(self):
        # Explore has its own <body> and does not extend base.html, so this is
        # the test that catches the public discovery feed going untracked.
        html = self.client.get(reverse('explore')).content.decode()
        self.assertIn(GA_SRC, html)
        self.assertIn('data-ga-page="explore_view"', html)

    def test_the_signup_page_announces_the_funnel_step(self):
        html = self.client.get(reverse('accounts:signup')).content.decode()
        self.assertIn('data-ga-page="signup_started"', html)

    def test_a_completed_signup_reports_its_conversion_on_the_next_page(self):
        self.client.post(reverse('accounts:signup'), {
            'username': 'ga_convert', 'email': 'ga.convert@example.com',
            'password1': 'Analytics!2026xyz', 'password2': 'Analytics!2026xyz',
            'role': 'founder',
        })
        # The signup response is a redirect, so the event rides to the next page
        # — and it is reported even though the visitor is now signed in.
        html = self.client.get(reverse('pages:home')).content.decode()
        self.assertIn("gtag('event', 'signup_completed')", html)

    def test_the_conversion_fires_once_and_is_not_repeated(self):
        self.client.post(reverse('accounts:signup'), {
            'username': 'ga_once', 'email': 'ga.once@example.com',
            'password1': 'Analytics!2026xyz', 'password2': 'Analytics!2026xyz',
            'role': 'founder',
        })
        self.client.get(reverse('pages:home'))
        again = self.client.get(reverse('pages:home')).content.decode()
        self.assertNotIn("gtag('event', 'signup_completed')", again)
        # And with the conversion spent, signed-in pages are untracked again.
        self.assertNotIn(GA_SRC, again)
