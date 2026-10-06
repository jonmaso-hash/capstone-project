from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('zelda_api', '0036_claimeddatapoint_usage_category')]

    operations = [
        migrations.AlterField(
            model_name='entityverificationreport',
            name='status',
            field=models.CharField(
                choices=[('pending', 'Checking'), ('complete', 'Complete'), ('failed', "Couldn't complete")],
                default='complete', max_length=10,
            ),
        ),
    ]
