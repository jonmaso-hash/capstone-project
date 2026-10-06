from pathlib import Path
from django.test import SimpleTestCase


class DockerEntrypointMigrationGuardTests(SimpleTestCase):
    def test_runtime_migrations_are_explicitly_opt_in(self):
        entrypoint = Path('docker-entrypoint.sh').read_text()
        self.assertIn('RUN_MIGRATIONS', entrypoint)
        self.assertIn('python manage.py migrate --noinput', entrypoint)
        self.assertIn('if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then', entrypoint)
