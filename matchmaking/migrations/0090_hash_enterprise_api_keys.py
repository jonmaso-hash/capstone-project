import hashlib

from django.db import migrations, models


def hash_existing_keys(apps, schema_editor):
    APIKey = apps.get_model('matchmaking', 'APIKey')
    for row in APIKey.objects.all().iterator():
        raw = row.key or ''
        row.key_hash = hashlib.sha256(raw.encode('utf-8')).hexdigest()
        row.key_prefix = raw[:12]
        row.save(update_fields=['key_hash', 'key_prefix'])


class Migration(migrations.Migration):

    dependencies = [
        ('matchmaking', '0089_peermarketbenchmark'),
    ]

    operations = [
        migrations.AddField(
            model_name='apikey',
            name='key_hash',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='apikey',
            name='key_prefix',
            field=models.CharField(blank=True, max_length=12),
        ),
        migrations.RunPython(hash_existing_keys, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='apikey',
            name='key',
        ),
        migrations.AlterField(
            model_name='apikey',
            name='key_hash',
            field=models.CharField(editable=False, max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name='apikey',
            name='key_prefix',
            field=models.CharField(editable=False, max_length=12),
        ),
    ]
