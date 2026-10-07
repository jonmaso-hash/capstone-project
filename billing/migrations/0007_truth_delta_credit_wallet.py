from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0006_zeldaorder'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TruthDeltaCreditWallet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('balance', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='truth_delta_credit_wallet', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='TruthDeltaCreditPurchase',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('credits', models.PositiveSmallIntegerField(default=3)),
                ('amount', models.PositiveIntegerField(default=2500)),
                ('currency', models.CharField(default='usd', max_length=3)),
                ('status', models.CharField(choices=[('awaiting_payment', 'Awaiting payment'), ('paid', 'Paid'), ('canceled', 'Canceled')], default='awaiting_payment', max_length=24)),
                ('stripe_session_id', models.CharField(blank=True, max_length=255, null=True, unique=True)),
                ('checkout_url', models.URLField(blank=True, max_length=1000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='truth_delta_credit_purchases', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='TruthDeltaCreditRedemption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('credits_used', models.PositiveSmallIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('order', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='truth_delta_credit_redemption', to='billing.zeldaorder')),
                ('wallet', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='redemptions', to='billing.truthdeltacreditwallet')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
