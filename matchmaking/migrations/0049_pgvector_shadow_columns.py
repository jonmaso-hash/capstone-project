# Postgres-only ANN shadow columns (see Application.description_vector_pg /
# InvestorApplication.focus_vector_pg docstrings). The columns themselves
# are added as ordinary fields on every backend — pgvector's Django
# VectorField serializes to a plain text format (e.g. "[1.0,2.0]"), which
# SQLite stores fine as an opaque value with no ANN capability, so a normal
# AddField here is safe everywhere. What's genuinely Postgres-only is the
# `vector` extension and the HNSW index, both skipped as no-ops elsewhere.

import pgvector.django.vector
from django.db import migrations


def create_vector_extension(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")


def drop_vector_extension(apps, schema_editor):
    # Deliberately not dropping the extension on reverse — other tables/
    # migrations may depend on it, and CREATE EXTENSION IF NOT EXISTS is
    # already idempotent, so there's nothing to reverse here.
    pass


def create_hnsw_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS matchmaking_app_desc_vec_hnsw "
            "ON matchmaking_application USING hnsw (description_vector_pg vector_cosine_ops);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS matchmaking_inv_focus_vec_hnsw "
            "ON matchmaking_investorapplication USING hnsw (focus_vector_pg vector_cosine_ops);"
        )


def drop_hnsw_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP INDEX IF EXISTS matchmaking_app_desc_vec_hnsw;")
        cursor.execute("DROP INDEX IF EXISTS matchmaking_inv_focus_vec_hnsw;")


class Migration(migrations.Migration):

    dependencies = [
        ('matchmaking', '0048_alter_matchtrainingexample_source'),
    ]

    operations = [
        migrations.RunPython(create_vector_extension, drop_vector_extension),
        migrations.AddField(
            model_name='application',
            name='description_vector_pg',
            field=pgvector.django.vector.VectorField(blank=True, dimensions=768, null=True),
        ),
        migrations.AddField(
            model_name='investorapplication',
            name='focus_vector_pg',
            field=pgvector.django.vector.VectorField(blank=True, dimensions=768, null=True),
        ),
        migrations.RunPython(create_hnsw_indexes, drop_hnsw_indexes),
    ]
