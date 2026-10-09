from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import PersonProfile, EducationRecord, OrganizationRelationship, ProfessionalOrganization


class PublicProfessionalProfileTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="public_test_owner", password="testpass123")
        self.profile = PersonProfile.objects.create(user=self.user, display_name="Example Owner", biography="Overview text")
        EducationRecord.objects.create(person=self.profile, institution="Private College", is_public=False)
        EducationRecord.objects.create(person=self.profile, institution="Public College", is_public=True)
        org = ProfessionalOrganization.objects.create(name="Private Company")
        OrganizationRelationship.objects.create(person=self.profile, organization=org, role="founder", is_public=False)
        org2 = ProfessionalOrganization.objects.create(name="Public Company")
        OrganizationRelationship.objects.create(person=self.profile, organization=org2, role="advisor", is_public=True)
        self.url = reverse("accounts:public_professional_profile", args=[self.user.username])

    def test_overview_private_by_default(self):
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_public_page_filters_private_children(self):
        self.profile.is_public = True
        self.profile.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Overview text")
        self.assertContains(response, "Public College")
        self.assertContains(response, "Public Company")
        self.assertNotContains(response, "Private College")
        self.assertNotContains(response, "Private Company")

    def test_disabling_public_overview_hides_everything(self):
        self.profile.is_public = True
        self.profile.save()
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.profile.is_public = False
        self.profile.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)
