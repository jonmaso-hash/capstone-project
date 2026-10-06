import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('billing', '0005_subscription_consent'), ('zelda_api', '0038_product_document_subject'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name='ZeldaOrder', fields=[
        ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
        ('product', models.CharField(max_length=32)), ('reports', models.JSONField(default=list)),
        ('amount', models.PositiveIntegerField()), ('currency', models.CharField(default='usd', max_length=3)),
        ('status', models.CharField(choices=[('awaiting_payment', 'Awaiting payment'), ('paid', 'Paid'), ('processing', 'Processing'), ('ready', 'Ready'), ('failed', 'Could not finish'), ('canceled', 'Canceled')], default='awaiting_payment', max_length=24)),
        ('stripe_session_id', models.CharField(blank=True, max_length=255, null=True, unique=True)),
        ('checkout_url', models.URLField(blank=True, max_length=1000)),
        ('created_at', models.DateTimeField(auto_now_add=True)), ('paid_at', models.DateTimeField(blank=True, null=True)), ('finished_at', models.DateTimeField(blank=True, null=True)),
        ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='zelda_orders', to=settings.AUTH_USER_MODEL)),
        ('source_document', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='product_orders', to='zelda_api.documentsource')),
        ('analysis_document', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='analysis_orders', to='zelda_api.documentsource')),
        ('valuation_document', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='valuation_orders', to='zelda_api.documentsource')),
        ('entity_report', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='product_orders', to='zelda_api.entityverificationreport')),
    ], options={'ordering': ['-created_at']})]
