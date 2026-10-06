from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.models import Application


User = get_user_model()


class FounderOwnerWorkflowAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('owner_workflow_founder', password='x')
        self.application = Application.objects.create(
            user=self.user,
            founder_name='Owner Founder',
            email='owner@example.com',
            company_name='Owner Co',
            sector='SaaS',
            stage='Seed',
            description='Owner workflow smoke test',
            is_private=False,
        )
        self.client.force_login(self.user)

    def test_founder_owner_can_open_fundraising_crm(self):
        response = self.client.get(reverse('matchmaking:fundraising_crm'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Fundraising')

    def test_founder_owner_can_open_own_data_room(self):
        response = self.client.get(reverse('matchmaking:data_room', args=[self.user.username]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Data Room')
