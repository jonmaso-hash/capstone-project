"""
No two accounts share an email address, whatever its case.

auth.User is Django's model, so the rule lives in a plain index here rather
than on the model: unique on LOWER(email), for non-blank emails only, so
accounts without an email are still allowed. Postgres and SQLite both accept
this statement. The migration fails if duplicates already exist; resolve
them first.
"""
from django.db import migrations

INDEX_NAME = 'accounts_auth_user_email_ci_uniq'


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0013_ratelimitevent'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunSQL(
            sql=f"CREATE UNIQUE INDEX {INDEX_NAME} ON auth_user (LOWER(email)) WHERE email <> ''",
            reverse_sql=f"DROP INDEX {INDEX_NAME}",
        ),
    ]
