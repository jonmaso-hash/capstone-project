"""
Production settings that only matter once DEBUG is off.

Settings are evaluated once at import, so the production-shaped cases load them
in a subprocess with the environment a host would set. That imports settings
only -- no apps, no models -- so it stays fast and runs in the blocking CI job.

What is pinned:
- static files use WhiteNoise's hashed, compressed storage in production, even
  when S3 is configured (S3 holds uploads only), and the plain storage with
  DEBUG on so dev and CI need no collectstatic;
- CSRF_TRUSTED_ORIGINS comes from the environment;
- production logs to the console only;
- every literal {% static %} path resolves. Under the manifest storage an
  unresolvable one raises at render time -- a 500 -- which is how a dead
  css/favorites.css link on the favorites page was found;
- no collected stylesheet points at /media/, which production never serves
  from the app (the homepage hero image lived there).
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)
MANIFEST = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
PLAIN = 'django.contrib.staticfiles.storage.StaticFilesStorage'

_PROBE = (
    "import json; from django.conf import settings as s; "
    "print('SETTINGS_JSON=' + json.dumps({"
    "'debug': s.DEBUG, "
    "'staticfiles': s.STORAGES['staticfiles']['BACKEND'], "
    "'default': s.STORAGES['default']['BACKEND'], "
    "'csrf': s.CSRF_TRUSTED_ORIGINS, "
    "'root_handlers': s.LOGGING['root']['handlers'], "
    "'django_handlers': s.LOGGING['loggers']['django']['handlers'], "
    "'handler_names': sorted(s.LOGGING['handlers']), "
    "'object_params': getattr(s, 'AWS_S3_OBJECT_PARAMETERS', None), "
    "}))"
)


def _settings_with(**env):
    """Load config.settings in a fresh interpreter under the given environment."""
    child_env = dict(os.environ)
    child_env.update({
        'DJANGO_SETTINGS_MODULE': 'config.settings',
        'SECRET_KEY': 'test-only-production-settings-probe',
        'ALLOWED_HOSTS': 'localhost',
        'STRIPE_SECRET_KEY': '',
        'AWS_STORAGE_BUCKET_NAME': '',
        'CSRF_TRUSTED_ORIGINS': '',
        'LOG_TO_FILE': '',
        'SENTRY_DSN': '',
        # These probes load production-shaped settings with no S3 bucket, which
        # config/storage_guard.py refuses by default. They are testing static
        # files and logging, not storage, so they acknowledge the ephemeral
        # media explicitly rather than each one tripping the guard.
        # MediaStorageGuardTests overrides this to test the guard itself.
        'ALLOW_EPHEMERAL_MEDIA': '1',
    })
    child_env = {k: v for k, v in child_env.items() if v != ''} | {k: v for k, v in env.items()}
    result = subprocess.run(
        [sys.executable, '-c', _PROBE], cwd=ROOT, env=child_env,
        capture_output=True, text=True, timeout=120,
    )
    line = next((l for l in result.stdout.splitlines() if l.startswith('SETTINGS_JSON=')), None)
    if line is None:
        raise AssertionError(f'settings failed to load:\n{result.stderr[-2000:]}')
    return json.loads(line[len('SETTINGS_JSON='):])


def _settings_refused(**env):
    """Load settings expecting ImproperlyConfigured; return the message."""
    child_env = dict(os.environ)
    child_env.update({
        'DJANGO_SETTINGS_MODULE': 'config.settings',
        'SECRET_KEY': 'test-only-production-settings-probe',
        'ALLOWED_HOSTS': 'localhost',
        'STRIPE_SECRET_KEY': '',
        'AWS_STORAGE_BUCKET_NAME': '',
        'CSRF_TRUSTED_ORIGINS': '',
        'LOG_TO_FILE': '',
        'SENTRY_DSN': '',
        'ALLOW_EPHEMERAL_MEDIA': '',
    })
    child_env = {k: v for k, v in child_env.items() if v != ''} | {k: v for k, v in env.items()}
    result = subprocess.run(
        [sys.executable, '-c', _PROBE], cwd=ROOT, env=child_env,
        capture_output=True, text=True, timeout=120,
    )
    if any(l.startswith('SETTINGS_JSON=') for l in result.stdout.splitlines()):
        raise AssertionError('settings loaded, but should have been refused')
    return result.stderr


class MediaStorageGuardTests(SimpleTestCase):
    """
    Production must not silently store uploads on a container's local disk.

    Found on the first Render deploy: no S3 bucket was configured, so every
    FileField wrote to the container filesystem. A founder uploading a cap table
    got a success message, and the file was destroyed by the next deploy. The
    upload path was working correctly; the storage underneath it was disposable,
    and nothing anywhere said so.

    The guard makes that combination deliberate instead of accidental. It is not
    absolute: bringing up a new environment (proving the database, running
    migrations) legitimately happens before object storage exists, so an
    explicit ALLOW_EPHEMERAL_MEDIA acknowledges the trade rather than pretending
    it is safe. What it forbids is arriving there by omission.
    """

    def test_production_without_a_bucket_refuses_to_start(self):
        message = _settings_refused(DEBUG='False')
        self.assertIn('ALLOW_EPHEMERAL_MEDIA', message)
        self.assertIn('AWS_STORAGE_BUCKET_NAME', message)

    def test_production_with_a_bucket_starts(self):
        loaded = _settings_with(DEBUG='False', AWS_STORAGE_BUCKET_NAME='interlink-uploads',
                                ALLOW_EPHEMERAL_MEDIA='')
        self.assertEqual(loaded['default'], 'storages.backends.s3.S3Storage')

    def test_development_without_a_bucket_is_unaffected(self):
        """Local dev and CI have no S3 and must never need it."""
        loaded = _settings_with(DEBUG='True', ALLOW_EPHEMERAL_MEDIA='')
        self.assertEqual(loaded['default'], 'django.core.files.storage.FileSystemStorage')

    def test_an_explicit_acknowledgement_allows_bring_up(self):
        loaded = _settings_with(DEBUG='False', ALLOW_EPHEMERAL_MEDIA='1')
        self.assertEqual(loaded['default'], 'django.core.files.storage.FileSystemStorage')

    def test_uploads_are_encrypted_at_rest(self):
        loaded = _settings_with(DEBUG='False', AWS_STORAGE_BUCKET_NAME='interlink-uploads')
        self.assertEqual((loaded['object_params'] or {}).get('ServerSideEncryption'), 'AES256')

    def test_no_bucket_means_no_s3_object_parameters(self):
        self.assertIsNone(_settings_with(DEBUG='True')['object_params'])


class StaticStorageTests(SimpleTestCase):

    def test_production_uses_hashed_compressed_static_files(self):
        loaded = _settings_with(DEBUG='False')
        self.assertFalse(loaded['debug'])
        self.assertEqual(loaded['staticfiles'], MANIFEST)

    def test_static_files_stay_on_whitenoise_when_s3_holds_the_uploads(self):
        loaded = _settings_with(DEBUG='False', AWS_STORAGE_BUCKET_NAME='interlink-uploads')
        self.assertEqual(loaded['default'], 'storages.backends.s3.S3Storage')
        self.assertEqual(loaded['staticfiles'], MANIFEST)

    def test_dev_and_ci_use_the_plain_storage_that_needs_no_collectstatic(self):
        self.assertEqual(_settings_with(DEBUG='True')['staticfiles'], PLAIN)

    def test_the_static_directory_is_listed_once(self):
        resolved = [Path(d).resolve() for d in settings.STATICFILES_DIRS]
        self.assertEqual(len(resolved), len(set(resolved)))


class CsrfTrustedOriginsTests(SimpleTestCase):

    def test_origins_come_from_the_environment(self):
        loaded = _settings_with(
            DEBUG='False', CSRF_TRUSTED_ORIGINS='https://interlinkfoundry.com,https://interlink.onrender.com')
        self.assertEqual(loaded['csrf'], ['https://interlinkfoundry.com', 'https://interlink.onrender.com'])

    def test_no_origins_are_trusted_by_default(self):
        self.assertEqual(_settings_with(DEBUG='False')['csrf'], [])


class LoggingTests(SimpleTestCase):

    def test_production_logs_to_the_console_only(self):
        loaded = _settings_with(DEBUG='False')
        self.assertEqual(loaded['root_handlers'], ['console'])
        self.assertEqual(loaded['django_handlers'], ['console'])
        self.assertNotIn('file', loaded['handler_names'])

    def test_the_log_file_can_be_turned_on_explicitly(self):
        loaded = _settings_with(DEBUG='False', LOG_TO_FILE='True')
        self.assertEqual(loaded['root_handlers'], ['console', 'file'])
        self.assertIn('file', loaded['handler_names'])

    def test_local_dev_keeps_the_log_file_by_default(self):
        self.assertIn('file', _settings_with(DEBUG='True')['root_handlers'])


class StaticReferenceTests(SimpleTestCase):

    LITERAL_STATIC = re.compile(r"""\{%\s*static\s+(['"])(?P<path>[^'"]+)\1""")

    def _templates(self):
        for base in [ROOT / 'templates', *ROOT.glob('*/templates')]:
            if 'venv' in base.parts:
                continue
            yield from base.rglob('*.html')

    def test_every_literal_static_reference_resolves(self):
        missing = []
        for template in self._templates():
            for match in self.LITERAL_STATIC.finditer(template.read_text(encoding='utf-8', errors='ignore')):
                if not finders.find(match.group('path')):
                    missing.append(f"{template.relative_to(ROOT).as_posix()}: {match.group('path')}")
        self.assertEqual(missing, [])

    def test_no_template_hard_codes_a_media_path(self):
        """
        Production never serves /media/ from the app (uploads live in S3), so a
        site asset linked as /media/... breaks there. Uploaded files are linked
        through their FileField .url, never a literal.
        """
        offenders = []
        for template in self._templates():
            text = template.read_text(encoding='utf-8', errors='ignore')
            for match in re.finditer(r"""(?:src|href)\s*=\s*['"]/media/[^'"]*""", text):
                offenders.append(f"{template.relative_to(ROOT).as_posix()}: {match.group(0)}")
        self.assertEqual(offenders, [])

    def test_no_stylesheet_points_at_media(self):
        offenders = []
        for directory in settings.STATICFILES_DIRS:
            for css in Path(directory).rglob('*.css'):
                if re.search(r"""url\(\s*['"]?/media/""", css.read_text(encoding='utf-8', errors='ignore')):
                    offenders.append(css.relative_to(ROOT).as_posix())
        self.assertEqual(offenders, [])
