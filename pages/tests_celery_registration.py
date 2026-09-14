"""
A Celery worker registers every task the app queues.

A worker only knows a task if its module was imported at startup; autodiscovery
imports each app's `tasks` module and nothing else. Entity Integrity's task lives
in zelda_api/entity_verification_tasks.py, which nothing imported until a request
queued it -- so the worker discarded every Entity Integrity job as an unregistered
task and no report was ever produced.

This has to be checked the way a worker starts: in a fresh interpreter, with
django.setup() and the Celery app's own module loading, and without the URL
configuration. Inside the test runner, loading the URLs imports these modules
first and would hide exactly this bug.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)

_WORKER_STARTUP_PROBE = (
    "import json, os, sys; sys.path.insert(0, os.getcwd()); "
    "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); "
    "import django; django.setup(); "
    "from config.celery import app; app.loader.import_default_modules(); "
    "print('TASKS_JSON=' + json.dumps(sorted(app.tasks)))"
)

# Every task the app queues with .delay() from a module other than an app's
# tasks.py -- the ones autodiscovery cannot find on its own.
MUST_BE_REGISTERED = (
    'zelda_api.entity_verification_tasks.verify_entity_integrity',
    'zelda_api.truth_delta_tasks.verify_document_truth_delta',
    'zelda_api.truth_delta_tasks.extract_claims_from_insights',
)


class WorkerTaskRegistrationTests(SimpleTestCase):

    def test_a_freshly_started_worker_registers_every_task_the_app_queues(self):
        env = dict(os.environ)
        env.setdefault('SECRET_KEY', 'test-only-celery-registration-probe')
        result = subprocess.run([sys.executable, '-c', _WORKER_STARTUP_PROBE], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=300)
        line = next((l for l in result.stdout.splitlines() if l.startswith('TASKS_JSON=')), None)
        self.assertIsNotNone(line, result.stderr[-3000:])
        registered = set(json.loads(line[len('TASKS_JSON='):]))
        self.assertEqual([task for task in MUST_BE_REGISTERED if task not in registered], [])
