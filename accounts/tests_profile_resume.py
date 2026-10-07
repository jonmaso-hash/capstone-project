from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class UnfinishedProfileTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('unfinished_profile')
        self.client.force_login(self.user)

    def test_selected_role_can_resume_after_leaving_form(self):
        for role in ('founder', 'investor', 'seller', 'buyer'):
            with self.subTest(role=role):
                self.client.post(reverse('accounts:choose_role'), {'role': role})
                page = self.client.get(reverse('accounts:profile_self'), follow=True)
                self.assertContains(page, 'Create a Profile')
                self.assertContains(page, reverse('jobs:create'))
                self.assertContains(page, '>Messages</a>')
                self.assertContains(page, '>Dashboard</a>')
                self.assertRedirects(
                    self.client.get(reverse('accounts:create_profile')),
                    reverse(f'usersettings:edit_{role}_profile'),
                    fetch_redirect_response=False,
                )

    def test_no_role_uses_existing_role_picker(self):
        self.assertRedirects(self.client.get(reverse('accounts:create_profile')),
                             reverse('accounts:choose_role'))
        self.assertRedirects(self.client.get(reverse('accounts:dashboard')),
                             reverse('matchmaking:founder_dashboard'), fetch_redirect_response=False)

    def test_dashboard_without_profile_shows_founder_connections_workspace(self):
        page = self.client.get(reverse('accounts:dashboard'), follow=True)
        self.assertEqual(page.status_code, 200)
        self.assertTemplateUsed(page, 'matchmaking/founder_dashboard.html')
        self.assertContains(page, 'Introduction requests')
        self.assertContains(page, 'Connections')
        self.assertContains(page, 'Fundraising CRM')
        self.assertNotContains(page, 'Create a Profile')
        self.assertNotContains(page, 'Milestones')
        self.assertNotContains(page, reverse('matchmaking:post_milestone'))

    def test_founder_dashboard_retains_investor_requests_crm_and_deal_room(self):
        from matchmaking.models import Application, InvestorApplication, Connection, FounderMilestone
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        founder = Application.objects.create(user=self.user, company_name='Founder Workspace')
        FounderMilestone.objects.create(founder=founder, milestone_type='product_launch', title='Platform launched')
        for status in ('PENDING', 'ACCEPTED'):
            investor_user = get_user_model().objects.create_user(f'workspace_investor_{status}')
            investor = InvestorApplication.objects.create(
                user=investor_user, full_name=f'Investor {status}', company_name=f'Fund {status}')
            connection = Connection.objects.create(
                founder=founder, investor=investor, status=status, initiated_by='INVESTOR')
            if status == 'ACCEPTED':
                accepted = connection
        page = self.client.get(reverse('accounts:dashboard'), follow=True)
        self.assertTemplateUsed(page, 'matchmaking/founder_dashboard.html')
        self.assertContains(page, 'Fund PENDING')
        self.assertContains(page, 'Fund ACCEPTED')
        self.assertContains(page, reverse('matchmaking:fundraising_crm'))
        self.assertContains(page, reverse('matchmaking:deal_workspace', args=[accepted.pk]))
        self.assertContains(page, 'Milestones')
        self.assertContains(page, reverse('matchmaking:post_milestone'))
        self.assertContains(page, 'Platform launched')
        profile_page = self.client.get(reverse('accounts:profile', args=[self.user.username]))
        self.assertContains(profile_page, 'Platform launched')
        self.assertEqual(len(page.context['pending_requests']), 1)

    def test_founder_workspace_crm_and_data_room_open_for_founder(self):
        from matchmaking.models import Application
        founder = Application.objects.create(user=self.user, company_name='Workspace Founder')
        self.assertEqual(self.client.get(reverse('matchmaking:fundraising_crm')).status_code, 200)
        self.assertEqual(self.client.get(reverse('matchmaking:data_room', args=[self.user.username])).status_code, 200)
        self.assertEqual(founder.user.username, self.user.username)

    def test_investor_still_routes_to_investor_dashboard(self):
        from matchmaking.models import InvestorApplication
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        InvestorApplication.objects.create(user=self.user, company_name='Investor Workspace')
        self.assertRedirects(self.client.get(reverse('accounts:dashboard')),
                             reverse('matchmaking:investor_dashboard'), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('matchmaking:founder_dashboard')).status_code, 403)

    def test_other_users_canvas_does_not_offer_profile_creation(self):
        other = get_user_model().objects.create_user('another_unfinished_profile')
        page = self.client.get(reverse('accounts:profile', args=[other.username]))
        self.assertNotContains(page, 'Create a Profile')

    def test_profile_creation_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('accounts:create_profile')).status_code, 302)
