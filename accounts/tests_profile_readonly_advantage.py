from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.models import Application


User = get_user_model()


class FounderProfileReadOnlyAdvantageTests(TestCase):
    def test_owner_profile_get_does_not_save_application_or_generate_embeddings(self):
        user = User.objects.create_user('profile_readonly_founder', password='x')
        Application.objects.create(
            user=user,
            company_name='Profile Co',
            founder_name='Founder',
            email='founder@example.com',
            description='',
            sector='Other',
            stage='Seed',
            is_private=True,
        )
        self.client.force_login(user)

        with patch('matchmaking.models.Application.save') as save_mock, \
             patch('matchmaking.services.ai_engine.generate_profile_embedding') as embed_mock:
            response = self.client.get(reverse('accounts:profile', args=[user.username]))

        self.assertEqual(response.status_code, 200)
        save_mock.assert_not_called()
        embed_mock.assert_not_called()
