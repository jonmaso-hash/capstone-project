from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import (
    PersonProfile, ProfessionalOrganization, OrganizationRelationship, EducationRecord,
)


class ProfessionalProfileFoundationTests(TestCase):
    def test_optional_profile_and_multiple_organizations(self):
        user = get_user_model().objects.create_user(username="profile_v2", password="test-password")
        self.assertFalse(PersonProfile.objects.filter(user=user).exists())
        person = PersonProfile.objects.create(user=user, headline="Founder")
        first = ProfessionalOrganization.objects.create(name="First Company")
        second = ProfessionalOrganization.objects.create(name="Second Company")
        OrganizationRelationship.objects.create(person=person, organization=first, role="founder")
        OrganizationRelationship.objects.create(person=person, organization=second, role="advisor")
        self.assertEqual(person.organization_relationships.count(), 2)
        self.assertFalse(person.organization_relationships.filter(is_public=True).exists())

    def test_education_is_private_by_default(self):
        user = get_user_model().objects.create_user(username="education_v2", password="test-password")
        person = PersonProfile.objects.create(user=user)
        record = EducationRecord.objects.create(person=person, institution="Example University")
        self.assertFalse(record.is_public)
