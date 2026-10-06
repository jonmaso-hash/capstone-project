from unittest.mock import patch

from django.test import SimpleTestCase

from matchmaking.models import Application
from matchmaking.services.ai_engine import calculate_zelda_advantage


class ZeldaAdvantageReadOnlyTests(SimpleTestCase):
    def test_calculation_does_not_save_or_generate_embeddings(self):
        application = Application(
            company_name='Profile Co',
            founder_name='Founder',
            email='founder@example.com',
            description='',
            sector='Other',
            stage='Seed',
            raising_amount=0,
            prior_amount_raised=0,
        )

        with patch.object(application, 'save') as save_mock, \
             patch('matchmaking.services.ai_engine.generate_profile_embedding') as embed_mock:
            calculate_zelda_advantage(application)

        save_mock.assert_not_called()
        embed_mock.assert_not_called()
        self.assertEqual(application.zelda_score, 40)
