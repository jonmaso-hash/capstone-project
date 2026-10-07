from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('matchmaking', '0086_provision_live_founder_scaffold'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanyRepresentationAttestation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company_name', models.CharField(max_length=255)),
                ('relationship', models.CharField(choices=[
                    ('FOUNDER_OWNER', 'Founder / Owner'),
                    ('OFFICER_EXECUTIVE', 'Officer / Executive'),
                    ('EMPLOYEE', 'Employee'),
                    ('INVESTOR_REPRESENTATIVE', 'Investor / Fund Representative'),
                    ('BUYER_REPRESENTATIVE', 'Buyer / Acquirer Representative'),
                    ('SELLER_REPRESENTATIVE', 'Seller Representative'),
                    ('AUTHORIZED_ADVISOR', 'Authorized Advisor'),
                    ('OTHER', 'Other'),
                ], max_length=32)),
                ('role_title', models.CharField(blank=True, max_length=255)),
                ('authorized_to_represent', models.BooleanField(default=False)),
                ('attested_at', models.DateTimeField(auto_now_add=True)),
                ('withdrawn_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='company_representation_attestations',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-attested_at']},
        ),
        migrations.AddIndex(
            model_name='companyrepresentationattestation',
            index=models.Index(fields=['user', 'withdrawn_at'], name='matchmaking_user_id_43a739_idx'),
        ),
        migrations.AddIndex(
            model_name='companyrepresentationattestation',
            index=models.Index(fields=['company_name'], name='matchmaking_company_9d8735_idx'),
        ),
    ]
