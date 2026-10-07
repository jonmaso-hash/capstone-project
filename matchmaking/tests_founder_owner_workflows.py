from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.models import Application, FundraisingLead


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

    def test_free_founder_crm_is_capped_at_seven_leads(self):
        for i in range(7):
            FundraisingLead.objects.create(founder=self.application, investor_name=f'Investor {i}')

        response = self.client.get(reverse('matchmaking:fundraising_crm'))
        self.assertContains(response, '7/7 leads used (Free tier)')

        response = self.client.post(reverse('matchmaking:create_lead'), {
            'investor_name': 'Investor 8',
            'stage': 'LEADS',
        }, follow=True)
        self.assertContains(response, 'Free tier is limited to 7 CRM leads.')
        self.assertEqual(FundraisingLead.objects.filter(founder=self.application).count(), 7)

    def test_premium_founder_crm_is_unlimited(self):
        self.application.is_premium = True
        self.application.save(update_fields=['is_premium'])
        for i in range(8):
            FundraisingLead.objects.create(founder=self.application, investor_name=f'Investor {i}')

        response = self.client.post(reverse('matchmaking:create_lead'), {
            'investor_name': 'Investor 9',
            'stage': 'LEADS',
        })
        self.assertRedirects(response, reverse('matchmaking:fundraising_crm'))
        self.assertEqual(FundraisingLead.objects.filter(founder=self.application).count(), 9)

    def test_founder_owner_can_open_own_data_room(self):
        response = self.client.get(reverse('matchmaking:data_room', args=[self.user.username]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Data Room')
