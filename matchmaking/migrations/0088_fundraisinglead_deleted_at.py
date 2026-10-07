from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('matchmaking', '0087_companyrepresentationattestation'),
    ]

    operations = [
        migrations.AddField(
            model_name='fundraisinglead',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
