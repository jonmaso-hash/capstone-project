"""
The Truth Delta score API honors the same hidden-document rule as the page.

truth_delta_ui_view refuses a document staff have hidden (still under review)
to everyone but its owner and staff. TruthDeltaScoreView, the JSON endpoint
behind that page, had no such check, so any signed-in user could read a hidden
document's score, risk and summary by id. Who may view a visible report is
unchanged: any signed-in user, as on the page.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.models import Application
from matchmaking.tests import _mock_embedding_generation

from .truth_delta_models import TruthDeltaReport
from .vector_models import DocumentSource

User = get_user_model()


class TruthDeltaScoreVisibilityTests(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.owner = User.objects.create_user('tdv_owner', password='x')
        Application.objects.create(
            user=self.owner, company_name='TDVCo', founder_name='F', email='f@t.test',
            description='d', sector='SaaS', stage='Seed',
        )
        self.investor = User.objects.create_user('tdv_investor', password='x')
        self.staff = User.objects.create_user('tdv_staff', password='x', is_staff=True)
        self.doc = DocumentSource.objects.create(
            uploaded_by=self.owner, filename='deck.pdf', source_entity='TDVCo', document_type='pitch_deck',
        )
        TruthDeltaReport.objects.create(
            document=self.doc, overall_truth_score=80.0, credibility_risk='low',
            summary='Under-review summary.', details={},
        )
        self.api_url = reverse('zelda_api:truth_delta_score', args=[self.doc.id])

    def _hide(self):
        DocumentSource.objects.filter(id=self.doc.id).update(is_hidden_by_staff=True)

    def _get_api(self, user):
        self.client.force_login(user)
        return self.client.get(self.api_url)

    def test_a_visible_report_stays_readable_by_another_signed_in_user(self):
        response = self._get_api(self.investor)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['summary'], 'Under-review summary.')

    def test_a_hidden_document_report_is_refused_to_other_users(self):
        self._hide()
        response = self._get_api(self.investor)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('Under-review summary.', response.content.decode())
        self.assertNotIn('overall_truth_score', response.content.decode())

    def test_the_owner_still_reads_a_hidden_document_report(self):
        self._hide()
        self.assertEqual(self._get_api(self.owner).status_code, 200)

    def test_staff_still_read_a_hidden_document_report(self):
        self._hide()
        self.assertEqual(self._get_api(self.staff).status_code, 200)

    def test_the_page_and_the_api_refuse_the_same_viewer(self):
        self._hide()
        self.client.force_login(self.investor)
        page = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.doc.id]))
        api = self.client.get(self.api_url)
        self.assertEqual((page.status_code, api.status_code), (403, 403))
