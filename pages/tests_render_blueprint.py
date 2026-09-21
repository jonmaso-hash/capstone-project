"""
The Render Blueprint (render.yaml) describes the production stack.

It can't be deployed for free, so these tests hold it to what the app actually
needs, and prove the two settings that a Render health check depends on:

- web, a Celery worker, exactly one Celery beat, Key Value and Postgres exist;
- the web health check points at the real health endpoint, and migrations run
  as the pre-deploy command;
- every Django service gets DATABASE_URL, the Celery broker, and the shared
  group whose generated SECRET_KEY is the same value everywhere;
- no secret value is committed, and every variable name is one the app reads;
- the worker copies its secrets from the web service instead of re-declaring them;
- Key Value is private and never evicts queued tasks; Postgres matches the
  version docker-compose develops against (pgvector);
- under production settings, Render's health check -- plain HTTP, Host set to the
  onrender.com hostname -- gets 200, not a 400 DisallowedHost or a 301 SSL
  redirect, while other paths still redirect and unknown hosts are refused.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml
from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse

ROOT = Path(settings.BASE_DIR)
BLUEPRINT = ROOT / 'render.yaml'
DJANGO_SERVICES = ('interlink-web', 'interlink-worker', 'interlink-beat')
SECRET_NAME = re.compile(r'SECRET|TOKEN|PASSWORD|DSN|_KEY$|_KEY_ID$')


def _load():
    return yaml.safe_load(BLUEPRINT.read_text(encoding='utf-8'))


def _services(blueprint):
    return {service['name']: service for service in blueprint.get('services', [])}


def _env(service):
    return {item['key']: item for item in service.get('envVars', []) if 'key' in item}


def _groups_linked(service):
    return [item['fromGroup'] for item in service.get('envVars', []) if 'fromGroup' in item]


def _names_the_app_reads():
    """Variable names read by settings.py, gunicorn.conf.py and dj-database-url."""
    names = set()
    for source in ('config/settings.py', 'gunicorn.conf.py'):
        text = (ROOT / source).read_text(encoding='utf-8')
        names |= set(re.findall(r"""env(?:\.[a-z]+)?\(\s*['"]([A-Z0-9_]+)['"]""", text))
        names |= set(re.findall(r"""_int_env\(\s*['"]([A-Z0-9_]+)['"]""", text))
    return names | {'DATABASE_URL'}


class BlueprintShapeTests(SimpleTestCase):

    def setUp(self):
        self.blueprint = _load()
        self.services = _services(self.blueprint)

    def test_the_stack_is_web_worker_one_beat_key_value_and_postgres(self):
        self.assertEqual(self.services['interlink-web']['type'], 'web')
        self.assertEqual(self.services['interlink-worker']['type'], 'worker')
        self.assertEqual(self.services['interlink-beat']['type'], 'worker')
        self.assertEqual(self.services['interlink-keyvalue']['type'], 'keyvalue')
        self.assertEqual([db['name'] for db in self.blueprint['databases']], ['interlink-db'])
        beats = [s for s in self.services.values() if 'beat' in str(s.get('dockerCommand', ''))]
        self.assertEqual(len(beats), 1, 'Celery beat must run exactly once or scheduled tasks run twice')

    def test_every_django_service_builds_from_the_dockerfile(self):
        for name in DJANGO_SERVICES:
            with self.subTest(service=name):
                self.assertEqual(self.services[name]['runtime'], 'docker')
                self.assertEqual(self.services[name]['dockerfilePath'], './Dockerfile')

    def test_the_web_service_uses_the_image_command_and_the_real_health_endpoint(self):
        web = self.services['interlink-web']
        self.assertNotIn('dockerCommand', web, 'web should run the Dockerfile CMD (gunicorn with gunicorn.conf.py)')
        self.assertEqual(web['healthCheckPath'], reverse('zelda_api:health_check'))

    def test_migrations_run_before_each_deploy_goes_live(self):
        self.assertIn('manage.py migrate', self.services['interlink-web']['preDeployCommand'])

    def test_the_worker_and_beat_run_celery(self):
        self.assertIn('celery -A config worker', self.services['interlink-worker']['dockerCommand'])
        self.assertIn('celery -A config beat', self.services['interlink-beat']['dockerCommand'])

    def test_plans_match_the_agreed_sizes(self):
        self.assertEqual(self.services['interlink-web']['plan'], '1c-2g')
        self.assertEqual(self.services['interlink-worker']['plan'], '1c-2g')
        self.assertEqual(self.services['interlink-beat']['plan'], '0.5c-512mb')


class BlueprintWiringTests(SimpleTestCase):

    def setUp(self):
        self.blueprint = _load()
        self.services = _services(self.blueprint)
        self.groups = {group['name']: group for group in self.blueprint.get('envVarGroups', [])}

    def test_every_django_service_gets_the_database_broker_and_shared_group(self):
        for name in DJANGO_SERVICES:
            with self.subTest(service=name):
                env = _env(self.services[name])
                self.assertEqual(env['DATABASE_URL']['fromDatabase'], {'name': 'interlink-db', 'property': 'connectionString'})
                for key in ('CELERY_BROKER_URL', 'CELERY_RESULT_BACKEND'):
                    self.assertEqual(env[key]['fromService'],
                                     {'type': 'keyvalue', 'name': 'interlink-keyvalue', 'property': 'connectionString'})
                self.assertIn('interlink-shared', _groups_linked(self.services[name]))

    def test_the_shared_group_generates_one_secret_key_and_turns_debug_off(self):
        env = {item['key']: item for item in self.groups['interlink-shared']['envVars']}
        self.assertIs(env['SECRET_KEY'].get('generateValue'), True)
        self.assertEqual(env['DEBUG']['value'], 'False')
        self.assertEqual(env['LOG_TO_FILE']['value'], 'False')

    def test_no_secret_value_is_committed(self):
        declared = []
        for service in self.services.values():
            declared += list(_env(service).values())
        for group in self.groups.values():
            declared += group['envVars']
        for item in declared:
            if SECRET_NAME.search(item['key']):
                with self.subTest(key=item['key']):
                    self.assertNotIn('value', item)

    def test_every_variable_name_is_one_the_app_actually_reads(self):
        known = _names_the_app_reads()
        declared = set()
        for service in self.services.values():
            declared |= set(_env(service))
        for group in self.groups.values():
            declared |= {item['key'] for item in group['envVars']}
        self.assertEqual(sorted(declared - known), [])

    def test_the_worker_copies_its_secrets_from_the_web_service(self):
        web_env = _env(self.services['interlink-web'])
        for key, item in _env(self.services['interlink-worker']).items():
            if 'fromService' in item and 'envVarKey' in item['fromService']:
                with self.subTest(key=key):
                    self.assertEqual(item['fromService']['name'], 'interlink-web')
                    self.assertIn(item['fromService']['envVarKey'], web_env)
                    self.assertIs(web_env[item['fromService']['envVarKey']].get('sync'), False)

    def test_key_value_is_private_and_never_evicts_queued_tasks(self):
        keyvalue = self.services['interlink-keyvalue']
        self.assertEqual(keyvalue['ipAllowList'], [])
        self.assertEqual(keyvalue['maxmemoryPolicy'], 'noeviction')

    def test_postgres_is_private_and_matches_the_version_developed_against(self):
        database = self.blueprint['databases'][0]
        self.assertEqual(database['ipAllowList'], [])
        compose = (ROOT / 'docker-compose.yml').read_text(encoding='utf-8')
        image = re.search(r'image:\s*pgvector/pgvector:pg(\d+)', compose)
        self.assertIsNotNone(image, 'docker-compose no longer pins a pgvector image')
        self.assertEqual(str(database['postgresMajorVersion']), image.group(1))


_HEALTH_PROBE = r"""
import json, os, sys
sys.path.insert(0, os.getcwd())
import django
django.setup()
from django.test import Client
client = Client(raise_request_exception=False)
host = os.environ['RENDER_EXTERNAL_HOSTNAME']
def status(path, host):
    response = client.get(path, HTTP_HOST=host)
    return [response.status_code, response.get('Location')]
from django.conf import settings
print('PROBE_JSON=' + json.dumps({
    'health': status('/api/v1/zelda/health/', host),
    'login': status('/accounts/login/', host),
    'unknown_host': status('/api/v1/zelda/health/', 'attacker.example'),
    'allowed_hosts': settings.ALLOWED_HOSTS,
    'csrf': settings.CSRF_TRUSTED_ORIGINS,
}))
"""


class RenderHealthCheckUnderProductionSettingsTests(SimpleTestCase):

    def test_render_health_check_reaches_the_app_and_other_paths_still_redirect(self):
        env = dict(os.environ)
        env.update({
            'DJANGO_SETTINGS_MODULE': 'config.settings',
            'SECRET_KEY': 'test-only-render-health-probe',
            'DEBUG': 'False',
            'ALLOWED_HOSTS': '',
            'CSRF_TRUSTED_ORIGINS': '',
            'RENDER_EXTERNAL_HOSTNAME': 'interlink-web.onrender.com',
            'STRIPE_SECRET_KEY': 'sk_test_placeholder',
            'LOG_TO_FILE': 'False',
            # Production settings with no S3 bucket, which
            # config/storage_guard.py refuses by default. This probe is about
            # the health-check route and host/CSRF derivation, not storage.
            'ALLOW_EPHEMERAL_MEDIA': '1',
        })
        env.pop('SECURE_SSL_REDIRECT', None)
        result = subprocess.run([sys.executable, '-c', _HEALTH_PROBE], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=180)
        line = next((l for l in result.stdout.splitlines() if l.startswith('PROBE_JSON=')), None)
        self.assertIsNotNone(line, result.stderr[-3000:])
        probe = json.loads(line[len('PROBE_JSON='):])

        self.assertIn('interlink-web.onrender.com', probe['allowed_hosts'])
        self.assertIn('https://interlink-web.onrender.com', probe['csrf'])
        self.assertEqual(probe['health'][0], 200, probe)
        self.assertEqual(probe['login'][0], 301, probe)
        self.assertTrue((probe['login'][1] or '').startswith('https://interlink-web.onrender.com/'), probe)
        self.assertEqual(probe['unknown_host'][0], 400, probe)
