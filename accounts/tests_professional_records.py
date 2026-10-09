from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import EducationRecord, OrganizationRelationship, PersonProfile


class ProfessionalRecordEditorTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner_records", password="test-pass")
        self.other = User.objects.create_user(username="other_records", password="test-pass")
        self.client.force_login(self.owner)

    def test_add_education_private_by_default(self):
        response = self.client.post(reverse("accounts:add_professional_education"), {
            "institution": "State University", "credential": "BA", "field_of_study": "Business"
        })
        self.assertEqual(response.status_code, 302)
        record = EducationRecord.objects.get(person__user=self.owner)
        self.assertFalse(record.is_public)

    def test_education_date_order(self):
        response = self.client.post(reverse("accounts:add_professional_education"), {
            "institution": "University", "started_on": "2025-01-01", "ended_on": "2024-01-01"
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EducationRecord.objects.filter(person__user=self.owner).exists())

    def test_organization_create_edit_and_delete(self):
        add = reverse("accounts:add_professional_organization")
        data = {"organization_name": "Example Co", "role": "founder", "title": "CEO"}
        self.assertEqual(self.client.post(add, data).status_code, 302)
        relation = OrganizationRelationship.objects.get(person__user=self.owner)
        self.assertFalse(relation.is_public)
        self.assertEqual(relation.organization.name, "Example Co")
        data["organization_name"] = "Renamed Co"
        self.assertEqual(self.client.post(reverse("accounts:edit_professional_organization", args=[relation.pk]), data).status_code, 302)
        relation.refresh_from_db()
        self.assertEqual(relation.organization.name, "Renamed Co")
        self.assertEqual(self.client.post(reverse("accounts:delete_professional_organization", args=[relation.pk])).status_code, 302)
        self.assertFalse(OrganizationRelationship.objects.filter(pk=relation.pk).exists())

    def test_cannot_modify_other_users_records(self):
        person = PersonProfile.objects.create(user=self.other)
        education = EducationRecord.objects.create(person=person, institution="Private School")
        self.assertEqual(self.client.post(reverse("accounts:delete_professional_education", args=[education.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("accounts:edit_professional_education", args=[education.pk])).status_code, 404)
        self.assertTrue(EducationRecord.objects.filter(pk=education.pk).exists())

    def test_delete_requires_post(self):
        self.client.post(reverse("accounts:add_professional_education"), {"institution": "School"})
        record = EducationRecord.objects.get(person__user=self.owner)
        self.assertEqual(self.client.get(reverse("accounts:delete_professional_education", args=[record.pk])).status_code, 405)
        self.assertTrue(EducationRecord.objects.filter(pk=record.pk).exists())
