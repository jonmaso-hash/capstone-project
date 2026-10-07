import importlib
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TransactionTestCase

from .models import APIKey


class EnterpriseAPIKeyMigrationTests(TransactionTestCase):
    def test_existing_plaintext_keys_are_hashed_without_changing_access_state(self):
        # Exercise the data migration against the real historical schema in
        # an isolated table, without reversing an irreversible live migration.
        state = MigrationLoader(connection).project_state([
            ('matchmaking', '0089_peermarketbenchmark'),
        ])
        legacy = state.apps.get_model('matchmaking', 'APIKey')
        legacy._meta.db_table = 'test_legacy_enterprise_key'
        owner = get_user_model().objects.create_user('migration_key_owner')
        with connection.schema_editor() as editor:
            editor.create_model(legacy)
        try:
            raw = 'ab' * 32
            old = legacy.objects.create(owner_id=owner.pk, firm_name='Legacy',
                                        key=raw, is_active=False)
            # key_suffix is added before RunPython, while the key field still
            # has its historical name.
            from django.db import models
            suffix = models.CharField(max_length=4, editable=False, default='')
            suffix.set_attributes_from_name('key_suffix')
            with connection.schema_editor() as editor:
                editor.add_field(legacy, suffix)
            legacy.add_to_class('key_suffix', suffix)
            migration = importlib.import_module(
                'matchmaking.migrations.0090_hash_enterprise_api_keys')
            migration.hash_existing_keys(
                SimpleNamespace(get_model=lambda *args: legacy),
                SimpleNamespace(connection=connection),
            )
            old.refresh_from_db()
            self.assertEqual(old.key, APIKey.digest(raw))
            self.assertEqual(old.key_suffix, raw[-4:])
            self.assertEqual(old.owner_id, owner.pk)
            self.assertFalse(old.is_active)
        finally:
            with connection.schema_editor() as editor:
                editor.delete_model(legacy)
