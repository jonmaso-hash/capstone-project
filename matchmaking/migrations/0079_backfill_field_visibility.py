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


# The exact levels this migration applied, frozen here on purpose.
#
# This is the historical record of what 0079 wrote to profiles that predated
# per-field visibility -- NOT the source of current defaults. Those live in
# matchmaking.models.NEW_PROFILE_FIELD_VISIBILITY and may change freely; this
# must not. A migration runs against historical state, so reading these values
# from application code would mean that editing a live constant silently
# changes what a fresh database receives, and removing it would make every
# clean migration run fail. Both were true of the first version of this file.
#
# Never edit this dict to change visibility for existing profiles. Write a new
# migration.
APPLIED_FIELD_VISIBILITY = {
    'company_website': 'PUBLIC',
    'current_revenue': 'CONNECTED',
    'description': 'PUBLIC',
    'extra_info': 'PUBLIC',
    'founder_name': 'CONNECTED',
    'geography': 'PUBLIC',
    'linkedin_url': 'PUBLIC',
    'monthly_burn_rate': 'CONNECTED',
    'pitch_deck': 'PUBLIC',
    'prior_amount_raised': 'CONNECTED',
    'raising_amount': 'CONNECTED',
    'reason_for_capital': 'CONNECTED',
    'sector': 'PUBLIC',
    'stage': 'PUBLIC',
    'team_size': 'PUBLIC',
    'years_in_business': 'PUBLIC',
}


def apply_starting_visibility(apps, schema_editor):
    Application = apps.get_model('matchmaking', 'Application')
    now = timezone.now()
    rows = []
    for profile in Application.objects.filter(field_visibility_defaults_applied_at__isnull=True):
        # A founder cannot have set anything yet, but merging rather than
        # overwriting keeps this safe to re-run and safe to run late.
        merged = dict(APPLIED_FIELD_VISIBILITY)
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
