import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('matchmaking', '0088_fundraisinglead_deleted_at'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PeerMarketBenchmark',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('founder', 'Founder'), ('seller', 'Seller')], max_length=12)),
                ('subject_name', models.CharField(max_length=255)),
                ('cohort_label', models.CharField(blank=True, max_length=255)),
                ('subject_snapshot', models.JSONField(blank=True, default=dict)),
                ('interlink_benchmark', models.JSONField(blank=True, default=dict)),
                ('external_peers', models.JSONField(blank=True, default=list)),
                ('external_benchmark', models.JSONField(blank=True, default=dict)),
                ('sources', models.JSONField(blank=True, default=list)),
                ('narrative', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('ready', 'Ready'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('error_message', models.TextField(blank=True)),
                ('generated_at', models.DateTimeField(blank=True, null=True)),
                ('refresh_eligible_at', models.DateTimeField(blank=True, null=True)),
                ('share_token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('sharing_enabled', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('founder', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='peer_market_benchmarks', to='matchmaking.application')),
                ('seller', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='peer_market_benchmarks', to='matchmaking.sellerapplication')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='peer_market_benchmarks', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
