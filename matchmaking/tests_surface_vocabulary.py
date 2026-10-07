"""
Standing contract for Interlink's user-facing relationship vocabulary.

Internal database states such as ACCEPTED, FUNDED and CLOSED deliberately remain
unchanged.  This test protects the presentation layer: users see neutral
relationship and counterparty-confirmation language rather than transaction or
independent-verification claims.
"""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class MarketplaceSurfaceVocabularyTests(SimpleTestCase):
    def _text(self, relative_path):
        return (Path(settings.BASE_DIR) / relative_path).read_text(encoding='utf-8', errors='ignore')

    def test_four_dashboards_render_accepted_relationships_as_connected(self):
        for path in (
            'templates/matchmaking/founder_dashboard.html',
            'templates/matchmaking/investor_dashboard.html',
            'templates/matchmaking/seller_dashboard.html',
            'templates/matchmaking/buyer_dashboard.html',
        ):
            with self.subTest(path=path):
                text = self._text(path)
                self.assertIn('Connected', text)
                self.assertNotIn('>Accepted</span>', text)
                self.assertNotIn('> Accepted', text)

    def test_dashboard_discovery_copy_does_not_call_recommendations_deals(self):
        for path in (
            'templates/matchmaking/founder_dashboard.html',
            'templates/matchmaking/investor_dashboard.html',
            'templates/matchmaking/seller_dashboard.html',
            'templates/matchmaking/buyer_dashboard.html',
        ):
            with self.subTest(path=path):
                text = self._text(path)
                self.assertNotIn('Accepted Deals', text)
                self.assertNotIn('No matches yet.', text)

    def test_profile_uses_factual_confirmed_outcome_labels(self):
        text = self._text('templates/accounts/profile.html')
        for expected in (
            'Funding Outcome Confirmed',
            'Sale Outcome Confirmed',
            'Confirmed Outcomes',
        ):
            self.assertIn(expected, text)
        for retired in ('Verified Funded', 'Verified Sold', 'Verified Track Record'):
            self.assertNotIn(retired, text)

    def test_bulletins_keep_paid_visibility_separate_from_alignment_and_outcomes(self):
        founder = self._text('templates/matchmaking/bulletin_board.html')
        seller = self._text('templates/matchmaking/acquisition_bulletin_board.html')

        self.assertIn('Funding Outcome Confirmed', founder)
        self.assertIn('Alignment</span>', founder)
        self.assertNotIn('Verified Funded', founder)

        self.assertIn('Sale Outcome Confirmed', seller)
        self.assertNotIn('Verified Sold', seller)

    def test_deal_timeline_names_the_fact_that_was_established(self):
        text = self._text('matchmaking/deal_activity.py')
        for expected in ('Connected', 'Funding Outcome Confirmed', 'Sale Outcome Confirmed'):
            self.assertIn(f"'label': '{expected}'", text)
        for retired in ("'label': 'Connection accepted'", "'label': 'Verified Funded'", "'label': 'Verified Sold'"):
            self.assertNotIn(retired, text)
