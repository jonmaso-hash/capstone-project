"""
Give every profile that predates per-field visibility an explicit starting
state, rather than leaving it to a runtime default.

The authority already falls back to the declared default for an absent key, so
an unmigrated row is closed, not open. This migration is the second, independent
protection: with the levels written down, nobody reading the table has to know
the fallback rule to work out what a profile discloses, and
`field_visibility_defaults_applied_at` answers "was this ever migrated?" --
which an empty dict cannot, because a founder may legitimately clear every
setting back to the defaults.

Reversible: the reverse clears exactly what the forward wrote, and only for
rows it stamped, so a founder's own later choices are never discarded by a
rollback.
"""
from django.db import migrations
from django.utils import timezone


def apply_starting_visibility(apps, schema_editor):
    from matchmaking.models import MIGRATION_FIELD_VISIBILITY

    Application = apps.get_model('matchmaking', 'Application')
    now = timezone.now()
    rows = []
    for profile in Application.objects.filter(field_visibility_defaults_applied_at__isnull=True):
        # A founder cannot have set anything yet, but merging rather than
        # overwriting keeps this safe to re-run and safe to run late.
        merged = dict(MIGRATION_FIELD_VISIBILITY)
        merged.update(profile.field_visibility or {})
        profile.field_visibility = merged
        profile.field_visibility_defaults_applied_at = now
        rows.append(profile)
    if rows:
        Application.objects.bulk_update(
            rows, ['field_visibility', 'field_visibility_defaults_applied_at'], batch_size=200
        )


def clear_starting_visibility(apps, schema_editor):
    Application = apps.get_model('matchmaking', 'Application')
    Application.objects.filter(field_visibility_defaults_applied_at__isnull=False).update(
        field_visibility={}, field_visibility_defaults_applied_at=None
    )


class Migration(migrations.Migration):

    dependencies = [
        ('matchmaking', '0078_application_field_visibility_and_more'),
    ]

    operations = [
        migrations.RunPython(apply_starting_visibility, clear_starting_visibility),
    ]
