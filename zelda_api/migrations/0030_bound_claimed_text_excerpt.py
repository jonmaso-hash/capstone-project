"""
ClaimedDatapoint.text_excerpt held the whole source chunk: document text
copied outside the chunk boundary (Phase 1 Task 4 finding). New claims store
the claim's own sentence, bounded (truth_delta_tasks.bounded_excerpt). This
replaces the existing copies the same way, from claimed_value -- the claim's
sentence as stored. The chunks themselves are untouched; chunk_hash and
page_number keep the provenance. Irreversible by design: the old values were
duplicates of chunk text that still exists in DocumentChunk.
"""
from django.db import migrations

EXCERPT_CHARS = 300


def bound(text):
    text = ' '.join((text or '').split())
    return text if len(text) <= EXCERPT_CHARS else text[:EXCERPT_CHARS - 1] + '…'


def bound_existing_excerpts(apps, schema_editor):
    ClaimedDatapoint = apps.get_model('zelda_api', 'ClaimedDatapoint')
    for claim in ClaimedDatapoint.objects.exclude(text_excerpt='').only('id', 'claimed_value', 'text_excerpt').iterator():
        bounded = bound(claim.claimed_value)
        if claim.text_excerpt != bounded:
            ClaimedDatapoint.objects.filter(pk=claim.pk).update(text_excerpt=bounded)


class Migration(migrations.Migration):

    dependencies = [
        ('zelda_api', '0029_documentsource_verifying_status'),
    ]

    operations = [
        migrations.RunPython(bound_existing_excerpts, migrations.RunPython.noop),
    ]
