import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('matchmaking', '0092_dataroom_report_categories')]
    operations = [
        migrations.AddField(model_name='dataroomdocument', name='size_bytes',
                            field=models.PositiveBigIntegerField(blank=True, help_text='Stored file size for Data Room quota accounting.', null=True)),
        migrations.CreateModel(
            name='DataRoomReportLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_kind', models.CharField(choices=[('document', 'Document'), ('order', 'Order')], max_length=12)),
                ('source_id', models.CharField(max_length=40)),
                ('report_key', models.CharField(max_length=32)),
                ('size_bytes', models.PositiveBigIntegerField(default=0)),
                ('saved_at', models.DateTimeField(auto_now_add=True)),
                ('founder', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='data_room_report_links', to='matchmaking.application')),
            ],
            options={'ordering': ['-saved_at'],
                     'constraints': [models.UniqueConstraint(fields=('founder', 'source_kind', 'source_id', 'report_key'), name='unique_data_room_report_link')]},
        ),
    ]
