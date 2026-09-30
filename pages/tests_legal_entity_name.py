"""
The legal entity is named where it protects, and only there.

Interlink Foundry LLC is a California limited liability company (articles of
organization filed 2026-09-30). Two different jobs are being done with the
name, and conflating them costs something either way:

    LEGAL SURFACES name the entity. The footer copyright, the Terms and the
    Privacy Policy identify who the user is actually contracting with. A
    contract that does not name the contracting party, and a copyright notice
    claiming rights for a trade name rather than the entity that holds them,
    are both weaker than they look. This is the half that preserves limited
    liability -- it signals that the counterparty is a registered company, not
    an individual trading under a name.

    BRANDING DOES NOT. The navbar, the logo and headline copy stay "Interlink
    Foundry". Putting "LLC" in the header is visual noise that buys no
    protection, because the footer and the legal pages already establish it.

Both directions are asserted. Only checking that "LLC" appears would be
satisfied by pasting it everywhere, which is the mistake this file exists to
prevent as much as the omission is.
"""
from django.test import TestCase
from django.urls import reverse

LEGAL_NAME = 'Interlink Foundry LLC'
JURISDICTION = 'California limited liability company'


class TheFooterIdentifiesTheEntityTests(TestCase):
    """
    The footer is on every page, so it is the one surface that always carries
    the entity regardless of where a visitor lands.
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        self.html = self.client.get(reverse('pages:home')).content.decode()

    def test_the_page_rendered_at_all(self):
        """Positive control: every assertion below reads this one response."""
        self.assertIn('<footer', self.html)

    def test_the_copyright_names_the_entity(self):
        self.assertIn(f'&copy; 2026 {LEGAL_NAME}', self.html)

    def test_the_footer_states_the_jurisdiction(self):
        self.assertIn(JURISDICTION, self.html)


class TheLegalPagesNameTheContractingPartyTests(TestCase):

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)

    def page(self, name):
        response = self.client.get(reverse(f'pages:{name}'))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_the_terms_name_the_entity(self):
        """
        Terms that never name the contracting party are harder to enforce:
        the user has agreed with a trade name rather than a company.
        """
        self.assertIn(LEGAL_NAME, self.page('terms'))

    def test_the_privacy_policy_names_the_entity(self):
        """
        The privacy policy states who the data controller is. A trade name is
        not a legal person and cannot hold that role.
        """
        self.assertIn(LEGAL_NAME, self.page('privacy'))


class BrandingStaysCleanTests(TestCase):
    """
    The paired negative. Without it, "name the entity" is satisfied by putting
    LLC in the navbar, the hero and the page title -- which protects nothing
    further and reads as clutter.
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        self.html = self.client.get(reverse('pages:home')).content.decode()

    def test_the_navbar_brand_does_not_carry_the_suffix(self):
        brand = self.html.split('navbar-brand', 1)[1].split('</a>', 1)[0]
        self.assertIn('Interlink Foundry', brand, 'the brand link lost its name')
        self.assertNotIn('LLC', brand, 'the entity suffix belongs in the footer, not the header')

    def test_the_page_title_does_not_carry_the_suffix(self):
        title = self.html.split('<title>', 1)[1].split('</title>', 1)[0]
        self.assertIn('Interlink Foundry', title)
        self.assertNotIn('LLC', title)
