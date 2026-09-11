"""
The pipeline dashboard is an internal monitor, not a product page.

It was reachable by any authenticated user -- a bare @login_required -- and
passed `DocumentSource.objects.all()[:10]` into its template: every user's
documents, unscoped, on a platform whose premise is private company
information. Nothing leaked, because the template never rendered that context;
it loads client-side and its only fetches take a document id typed by hand. But
it sat one `{% for %}` away from showing filenames and source entities across
tenants.

These tests pin both halves of the fix: who may reach the page, and that no
other user's document metadata can surface on it.

NOTE: zelda_api is excluded from the blocking CI job. Run this module
explicitly when touching the dashboard or its authorization.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from zelda_api.vector_models import DocumentSource

User = get_user_model()

PASSWORD = 'Str0ng-Passw0rd-9x'


class PipelineDashboardAccessTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.url = reverse('zelda_api:intelligence_dashboard')

        cls.staff = User.objects.create_user('zd_staff', password=PASSWORD, is_staff=True)
        cls.member = User.objects.create_user('zd_member', password=PASSWORD)
        cls.other = User.objects.create_user('zd_other', password=PASSWORD)

        # A document belonging to someone who is not the viewer.
        cls.foreign_document = DocumentSource.objects.create(
            filename='Confidential_CapTable_2026.pdf',
            document_type='financial_model',
            source_entity='Harbour Facilities Holdings',
            uploaded_by=cls.other,
            status='analyzed',
        )

    def test_anonymous_is_sent_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_authenticated_non_staff_cannot_reach_it(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)

        self.assertNotEqual(
            response.status_code, 200,
            'a non-staff user reached an internal pipeline monitor')
        # user_passes_test redirects to the login url rather than 403ing.
        self.assertEqual(response.status_code, 302)

    def test_staff_can_reach_it(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Zelda Intelligence Pipeline')

    def test_no_document_metadata_is_rendered_even_for_staff(self):
        """
        The page loads documents client-side through endpoints that check
        ownership. Nothing should arrive pre-rendered in the HTML, so a future
        template change cannot quietly start leaking the old unscoped context.
        """
        self.client.force_login(self.staff)
        html = self.client.get(self.url).content.decode(errors='ignore')

        self.assertIn('Zelda Intelligence Pipeline', html, 'positive control')
        self.assertNotIn(self.foreign_document.filename, html)
        self.assertNotIn(self.foreign_document.source_entity, html)

    def test_the_view_passes_no_documents_context(self):
        """The unscoped queryset is gone, not merely unused by the template."""
        self.client.force_login(self.staff)
        response = self.client.get(self.url)

        self.assertNotIn(
            'documents', response.context,
            'the dashboard is passing a documents queryset again; if a template '
            'ever iterates it, every user sees every user\'s document metadata')


class DocumentStatusOwnershipTests(TestCase):
    """
    The endpoint the dashboard actually reads from. Its ownership check is what
    makes the client-side loading safe, so it is pinned here alongside.
    """

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('zd_owner', password=PASSWORD)
        cls.stranger = User.objects.create_user('zd_stranger', password=PASSWORD)
        cls.staff = User.objects.create_user('zd_staff2', password=PASSWORD, is_staff=True)
        cls.document = DocumentSource.objects.create(
            filename='deck.pdf', document_type='pitch_deck',
            source_entity='Northwind Grid', uploaded_by=cls.owner, status='analyzed',
        )
        cls.url = reverse('zelda_api:document_status', args=[cls.document.id])

    def test_owner_may_read_status(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_staff_may_read_status(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_a_stranger_may_not(self):
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_anonymous_may_not(self):
        self.assertIn(self.client.get(self.url).status_code, (401, 403, 302))
