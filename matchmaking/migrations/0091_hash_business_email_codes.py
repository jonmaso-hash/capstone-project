from django.contrib.auth.hashers import make_password
from django.db import migrations, models
from django.utils import timezone


def harden_existing_codes(apps, schema_editor):
    Verification = apps.get_model('matchmaking', 'BusinessEmailVerification')
    rows = Verification.objects.using(schema_editor.connection.alias)
    seen = set()
    now = timezone.now()
    for row in rows.order_by('user_id', '-created_at', '-pk').iterator():
        status = row.status
        if status == 'PENDING' and (row.user_id in seen or row.expires_at <= now):
            status = 'EXPIRED'
        seen.add(row.user_id)
        rows.filter(pk=row.pk).update(
            status=status, code_hash=make_password(row.code) if status == 'PENDING' else '',
        )


class Migration(migrations.Migration):
    dependencies = [('matchmaking', '0090_hash_enterprise_api_keys')]
    operations = [
        migrations.AddField(
            model_name='businessemailverification', name='code_hash',
            field=models.CharField(max_length=128, editable=False, default=''),
            preserve_default=False,
        ),
        migrations.RunPython(harden_existing_codes),
        migrations.RemoveField(model_name='businessemailverification', name='code'),
        migrations.AddConstraint(
            model_name='businessemailverification',
            constraint=models.UniqueConstraint(fields=['user'], condition=models.Q(status='PENDING'),
                                               name='one_pending_business_email_code'),
        ),
    ]
