from django.db import migrations

# Old (hiring-evaluation) vocabulary -> new (investment) vocabulary. Ordinal
# meaning preserved: strong_pass/pass (the two most negative old values)
# both collapse to PASS since the new 4-point scale has no "strongly
# decline" distinct from "decline" — the live prompt never produces that
# distinction either.
OLD_TO_NEW = {
    'strong_interest': 'STRONG_INVEST',
    'interview': 'INVEST',
    'consider': 'NEEDS_REVIEW',
    'pass': 'PASS',
    'strong_pass': 'PASS',
}


def backfill_forward(apps, schema_editor):
    IntelligenceMemo = apps.get_model('zelda_api', 'IntelligenceMemo')
    for old_value, new_value in OLD_TO_NEW.items():
        IntelligenceMemo.objects.filter(recommendation=old_value).update(recommendation=new_value)


def backfill_backward(apps, schema_editor):
    # Best-effort reverse mapping — INVEST/STRONG_INVEST/NEEDS_REVIEW/PASS
    # map back to a representative old value each. Not a perfect inverse
    # (strong_pass information is lost going forward), but keeps `migrate`
    # reversible rather than raising.
    IntelligenceMemo = apps.get_model('zelda_api', 'IntelligenceMemo')
    new_to_old = {
        'STRONG_INVEST': 'strong_interest',
        'INVEST': 'interview',
        'NEEDS_REVIEW': 'consider',
        'PASS': 'pass',
    }
    for new_value, old_value in new_to_old.items():
        IntelligenceMemo.objects.filter(recommendation=new_value).update(recommendation=old_value)


class Migration(migrations.Migration):

    dependencies = [
        ('zelda_api', '0020_alter_intelligencememo_recommendation'),
    ]

    operations = [
        migrations.RunPython(backfill_forward, backfill_backward),
    ]
