"""
"Claims Analyzed" on the Truth Delta page is Verified + Unverified.

The stat card showed the number of extracted ClaimedDatapoint rows, while
Verified and Unverified beside it count the report's claim categories
(TruthDeltaReport.category_states). The two numbers come from different
sources, so a deck could show "6 analyzed, 3 verified, 1 unverified" with the
other two unaccounted for. The page script's claims_analyzed -- the total the
Lite "showing N of M" note compares against -- had the same mismatch.

Now all three cards and the script total come from category_states, and the
unused script fields claims_verified and flag_breakdown.verified (which
repeated the row count as a "verified" figure) are gone.
"""
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.models import Application
from matchmaking.tests import _mock_embedding_generation

from .truth_delta_models import ClaimedDatapoint, TruthDeltaReport
from .vector_models import DocumentSource

User = get_user_model()

PER_CLAIM = [
    {'category': 'revenue', 'claimed': '$1M ARR', 'observed': 'SEC Form D: $900K sold', 'assessment': 'close'},
    {'category': 'customers', 'claimed': '500', 'observed': 'No external data found', 'assessment': 'n/a'},
    {'category': 'team_size', 'claimed': '12', 'observed': 'LinkedIn: 11 employees', 'assessment': 'close'},
    {'category': 'funding_raised', 'claimed': '$2M', 'observed': 'Form D: $2M', 'assessment': 'match'},
]


def _stat(html, label):
    match = re.search(
        r'<div class="stat-value"[^>]*>\s*(\d+)\s*</div>\s*<div class="stat-label">' + re.escape(label) + '</div>',
        html,
    )
    return int(match.group(1)) if match else None


class ClaimsAnalyzedCountTests(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.owner = User.objects.create_user('cac_owner', password='x')
        Application.objects.create(
            user=self.owner, company_name='CACo', founder_name='F', email='cac@t.test',
            description='d', sector='SaaS', stage='Seed',
        )
        self.viewer = User.objects.create_user('cac_viewer', password='x')
        self.doc = DocumentSource.objects.create(
            uploaded_by=self.owner, filename='deck.pdf', source_entity='CACo', document_type='pitch_deck',
        )
        self.report = TruthDeltaReport.objects.create(
            document=self.doc, overall_truth_score=70.0, credibility_risk='low', summary='Summary.',
            details={'claims': [{'category': row['category']} for row in PER_CLAIM], 'per_claim': PER_CLAIM},
        )
        # Six extracted rows (two revenue figures, an "other") against four categories.
        for category, value in [
            ('revenue', '$1M'), ('revenue', '$80K MRR'), ('customers', '500'),
            ('team_size', '12'), ('funding_raised', '$2M'), ('other', 'NPS 70'),
        ]:
            ClaimedDatapoint.objects.create(document=self.doc, category=category, claimed_value=value)
        self.url = reverse('zelda_api:truth_delta_ui', args=[self.doc.id])

    def _page(self, user):
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        return response

    def test_claims_analyzed_is_verified_plus_unverified(self):
        for user in (self.owner, self.viewer):
            with self.subTest(user=user.username):
                html = self._page(user).content.decode()
                verified, unverified = _stat(html, 'Verified'), _stat(html, 'Unverified')
                self.assertEqual((verified, unverified), (3, 1))
                self.assertEqual(_stat(html, 'Claims Analyzed'), verified + unverified)

    def test_the_count_matches_the_reports_categories_not_the_extracted_rows(self):
        response = self._page(self.owner)
        self.assertEqual(response.context['claims_analyzed'], 4)
        self.assertEqual(ClaimedDatapoint.objects.filter(document=self.doc).count(), 6)

    def test_the_page_script_uses_the_same_total(self):
        html = self._page(self.viewer).content.decode()
        self.assertRegex(html, r'claims_analyzed:\s*4,')

    def test_the_unused_script_fields_are_gone(self):
        html = self._page(self.owner).content.decode()
        self.assertIn('const SERVER_TRUTH_DATA', html)
        self.assertNotIn('claims_verified', html)
        self.assertNotRegex(html, r'flag_breakdown:\s*\{\s*verified')

    def test_a_report_without_claims_shows_no_stat_cards(self):
        self.report.details = {}
        self.report.save(update_fields=['details'])
        html = self._page(self.owner).content.decode()
        self.assertIsNone(_stat(html, 'Claims Analyzed'))
        self.assertRegex(html, r'claims_analyzed:\s*0,')
