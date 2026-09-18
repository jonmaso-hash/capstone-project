"""
The memo's sections analyse instead of arguing a side.

Removing the verdict in 0023 was not enough while the sections underneath still
constructed a case: "Investment Thesis" was prompted as a bull case, and the
bull/bear sections asked Claude for the strongest case FOR and AGAINST
investing. The fields are renamed so the stored concept matches what the product
now means, and their prompts are rewritten in the same change.

**Content is carried over, not cleared.** This is the opposite of 0023 and
deliberately so: a verdict was a machine-generated conclusion the product no
longer stands behind, while these hold analysis text belonging to the founder's
document. Prose written under the old prompts still reads persuasively until
that document is re-analysed; moving it is a schema and presentation change,
and rewriting it would be a content mutation.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zelda_api', '0023_evidence_level_replaces_recommendation'),
    ]

    operations = [
        migrations.RenameField('intelligencememo', 'investment_thesis', 'business_model_analysis'),
        migrations.RenameField('intelligencememo', 'key_strengths', 'supported_points'),
        migrations.RenameField('intelligencememo', 'key_concerns', 'open_concerns'),
        migrations.RenameField('intelligencememo', 'what_would_change_decision', 'what_would_change_the_picture'),
        migrations.RenameField('intelligencememo', 'bull_case', 'upside_scenario'),
        migrations.RenameField('intelligencememo', 'base_case', 'base_scenario'),
        migrations.RenameField('intelligencememo', 'bear_case', 'downside_scenario'),
        migrations.AlterField(
            model_name='intelligencememo',
            name='business_model_analysis',
            field=models.TextField(
                help_text='How the company makes money, who its customers are, what drives growth, '
                          'and what evidence supports each — no conclusion about what to do about it',
            ),
        ),
        migrations.AlterField(
            model_name='intelligencememo',
            name='supported_points',
            field=models.TextField(blank=True, help_text='2-4 points the disclosed evidence supports, each cited'),
        ),
        migrations.AlterField(
            model_name='intelligencememo',
            name='open_concerns',
            field=models.TextField(
                blank=True,
                help_text='2-4 gaps, omissions or contradictions that remain unresolved, each cited',
            ),
        ),
        migrations.AlterField(
            model_name='intelligencememo',
            name='upside_scenario',
            field=models.TextField(
                blank=True,
                help_text='What would have to be true for the favourable reading, and what evidence bears on it',
            ),
        ),
        migrations.AlterField(
            model_name='intelligencememo',
            name='base_scenario',
            field=models.TextField(
                blank=True,
                help_text='What follows if the disclosed facts and current trajectory hold',
            ),
        ),
        migrations.AlterField(
            model_name='intelligencememo',
            name='downside_scenario',
            field=models.TextField(
                blank=True,
                help_text='What would have to be true for the unfavourable reading, and what evidence bears on it',
            ),
        ),
    ]
