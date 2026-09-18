"""
"Run Verification" is offered only to whoever can actually run it, and a
refusal says why.

The button rendered for every viewer of a Truth Delta page, but
TruthDeltaVerifyView accepts only the document's uploader or staff, so an
investor who clicked it got a 403. The page turned every failure into the
same alert, "Failed to start verification" -- including the 402 an owner
gets when their credits run out, whose body carries the upgrade message.

Now the button renders for the owner and staff only, and the page shows the
message the endpoint actually returned.
"""
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.models import Application
from matchmaking.tests import _mock_embedding_generation

from .truth_delta_models import TruthDeltaReport
from .vector_models import DocumentSource

User = get_user_model()

BUTTON = 'onclick="runTruthDeltaVerification()"'


class VerifyButtonVisibilityTests(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.owner = User.objects.create_user('vb_owner', password='x')
        Application.objects.create(
            user=self.owner, company_name='VBCo', founder_name='F', email='vb@t.test',
            description='d', sector='SaaS', stage='Seed',
        )
        self.viewer = User.objects.create_user('vb_viewer', password='x')
        self.staff = User.objects.create_user('vb_staff', password='x', is_staff=True)
        self.doc = DocumentSource.objects.create(
            uploaded_by=self.owner, filename='deck.pdf', source_entity='VBCo', document_type='pitch_deck',
        )
        TruthDeltaReport.objects.create(
            document=self.doc, overall_truth_score=70.0, credibility_risk='low',
            summary='Summary.', details={},
        )
        self.url = reverse('zelda_api:truth_delta_ui', args=[self.doc.id])

    def _page(self, user):
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_the_owner_is_offered_the_button(self):
        self.assertIn(BUTTON, self._page(self.owner))

    def test_staff_are_offered_the_button(self):
        self.assertIn(BUTTON, self._page(self.staff))

    def test_another_viewer_is_not_offered_the_button(self):
        html = self._page(self.viewer)
        # Positive control: this is the report page, with the summary on it.
        self.assertIn('Summary.', html)
        self.assertNotIn(BUTTON, html)

    def test_the_endpoint_still_refuses_another_viewer(self):
        self.client.force_login(self.viewer)
        response = self.client.post(
            reverse('zelda_api:truth_delta_verify', args=[self.doc.id])
        )
        self.assertEqual(response.status_code, 403)

    def test_a_refusal_shows_the_reason_the_endpoint_gave(self):
        # The 402 an owner gets when credits run out carries the upgrade
        # message in `error`; the page must show it rather than a generic
        # "Failed to start verification" for every failure alike.
        html = self._page(self.owner)
        script = html[html.index('async function runTruthDeltaVerification'):]
        script = script[:script.index('function pollTruthDeltaStatus')]
        self.assertRegex(script, r'\.error\b')
        self.assertNotRegex(script, r"alert\('Failed to start verification'\)")
