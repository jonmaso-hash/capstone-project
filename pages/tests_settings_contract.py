"""
No setting may be REQUIRED at import time.

`env('X')` with no declared default raises ImproperlyConfigured when X is
absent. That is not a test failure -- it happens while Django is still
importing settings, so it takes down `manage.py check`, which is the FIRST
step of the blocking CI job, before a single test runs. The whole gate dies
with a configuration error rather than a test result.

It is invisible locally, which is what makes it worth a guard: `.env` supplies
the variable on a developer machine, so the setting resolves fine and nothing
suggests CI will behave differently. A secret in particular must never be
required -- CI deliberately does not have one.

The contract:

    every env(...) call in config/settings.py either declares a default in
    the environ.Env(...) block or passes one inline

An absent optional key then means "this integration is off", which is a state
the application can handle, instead of "the process cannot start", which it
cannot.

This is the same shape as the CI manifest guard and the missing-static-file
guard: something whose absence produces silence rather than an error, made
loud by a test.
"""
import ast
import io
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

SETTINGS_PATH = Path(settings.BASE_DIR) / 'config' / 'settings.py'


def _parse():
    return ast.parse(io.open(SETTINGS_PATH, encoding='utf-8').read())


def declared_defaults(tree):
    """Names given a default in the environ.Env(...) constructor."""
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'Env'):
            return {kw.arg for kw in node.keywords if kw.arg}
    return set()


def env_reads(tree):
    """
    Every env('NAME') / env.str('NAME') ... call, as
    (name, has_default). Covers both an inline default= and the positional
    second argument some environ helpers accept.
    """
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_env = (
            (isinstance(func, ast.Name) and func.id == 'env')
            or (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                and func.value.id == 'env')
        )
        if not is_env or not node.args:
            continue
        first = node.args[0]
        if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
            continue
        has_default = (any(kw.arg == 'default' for kw in node.keywords)
                       or len(node.args) > 1)
        out.append((first.value, has_default))
    return out


class TheGuardCanReadTheSettingsTests(SimpleTestCase):
    """
    Positive controls. The assertion below compares a list against []; a parse
    that silently found nothing would pass for the worst possible reason.
    """

    def test_the_settings_file_is_where_this_test_thinks_it_is(self):
        self.assertTrue(SETTINGS_PATH.is_file(), f'{SETTINGS_PATH} not found')

    def test_env_reads_are_discovered(self):
        self.assertGreater(len(env_reads(_parse())), 20,
                           'the parser found almost no env() calls; it is reading '
                           'the wrong thing')

    def test_the_declaration_block_is_discovered(self):
        self.assertGreater(len(declared_defaults(_parse())), 20,
                           'the environ.Env(...) block was not found')


class NoSettingIsRequiredAtImportTests(SimpleTestCase):

    def test_every_env_read_has_a_default(self):
        tree = _parse()
        declared = declared_defaults(tree)
        required = sorted({
            name for name, has_default in env_reads(tree)
            if not has_default and name not in declared
        })
        self.assertEqual(
            required, [],
            'These settings are REQUIRED at import, so a machine without them '
            'cannot start Django at all -- including CI, which fails at '
            '`manage.py check` before any test runs:\n  ' + '\n  '.join(required) +
            '\nGive each one a default in the environ.Env(...) block '
            "(e.g. NAME=(str, '')) so an absent key means the integration is "
            'off rather than the process cannot start.')

    def test_a_secret_is_never_required(self):
        """
        Stated separately because it is the case that actually bites: CI has
        no secrets by design, so a required API key is guaranteed to break it
        while working perfectly on every developer machine that has a .env.
        """
        tree = _parse()
        declared = declared_defaults(tree)
        secretish = sorted({
            name for name, has_default in env_reads(tree)
            if not has_default and name not in declared
            and any(word in name for word in ('KEY', 'SECRET', 'TOKEN', 'PASSWORD', 'DSN'))
        })
        self.assertEqual(secretish, [],
                         f'credentials required at import: {secretish}')
