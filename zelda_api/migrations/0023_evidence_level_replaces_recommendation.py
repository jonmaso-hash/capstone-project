"""
The memo stops issuing a verdict.

`recommendation` held STRONG_INVEST / INVEST / NEEDS_REVIEW / PASS. It becomes
`evidence_level`, which says how well the company's statements are supported by
evidence and nothing about what the reader should do.

Existing rows are reset to NOT_CLASSIFIED rather than mapped. A verdict is not
an evidence rating, and converting one into the other would invent a fact that
was never measured. Re-analysing a document fills it in properly.

`investment_readiness` becomes `information_readiness` for the same reason: it
measures how complete the information is, not whether to invest.
"""
from django.db import migrations, models


def clear_verdicts(apps, schema_editor):
    apps.get_model('zelda_api', 'IntelligenceMemo').objects.update(evidence_level='NOT_CLASSIFIED')


def noop(apps, schema_editor):
    """Reversing restores the column, not the verdicts — those are gone on purpose."""


class Migration(migrations.Migration):

    dependencies = [
        ('zelda_api', '0022_entity_report_business_subject'),
    ]

    operations = [
        migrations.RenameField(
            model_name='intelligencememo',
            old_name='recommendation',
            new_name='evidence_level',
        ),
        migrations.RenameField(
            model_name='intelligencememo',
            old_name='investment_readiness',
            new_name='information_readiness',
        ),
        migrations.AlterField(
            model_name='intelligencememo',
            name='evidence_level',
            field=models.CharField(
                choices=[
                    ('WELL_EVIDENCED', 'Well evidenced'),
                    ('PARTLY_EVIDENCED', 'Partly evidenced'),
                    ('LIMITED_EVIDENCE', 'Limited evidence'),
                    ('LITTLE_EVIDENCE', 'Little evidence found'),
                    ('NOT_CLASSIFIED', 'Not classified'),
                ],
                default='NOT_CLASSIFIED',
                help_text='How much of what the company states is supported by evidence Zelda '
                          'could find. Never a view on whether to invest.',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='intelligencememo',
            name='information_readiness',
            field=models.TextField(
                blank=True,
                help_text='0-100 score for how complete and reviewable the information is — '
                          'not an assessment of whether an investment should be made',
            ),
        ),
        migrations.RunPython(clear_verdicts, noop),
    ]
