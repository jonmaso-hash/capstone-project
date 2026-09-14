"""
Fills the usernames kept on reports and impersonation logs (added in 0003) for
rows created before those fields existed, so a report or log whose account is
deleted later still names who it involved.
"""
from django.db import migrations


def fill_usernames(apps, schema_editor):
    UserReport = apps.get_model('ops', 'UserReport')
    ImpersonationLog = apps.get_model('ops', 'ImpersonationLog')

    reports = UserReport.objects.filter(reported_username='', reported_user__isnull=False).select_related('reported_user')
    for report in reports:
        report.reported_username = report.reported_user.username
        report.save(update_fields=['reported_username'])

    for log in ImpersonationLog.objects.select_related('impersonator', 'target'):
        changed = []
        if log.impersonator_id and not log.impersonator_username:
            log.impersonator_username = log.impersonator.username
            changed.append('impersonator_username')
        if log.target_id and not log.target_username:
            log.target_username = log.target.username
            changed.append('target_username')
        if changed:
            log.save(update_fields=changed)


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0003_keep_safety_records_after_account_deletion'),
    ]

    operations = [
        migrations.RunPython(fill_usernames, migrations.RunPython.noop),
    ]
