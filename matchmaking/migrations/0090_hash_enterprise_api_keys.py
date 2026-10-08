import hashlib

from django.db import migrations, models


def hash_existing_keys(apps, schema_editor):
    APIKey = apps.get_model('matchmaking', 'APIKey')
    database = schema_editor.connection.alias
    for key in APIKey.objects.using(database).all().iterator():
        APIKey.objects.using(database).filter(pk=key.pk).update(
            key=hashlib.sha256(key.key.encode('utf-8')).hexdigest(),
            key_suffix=key.key[-4:],
        )


class Migration(migrations.Migration):
    dependencies = [('matchmaking', '0089_peermarketbenchmark')]

    operations = [
        migrations.AddField(
            model_name='apikey', name='key_suffix',
            field=models.CharField(max_length=4, editable=False, default=''),
            preserve_default=False,
        ),
        # Deliberately irreversible: recovering plaintext would defeat hashing.
        migrations.RunPython(hash_existing_keys),
        migrations.RenameField(model_name='apikey', old_name='key', new_name='key_hash'),
    ]
