"""
Give every seller listing that predates per-field visibility an explicit
starting state.

The authority already falls back to the policy default for an absent key, so an
unmigrated seller is not exposed by the lack of a row -- it gets SELLER_FIELD_
VISIBILITY's defaults at read time. This writes them down, for the same two
reasons 0079 did for founders: the state becomes legible in the data without
knowing the fallback rule, and field_visibility_defaults_applied_at answers
"was this listing migrated?", which an empty dict cannot.

Written with the 0079 lesson applied from the start. The values below are the
historical record of what this migration applied, frozen in this file. It
imports nothing from application code, so renaming or editing
SELLER_FIELD_VISIBILITY later cannot make a clean migration run fail, and
cannot silently give a fresh database different starting visibility than
production received.

Asking price starts PUBLIC because on a business-for-sale listing it is the
listing -- existing sellers keep showing it exactly as they do today. Revenue,
EBITDA and reason for sale start CONNECTED: before this, they were visible to
any signed-in account, and in bulk through the acquisition CSV.

Reversible: the reverse clears exactly what the forward wrote, and only for
rows it stamped, so a seller's own later choices are never discarded.
"""
from django.db import migrations
from django.utils import timezone

# The exact levels this migration applied. The historical record, not the
# source of current defaults -- those live in
# matchmaking.models.SELLER_FIELD_VISIBILITY and may change. Never edit this to
# change existing listings; write a new migration.
APPLIED_SELLER_FIELD_VISIBILITY = {
    'annual_revenue': 'CONNECTED',
    'asking_price': 'PUBLIC',
    'ebitda': 'CONNECTED',
    'reason_for_sale': 'CONNECTED',
}


def apply_starting_visibility(apps, schema_editor):
    SellerApplication = apps.get_model('matchmaking', 'SellerApplication')
    now = timezone.now()
    rows = []
    for listing in SellerApplication.objects.filter(field_visibility_defaults_applied_at__isnull=True):
        merged = dict(APPLIED_SELLER_FIELD_VISIBILITY)
        merged.update(listing.field_visibility or {})
        listing.field_visibility = merged
        listing.field_visibility_defaults_applied_at = now
        rows.append(listing)
    if rows:
        SellerApplication.objects.bulk_update(
            rows, ['field_visibility', 'field_visibility_defaults_applied_at'], batch_size=200
        )


def clear_starting_visibility(apps, schema_editor):
    SellerApplication = apps.get_model('matchmaking', 'SellerApplication')
    SellerApplication.objects.filter(field_visibility_defaults_applied_at__isnull=False).update(
        field_visibility={}, field_visibility_defaults_applied_at=None
    )


class Migration(migrations.Migration):

    dependencies = [
        ('matchmaking', '0080_sellerapplication_field_visibility_and_more'),
    ]

    operations = [
        migrations.RunPython(apply_starting_visibility, clear_starting_visibility),
    ]
