"""
Privacy and Terms must exist, be readable without an account, and be linked.

The footer linked both to `href="#"` and neither page existed. For a platform
that takes payments and holds private company financials, a visitor has to be
able to read these *before* they sign up or pay -- which means the pages must
work while logged out, and the links that point at them must be real.
"""
from django.test import TestCase
from django.urls import reverse


class LegalPagesAreReachableTests(TestCase):
    """
    Anonymous access is the whole point; these must not be login-gated.

    TestCase rather than SimpleTestCase because base.html queries the
    database to build the nav, so even a static page needs DB access.
    """

    def test_privacy_is_readable_without_an_account(self):
        response = self.client.get(reverse('pages:privacy'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Privacy Policy')

    def test_terms_is_readable_without_an_account(self):
        response = self.client.get(reverse('pages:terms'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Terms of Service')

    def test_both_pages_say_when_they_were_last_updated(self):
        for name in ('pages:privacy', 'pages:terms'):
            with self.subTest(page=name):
                self.assertContains(self.client.get(reverse(name)), 'Last updated')


class LegalPagesAreLinkedTests(TestCase):
    """
    A page nobody can reach is the same as no page. These assert the footer
    links resolve, on a signed-out page a visitor actually sees.
    """

    def test_footer_links_to_both_pages_when_signed_out(self):
        response = self.client.get(reverse('accounts:signup'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="%s"' % reverse('pages:privacy'))
        self.assertContains(response, 'href="%s"' % reverse('pages:terms'))

    def test_footer_no_longer_points_privacy_or_terms_at_a_dead_anchor(self):
        html = self.client.get(reverse('accounts:signup')).content.decode()
        for label in ('Privacy', 'Terms'):
            with self.subTest(link=label):
                self.assertNotIn(
                    '<a href="#" class="text-decoration-none text-muted mx-2">%s</a>' % label,
                    html,
                    '%s is linked to a dead anchor again' % label)


class PrivacyDescribesWhatTheCodeActuallyDoesTests(TestCase):
    """
    Two things the policy never mentioned, both of which a founder uploading a
    cap table will ask about: that staff can view the site as them, and what
    happens to a document once an analysis is requested.

    Written from the implementation, so each assertion here is a claim the code
    has to keep being true:

    - read-only impersonation, permanent audit log, never counted as the user's
      own activity (ops/impersonation.py, ops.models.ImpersonationLog)
    - profile embeddings are generated on our own servers
      (matchmaking/services/ai_utils.py loads sentence-transformers locally), so
      profile text is not sent to an AI provider for matching
    """

    def setUp(self):
        self.html = self.client.get(reverse('pages:privacy')).content.decode()

    def test_staff_access_is_disclosed_as_read_only_and_logged(self):
        self.assertIn('Staff access to your account', self.html)
        self.assertIn('read-only', self.html)
        self.assertRegex(self.html, r'recorded|record')

    def test_it_says_what_happens_to_an_uploaded_document(self):
        self.assertIn('Anthropic', self.html)
        self.assertIn('not used to train', self.html)

    def test_it_says_matching_does_not_send_profiles_to_a_provider(self):
        self.assertRegex(self.html, r'not sent to an AI provider')

    def test_the_providers_are_named(self):
        for provider in ('Stripe', 'Anthropic', 'Stream', 'Postmark', 'Sentry'):
            with self.subTest(provider=provider):
                self.assertIn(provider, self.html)

    def test_the_advice_disclaimer_is_still_there(self):
        # Pre-existing and load-bearing: automated output is informational and
        # must not be the sole basis for a decision.
        self.assertIn('sole basis', self.html)
        self.assertIn('not investment, financial, legal, tax or accounting', self.html)
