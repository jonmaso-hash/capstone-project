# Gemini removed (matchmaking/services/ai_engine.py now uses the local
# sentence-transformers 'all-MiniLM-L6-v2' model, fixed at 384 dimensions,
# instead of Gemini's 768-dim embed_content call) — the pgvector shadow
# columns need to shrink to match. Old 768-dim values (Postgres only; SQLite
# stores these as opaque text and is unaffected either way) can't be cast to
# 384 dimensions, so they're nulled out here and re-backfilled by the
# existing lazy-generation signals on next save.

import pgvector.django.vector
from django.db import migrations


def resize_pg_vector_columns(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP INDEX IF EXISTS matchmaking_app_desc_vec_hnsw;")
        cursor.execute("DROP INDEX IF EXISTS matchmaking_inv_focus_vec_hnsw;")
        cursor.execute("ALTER TABLE matchmaking_application ALTER COLUMN description_vector_pg TYPE vector(384) USING NULL;")
        cursor.execute("ALTER TABLE matchmaking_investorapplication ALTER COLUMN focus_vector_pg TYPE vector(384) USING NULL;")
        cursor.execute(
            "CREATE INDEX matchmaking_app_desc_vec_hnsw "
            "ON matchmaking_application USING hnsw (description_vector_pg vector_cosine_ops);"
        )
        cursor.execute(
            "CREATE INDEX matchmaking_inv_focus_vec_hnsw "
            "ON matchmaking_investorapplication USING hnsw (focus_vector_pg vector_cosine_ops);"
        )


def revert_pg_vector_columns(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP INDEX IF EXISTS matchmaking_app_desc_vec_hnsw;")
        cursor.execute("DROP INDEX IF EXISTS matchmaking_inv_focus_vec_hnsw;")
        cursor.execute("ALTER TABLE matchmaking_application ALTER COLUMN description_vector_pg TYPE vector(768) USING NULL;")
        cursor.execute("ALTER TABLE matchmaking_investorapplication ALTER COLUMN focus_vector_pg TYPE vector(768) USING NULL;")
        cursor.execute(
            "CREATE INDEX matchmaking_app_desc_vec_hnsw "
            "ON matchmaking_application USING hnsw (description_vector_pg vector_cosine_ops);"
        )
        cursor.execute(
            "CREATE INDEX matchmaking_inv_focus_vec_hnsw "
            "ON matchmaking_investorapplication USING hnsw (focus_vector_pg vector_cosine_ops);"
        )


class Migration(migrations.Migration):

    dependencies = [
        ('matchmaking', '0050_partition_page_event_and_training_example'),
    ]

    operations = [
        migrations.AlterField(
            model_name='application',
            name='description_vector_pg',
            field=pgvector.django.vector.VectorField(blank=True, dimensions=384, null=True),
        ),
        migrations.AlterField(
            model_name='investorapplication',
            name='focus_vector_pg',
            field=pgvector.django.vector.VectorField(blank=True, dimensions=384, null=True),
        ),
        migrations.RunPython(resize_pg_vector_columns, revert_pg_vector_columns),
    ]
