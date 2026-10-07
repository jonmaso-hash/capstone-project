"""
Surface terminology contract for Phase 1.5E.

Internal route names and event keys remain stable (for example diligence_chat
and thumbs_up).  Only user-facing labels are standardized.
"""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class NavigationAnalyticsTerminologyTests(SimpleTestCase):
    def _text(self, relative_path):
        return (Path(settings.BASE_DIR) / relative_path).read_text(encoding='utf-8', errors='ignore')

    def test_navigation_calls_chat_messages_and_keeps_venture_insights(self):
        nav = self._text('templates/includes/main_navigation.html')
        self.assertIn('>Messages</a>', nav)
        self.assertNotIn('>Chat</a>', nav)
        self.assertIn('Venture Insights', nav)

    def test_role_analytics_names_are_role_specific(self):
        template = self._text('templates/accounts/profile_analysis.html')
        for label in ('Founder Insights', 'Seller Insights', 'Investor Analytics', 'Buyer Analytics'):
            self.assertIn(label, template)

    def test_profile_analytics_no_longer_exposes_thumbs_up_as_a_metric_label(self):
        template = self._text('templates/accounts/profile_analysis.html')
        self.assertIn('Marked Relevant', template)
        self.assertNotIn('>Thumbs Up</small>', template)

    def test_role_engagement_copy_uses_relevance_language(self):
        views = self._text('accounts/views.py')
        for label in (
            'Marked Relevant by Investors',
            'Marked Relevant by Buyers',
            'Companies Marked Relevant',
            'Listings Marked Relevant',
        ):
            self.assertIn(label, views)
        self.assertNotIn("'Thumbs Up Given'", views)
        self.assertNotIn("'Thumbs Up Received'", views)

    def test_funnel_presentation_uses_relevance_not_implementation_language(self):
        engine = self._text('matchmaking/insights_engine.py')
        self.assertIn("('thumbs_up', 'Marked Relevant')", engine)
        self.assertIn("'thumbs_up': 'Marked relevant'", engine)
        self.assertNotIn("('thumbs_up', 'Thumbs Up')", engine)
