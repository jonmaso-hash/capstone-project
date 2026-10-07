import hashlib

from django.contrib.auth.hashers import make_password
from django.db import migrations, models


def hash_existing_credentials(apps, schema_editor):
    APIKey = apps.get_model('matchmaking', 'APIKey')
    Verification = apps.get_model('matchmaking', 'BusinessEmailVerification')

    for row in APIKey.objects.all().iterator():
        raw = row.key or ''
        row.key_prefix = raw[:12]
        row.key_hash = hashlib.sha256(raw.encode('utf-8')).hexdigest()
        row.save(update_fields=['key_prefix', 'key_hash'])

    for row in Verification.objects.exclude(code='').iterator():
        row.code_hash = make_password(row.code)
        row.save(update_fields=['code_hash'])


class Migration(migrations.Migration):

    dependencies = [
        ('matchmaking', '0089_peermarketbenchmark'),
    ]

    operations = [
        migrations.AddField(
            model_name='apikey',
            name='key_hash',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='apikey',
            name='key_prefix',
            field=models.CharField(blank=True, db_index=True, max_length=12),
        ),
        migrations.AddField(
            model_name='businessemailverification',
            name='code_hash',
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.RunPython(hash_existing_credentials, migrations.RunPython.noop),
        migrations.RemoveField(model_name='apikey', name='key'),
        migrations.RemoveField(model_name='businessemailverification', name='code'),
        migrations.AlterField(
            model_name='apikey',
            name='key_hash',
            field=models.CharField(editable=False, max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name='apikey',
            name='key_prefix',
            field=models.CharField(db_index=True, editable=False, max_length=12),
        ),
        migrations.AlterField(
            model_name='businessemailverification',
            name='code_hash',
            field=models.CharField(blank=True, editable=False, max_length=128),
        ),
    ]
