from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('zelda_api', '0037_entityverificationreport_failed_status')]
    operations = [
        migrations.AddField(model_name='documentsource', name='is_external_subject', field=models.BooleanField(default=False, help_text='Evidence about another business, never the uploader profile.')),
        migrations.AddField(model_name='documentsource', name='is_product_input', field=models.BooleanField(default=False, help_text='Unprocessed evidence staged for a one-time Zelda purchase.')),
        migrations.AddField(model_name='documentsource', name='external_cik', field=models.CharField(blank=True, max_length=10, help_text='SEC identity selected through the shared resolver, when available.')),
    ]
