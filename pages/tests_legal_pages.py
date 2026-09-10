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
