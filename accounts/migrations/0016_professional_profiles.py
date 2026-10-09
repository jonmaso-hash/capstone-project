# Generated for the additive Profile Architecture 2.0 foundation.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0015_staff_mfa"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProfessionalOrganization",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("website", models.URLField(blank=True, max_length=500)),
                ("description", models.TextField(blank=True)),
                ("location", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="PersonProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("display_name", models.CharField(blank=True, max_length=255)),
                ("headline", models.CharField(blank=True, max_length=255)),
                ("biography", models.TextField(blank=True)),
                ("location", models.CharField(blank=True, max_length=255)),
                ("website", models.URLField(blank=True, max_length=500)),
                ("linkedin_url", models.URLField(blank=True, max_length=500)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="professional_profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="OrganizationRelationship",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("founder", "Founder"), ("owner", "Owner"), ("employee", "Employee"), ("advisor", "Advisor"), ("investor", "Investor"), ("other", "Other")], max_length=20)),
                ("title", models.CharField(blank=True, max_length=255)),
                ("started_on", models.DateField(blank=True, null=True)),
                ("ended_on", models.DateField(blank=True, null=True)),
                ("is_public", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="people", to="accounts.professionalorganization")),
                ("person", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="organization_relationships", to="accounts.personprofile")),
            ],
        ),
        migrations.CreateModel(
            name="EducationRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("institution", models.CharField(max_length=255)),
                ("credential", models.CharField(blank=True, max_length=255)),
                ("field_of_study", models.CharField(blank=True, max_length=255)),
                ("started_on", models.DateField(blank=True, null=True)),
                ("ended_on", models.DateField(blank=True, null=True)),
                ("is_public", models.BooleanField(default=False)),
                ("person", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="education", to="accounts.personprofile")),
            ],
        ),
    ]
