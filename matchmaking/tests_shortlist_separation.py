from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from matchmaking.models import Application, InvestorApplication, InvestorShortlist, MatchFeedback


class InvestorShortlistSeparationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("shortlist_investor", password="x")
        self.investor = InvestorApplication.objects.create(
            user=self.user,
            full_name="Investor",
            company_name="Fund",
            email="investor@example.com",
            investment_focus="SaaS",
            investment_stage="Seed",
        )
        founder_user = User.objects.create_user("shortlist_founder", password="x")
        self.founder = Application.objects.create(
            user=founder_user,
            company_name="Saved Co",
            founder_name="Founder",
            email="founder@example.com",
            description="A software company for shortlist tests.",
            sector="SaaS",
            stage="Seed",
        )
        self.client.force_login(self.user)

    def test_positive_feedback_does_not_add_to_shortlist(self):
        response = self.client.post(
            reverse("matchmaking:record_vote"),
            {"application_id": self.founder.id, "vote": "up"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            MatchFeedback.objects.filter(
                investor=self.investor, application=self.founder, vote=1
            ).exists()
        )
        self.assertFalse(
            InvestorShortlist.objects.filter(
                investor=self.investor, application=self.founder
            ).exists()
        )

    def test_shortlist_save_does_not_create_feedback(self):
        response = self.client.post(
            reverse("matchmaking:toggle_investor_shortlist"),
            {"application_id": self.founder.id},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            InvestorShortlist.objects.filter(
                investor=self.investor, application=self.founder
            ).exists()
        )
        self.assertFalse(
            MatchFeedback.objects.filter(
                investor=self.investor, application=self.founder
            ).exists()
        )

    def test_shortlist_toggle_removes_saved_company(self):
        InvestorShortlist.objects.create(
            investor=self.investor, application=self.founder
        )
        self.client.post(
            reverse("matchmaking:toggle_investor_shortlist"),
            {"application_id": self.founder.id},
        )
        self.assertFalse(
            InvestorShortlist.objects.filter(
                investor=self.investor, application=self.founder
            ).exists()
        )

    def test_shortlist_page_uses_saved_state_not_positive_feedback(self):
        other_user = User.objects.create_user("feedback_only_founder", password="x")
        feedback_only = Application.objects.create(
            user=other_user,
            company_name="Feedback Only",
            founder_name="F",
            email="f@example.com",
            description="Another software company for shortlist tests.",
            sector="SaaS",
            stage="Seed",
        )
        MatchFeedback.objects.create(
            user=self.user,
            investor=self.investor,
            application=feedback_only,
            vote=1,
        )
        InvestorShortlist.objects.create(
            investor=self.investor,
            application=self.founder,
        )

        response = self.client.get(reverse("matchmaking:investor_shortlist"))

        self.assertContains(response, "Saved Co")
        self.assertNotContains(response, "Feedback Only")
