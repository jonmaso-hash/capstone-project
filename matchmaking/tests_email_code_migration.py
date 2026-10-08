import importlib
from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.db import connection, models
from django.db.migrations.loader import MigrationLoader
from django.test import TransactionTestCase
from django.utils import timezone


class EmailCodeMigrationTests(TransactionTestCase):
    def test_only_latest_unexpired_pending_code_survives_migration(self):
        state = MigrationLoader(connection).project_state([('matchmaking', '0090_hash_enterprise_api_keys')])
        legacy = state.apps.get_model('matchmaking', 'BusinessEmailVerification')
        legacy._meta.db_table = 'test_legacy_email_codes'
        legacy._meta.indexes = []  # Avoid duplicating the live table's named index.
        legacy.add_to_class('code_hash', models.CharField(max_length=128, default=''))
        users = [get_user_model().objects.create_user(f'legacy_email_{i}') for i in range(3)]
        with connection.schema_editor() as editor:
            editor.create_model(legacy)
        try:
            def issue(user, code, **kwargs):
                return legacy.objects.create(user_id=user.pk, business_email='test@example.com',
                                             code=code, expires_at=timezone.now() + timedelta(minutes=30), **kwargs)
            old = issue(users[0], '111111')
            latest = issue(users[0], '222222')
            abandoned = issue(users[1], '333333')
            verified = issue(users[1], '444444', status='VERIFIED', verified_at=timezone.now())
            expired = issue(users[2], '555555')
            legacy.objects.filter(pk=expired.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
            module = importlib.import_module('matchmaking.migrations.0091_hash_business_email_codes')
            module.harden_existing_codes(SimpleNamespace(get_model=lambda *args: legacy),
                                         SimpleNamespace(connection=connection))
            latest.refresh_from_db()
            self.assertEqual(latest.status, 'PENDING')
            self.assertTrue(check_password('222222', latest.code_hash))
            for row in [old, abandoned, expired]:
                row.refresh_from_db()
                self.assertEqual(row.status, 'EXPIRED')
                self.assertEqual(row.code_hash, '')
            verified.refresh_from_db()
            self.assertEqual(verified.status, 'VERIFIED')
            self.assertIsNotNone(verified.verified_at)
            self.assertEqual(verified.code_hash, '')
        finally:
            with connection.schema_editor() as editor:
                editor.delete_model(legacy)
