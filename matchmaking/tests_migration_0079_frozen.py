"""
Migration 0079 carries its own record of what it applied.

The first version read its values from `matchmaking.models.MIGRATION_FIELD_VISIBILITY`.
A migration runs against historical state, so that coupling had two failure
modes, one loud and one silent: removing or renaming the constant would make
every clean migration run raise ImportError -- which is exactly what a first
production deploy onto an empty Postgres database does -- and editing its values
would silently give a fresh database different starting visibility than
production received, with no error anywhere.

These tests deliberately do NOT assert that the frozen values equal
NEW_PROFILE_FIELD_VISIBILITY. That would rebuild the same coupling as a test:
it would fail the day current defaults are legitimately changed, and the
natural "fix" would be to edit the historical record to match.
"""
import ast
import importlib
from pathlib import Path

from django.apps import apps as django_apps
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from .models import Application, PROFILE_FIELD_VISIBILITY_LEVELS
from .tests import _mock_embedding_generation

MIGRATION = importlib.import_module('matchmaking.migrations.0079_backfill_field_visibility')
MIGRATION_PATH = Path(MIGRATION.__file__)


class MigrationIsSelfContainedTests(SimpleTestCase):

    def test_it_imports_nothing_from_application_code(self):
        """The regression this fix exists to prevent, checked from source."""
        tree = ast.parse(MIGRATION_PATH.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                self.assertFalse(
                    node.module.startswith('matchmaking.models') or node.module == 'matchmaking',
                    f'0079 imports from {node.module}; its values must be frozen in the file',
                )

    def test_every_frozen_level_is_one_the_authority_still_recognises(self):
        """A record the authority cannot read would fall back to defaults."""
        for field, level in MIGRATION.APPLIED_FIELD_VISIBILITY.items():
            self.assertIn(level, PROFILE_FIELD_VISIBILITY_LEVELS, field)

    def test_the_record_is_the_sixteen_fields_it_applied(self):
        self.assertEqual(len(MIGRATION.APPLIED_FIELD_VISIBILITY), 16)
        self.assertEqual(MIGRATION.APPLIED_FIELD_VISIBILITY['raising_amount'], 'CONNECTED')
        self.assertEqual(MIGRATION.APPLIED_FIELD_VISIBILITY['founder_name'], 'CONNECTED')
        self.assertEqual(MIGRATION.APPLIED_FIELD_VISIBILITY['pitch_deck'], 'PUBLIC')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class MigrationBehaviourTests(TestCase):
    """Run the forward and reverse functions against real rows."""

    def setUp(self):
        _mock_embedding_generation(self)

    def profile(self, username, **fields):
        user = User.objects.create_user(username, password='x')
        return Application.objects.create(
            user=user, company_name=f'{username} Co', founder_name='F', email=f'{username}@t.com',
            description='d', sector='SaaS', stage='Seed', **fields,
        )

    def unstamp(self, profile, visibility=None):
        Application.objects.filter(pk=profile.pk).update(
            field_visibility=visibility or {}, field_visibility_defaults_applied_at=None
        )

    def test_forward_applies_the_frozen_levels_and_stamps(self):
        p = self.profile('m0079a')
        self.unstamp(p)
        MIGRATION.apply_starting_visibility(django_apps, None)
        p.refresh_from_db()
        self.assertEqual(p.field_visibility, MIGRATION.APPLIED_FIELD_VISIBILITY)
        self.assertIsNotNone(p.field_visibility_defaults_applied_at)

    def test_forward_keeps_a_choice_already_present(self):
        p = self.profile('m0079b')
        self.unstamp(p, {'raising_amount': 'PUBLIC'})
        MIGRATION.apply_starting_visibility(django_apps, None)
        p.refresh_from_db()
        self.assertEqual(p.field_visibility['raising_amount'], 'PUBLIC')

    def test_forward_skips_an_already_stamped_profile(self):
        p = self.profile('m0079c')
        stamp = timezone.now()
        Application.objects.filter(pk=p.pk).update(
            field_visibility={'sector': 'PRIVATE'}, field_visibility_defaults_applied_at=stamp
        )
        MIGRATION.apply_starting_visibility(django_apps, None)
        p.refresh_from_db()
        self.assertEqual(p.field_visibility, {'sector': 'PRIVATE'})

    def test_reverse_clears_only_what_forward_stamped(self):
        stamped = self.profile('m0079d')
        untouched = self.profile('m0079e')
        self.unstamp(stamped)
        MIGRATION.apply_starting_visibility(django_apps, None)
        Application.objects.filter(pk=untouched.pk).update(
            field_visibility={'sector': 'PRIVATE'}, field_visibility_defaults_applied_at=None
        )
        MIGRATION.clear_starting_visibility(django_apps, None)
        stamped.refresh_from_db()
        untouched.refresh_from_db()
        self.assertEqual(stamped.field_visibility, {})
        self.assertEqual(untouched.field_visibility, {'sector': 'PRIVATE'})
