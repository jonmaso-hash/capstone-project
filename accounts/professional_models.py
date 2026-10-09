"""Optional professional identity records; existing marketplace applications remain authoritative."""
from django.conf import settings
from django.db import models


class PersonProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="professional_profile")
    display_name = models.CharField(max_length=255, blank=True)
    is_public = models.BooleanField(default=False, help_text="Publish my professional overview publicly.")
    headline = models.CharField(max_length=255, blank=True)
    biography = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    website = models.URLField(max_length=500, blank=True)
    linkedin_url = models.URLField(max_length=500, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name or self.user.get_username()


class ProfessionalOrganization(models.Model):
    name = models.CharField(max_length=255)
    website = models.URLField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class OrganizationRelationship(models.Model):
    ROLE_CHOICES = [
        ("founder", "Founder"), ("owner", "Owner"), ("employee", "Employee"),
        ("advisor", "Advisor"), ("investor", "Investor"), ("other", "Other"),
    ]
    person = models.ForeignKey(PersonProfile, on_delete=models.CASCADE, related_name="organization_relationships")
    organization = models.ForeignKey(ProfessionalOrganization, on_delete=models.CASCADE, related_name="people")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    title = models.CharField(max_length=255, blank=True)
    started_on = models.DateField(null=True, blank=True)
    ended_on = models.DateField(null=True, blank=True)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.person} — {self.organization} ({self.role})"


class EducationRecord(models.Model):
    person = models.ForeignKey(PersonProfile, on_delete=models.CASCADE, related_name="education")
    institution = models.CharField(max_length=255)
    credential = models.CharField(max_length=255, blank=True)
    field_of_study = models.CharField(max_length=255, blank=True)
    started_on = models.DateField(null=True, blank=True)
    ended_on = models.DateField(null=True, blank=True)
    is_public = models.BooleanField(default=False)

    def __str__(self):
        return self.institution
