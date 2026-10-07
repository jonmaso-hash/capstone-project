from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('usersettings', '0005_usersettings_profile_picture')]
    operations = [migrations.AddField(
        model_name='usersettings', name='notification_retention_days',
        field=models.SmallIntegerField(default=0, choices=[
            (0, 'Keep notification history'),
            (-1, 'Remove ordinary updates after reading'),
            (7, 'Remove read updates older than 7 days'),
            (30, 'Remove read updates older than 30 days'),
        ]),
    )]
