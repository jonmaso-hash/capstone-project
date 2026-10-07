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

    def test_free_founder_crm_is_capped_at_seven_new_leads_per_month(self):
        for i in range(7):
            FundraisingLead.objects.create(founder=self.application, investor_name=f'Investor {i}')

        response = self.client.get(reverse('matchmaking:fundraising_crm'))
        self.assertContains(response, '7 of 7 new leads added this month')

        response = self.client.post(reverse('matchmaking:create_lead'), {
            'investor_name': 'Investor 8',
            'stage': 'LEADS',
        }, follow=True)
        self.assertContains(response, 'Free tier includes 7 new CRM leads per month.')
        self.assertEqual(FundraisingLead.objects.filter(founder=self.application).count(), 7)

    def test_deleting_lead_does_not_refund_monthly_allowance(self):
        leads = [
            FundraisingLead.objects.create(founder=self.application, investor_name=f'Investor {i}')
            for i in range(7)
        ]
        response = self.client.post(reverse('matchmaking:delete_lead', args=[leads[0].id]))
        self.assertRedirects(response, reverse('matchmaking:fundraising_crm'))
        leads[0].refresh_from_db()
        self.assertIsNotNone(leads[0].deleted_at)

        response = self.client.post(reverse('matchmaking:create_lead'), {
            'investor_name': 'Replacement Investor',
            'stage': 'LEADS',
        }, follow=True)
        self.assertContains(response, 'Free tier includes 7 new CRM leads per month.')
        self.assertEqual(
            FundraisingLead.objects.filter(founder=self.application, deleted_at__isnull=True).count(),
            6,
        )

    def test_downgraded_founder_keeps_existing_leads(self):
        self.application.is_premium = True
        self.application.save(update_fields=['is_premium'])
        leads = [
            FundraisingLead.objects.create(founder=self.application, investor_name=f'Investor {i}')
            for i in range(50)
        ]
        # Make the retained CRM history old enough that it does not consume the
        # current month's seven new additions after downgrade.
        from django.utils import timezone
        from datetime import timedelta
        FundraisingLead.objects.filter(id__in=[lead.id for lead in leads]).update(
            created_at=timezone.now() - timedelta(days=45),
        )

        self.application.is_premium = False
        self.application.save(update_fields=['is_premium'])

        response = self.client.get(reverse('matchmaking:fundraising_crm'))
        self.assertEqual(response.context['lead_count'], 50)
        self.assertEqual(response.context['monthly_additions'], 0)

        response = self.client.post(reverse('matchmaking:create_lead'), {
            'investor_name': 'New Free Lead',
            'stage': 'LEADS',
        })
        self.assertRedirects(response, reverse('matchmaking:fundraising_crm'))
        self.assertEqual(
            FundraisingLead.objects.filter(founder=self.application, deleted_at__isnull=True).count(),
            51,
        )

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
