"""Remove one confirmed unprocessed production upload from its owner's Library.

The source record remains intact for audit and can still be restored by removing
the LibraryHiddenItem. The exact match prevents changing any later Qibby upload.
"""
from datetime import datetime, timezone

from django.db import migrations


def hide_misplaced_upload(apps, schema_editor):
    Document = apps.get_model('zelda_api', 'DocumentSource')
    Hidden = apps.get_model('zelda_api', 'LibraryHiddenItem')
    document = Document.objects.using(schema_editor.connection.alias).filter(
        pk=1,
        uploaded_by__username='jonmason',
        filename='Qibby_Saves_LLC_Pitch_Deck.pptx',
        source_entity='Qibby Saves LLC',
        document_type='pitch_deck',
        status='ingested',
        created_at=datetime(2026, 10, 5, 12, 21, 25, 699509, tzinfo=timezone.utc),
    ).first()
    if document:
        Hidden.objects.using(schema_editor.connection.alias).get_or_create(
            user_id=document.uploaded_by_id, item_type='document', item_id=str(document.pk),
        )


class Migration(migrations.Migration):
    dependencies = [('zelda_api', '0039_libraryhiddenitem')]
    operations = [migrations.RunPython(hide_misplaced_upload, migrations.RunPython.noop)]
