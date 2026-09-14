"""
Bounded request timeouts.

Gunicorn ran with its 30-second default timeout, and every Anthropic client took
the SDK's 10-minute timeout with 2 retries. Ask Zelda calls Claude inside the
web request, so a slow reply got the worker killed and the user a 502.

These pin the fix: gunicorn's settings come from the environment with safe
defaults, each Anthropic client has an explicit ceiling, the web-request ceiling
is shorter than background work and fits inside gunicorn's, and every call site
uses the profile that matches where it runs.

They read source files rather than importing zelda_api's pipeline modules, which
load sentence-transformers -- this module runs in the blocking CI job.
"""
import os
import re
import runpy
import sys
import threading
import time
import types
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)
GUNICORN_VARS = (
    'PORT', 'WEB_CONCURRENCY', 'GUNICORN_TIMEOUT', 'GUNICORN_GRACEFUL_TIMEOUT', 'GUNICORN_KEEPALIVE',
    'GUNICORN_THREADS',
)

# Headroom a web request needs beyond the Claude call itself: the database
# search that follows extraction, serialization, and the proxy hop.
WEB_REQUEST_HEADROOM_SECONDS = 10


def _gunicorn_config(**overrides):
    env = {k: v for k, v in os.environ.items() if k not in GUNICORN_VARS}
    env.update(overrides)
    with mock.patch.dict(os.environ, env, clear=True):
        return runpy.run_path(str(ROOT / 'gunicorn.conf.py'))


class GunicornConfigTests(SimpleTestCase):

    def test_defaults(self):
        config = _gunicorn_config()
        self.assertEqual(config['timeout'], 60)
        self.assertEqual(config['workers'], 3)
        self.assertEqual(config['graceful_timeout'], 30)
        self.assertEqual(config['keepalive'], 5)
        self.assertEqual(config['bind'], '0.0.0.0:8000')

    def test_workers_are_threaded_so_one_slow_upload_does_not_hold_a_whole_worker(self):
        config = _gunicorn_config()
        self.assertEqual(config['worker_class'], 'gthread')
        self.assertEqual(config['threads'], 4)

    def test_the_environment_overrides_every_value(self):
        config = _gunicorn_config(
            PORT='10000', WEB_CONCURRENCY='2', GUNICORN_TIMEOUT='90',
            GUNICORN_GRACEFUL_TIMEOUT='20', GUNICORN_KEEPALIVE='2', GUNICORN_THREADS='8',
        )
        self.assertEqual(config['bind'], '0.0.0.0:10000')
        self.assertEqual(config['workers'], 2)
        self.assertEqual(config['timeout'], 90)
        self.assertEqual(config['graceful_timeout'], 20)
        self.assertEqual(config['keepalive'], 2)
        self.assertEqual(config['threads'], 8)

    def test_a_blank_value_falls_back_to_the_default(self):
        self.assertEqual(_gunicorn_config(GUNICORN_TIMEOUT='  ')['timeout'], 60)

    def test_the_image_runs_gunicorn_with_this_config_and_no_overriding_flags(self):
        """Command-line flags beat the config file, so a leftover one would silently win."""
        cmd = next(line for line in (ROOT / 'Dockerfile').read_text(encoding='utf-8').splitlines()
                   if line.startswith('CMD'))
        self.assertIn('gunicorn.conf.py', cmd)
        for flag in ('--timeout', '--workers', '--bind', '-w', '-t', '-b'):
            self.assertNotIn(f'"{flag}"', cmd)


class EmbeddingModelThreadSafetyTests(SimpleTestCase):
    """
    Threaded workers share one embedding model per process. Without a lock, the
    first requests to reach a fresh worker at the same moment would each load a
    copy, and on a 2 GB instance that is enough to run out of memory.
    """

    def test_threads_that_ask_for_the_model_at_once_load_it_once(self):
        from matchmaking.services import ai_utils

        loads, models = [], []

        def slow_model(name):
            loads.append(name)
            time.sleep(0.2)
            return object()

        barrier = threading.Barrier(4)

        def request():
            barrier.wait()
            models.append(ai_utils._get_model())

        fake = types.SimpleNamespace(SentenceTransformer=slow_model)
        with mock.patch.dict(sys.modules, {'sentence_transformers': fake}), mock.patch.object(ai_utils, '_model', None):
            threads = [threading.Thread(target=request) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(len(loads), 1)
        self.assertEqual(len({id(model) for model in models}), 1)


class AnthropicClientTimeoutTests(SimpleTestCase):

    def test_defaults(self):
        self.assertEqual(settings.ANTHROPIC_WEB_REQUEST_TIMEOUT_SECONDS, 25.0)
        self.assertEqual(settings.ANTHROPIC_WEB_REQUEST_MAX_RETRIES, 0)
        self.assertEqual(settings.ANTHROPIC_BACKGROUND_TIMEOUT_SECONDS, 120.0)
        self.assertEqual(settings.ANTHROPIC_BACKGROUND_MAX_RETRIES, 2)

    def test_the_web_request_client_is_short_and_does_not_retry(self):
        from zelda_api.anthropic_client import web_request_anthropic_client
        client = web_request_anthropic_client(api_key='sk-ant-test')
        self.assertEqual(client.timeout, settings.ANTHROPIC_WEB_REQUEST_TIMEOUT_SECONDS)
        self.assertEqual(client.max_retries, 0)

    def test_the_background_client_waits_longer_and_retries(self):
        from zelda_api.anthropic_client import background_anthropic_client
        client = background_anthropic_client(api_key='sk-ant-test')
        self.assertEqual(client.timeout, settings.ANTHROPIC_BACKGROUND_TIMEOUT_SECONDS)
        self.assertEqual(client.max_retries, settings.ANTHROPIC_BACKGROUND_MAX_RETRIES)
        self.assertGreater(client.timeout, settings.ANTHROPIC_WEB_REQUEST_TIMEOUT_SECONDS)

    def test_the_clients_follow_settings_overrides(self):
        from zelda_api.anthropic_client import background_anthropic_client, web_request_anthropic_client
        with self.settings(ANTHROPIC_WEB_REQUEST_TIMEOUT_SECONDS=5.0, ANTHROPIC_BACKGROUND_MAX_RETRIES=1):
            self.assertEqual(web_request_anthropic_client(api_key='sk-ant-test').timeout, 5.0)
            self.assertEqual(background_anthropic_client(api_key='sk-ant-test').max_retries, 1)

    def test_a_synchronous_claude_call_finishes_inside_the_gunicorn_worker_timeout(self):
        """
        The failure this prevents: the SDK still waiting while gunicorn kills the
        worker. Each retry repeats the whole wait, so the worst case is
        timeout x (retries + 1), plus headroom for the rest of the request.
        """
        worst_case = settings.ANTHROPIC_WEB_REQUEST_TIMEOUT_SECONDS * (settings.ANTHROPIC_WEB_REQUEST_MAX_RETRIES + 1)
        self.assertLessEqual(worst_case + WEB_REQUEST_HEADROOM_SECONDS, _gunicorn_config()['timeout'])


def _function_body(source, name):
    lines = source.splitlines()
    start = next(i for i, line in enumerate(lines) if re.match(rf'\s*def {re.escape(name)}\(', line))
    indent = len(lines[start]) - len(lines[start].lstrip())
    body = [lines[start]]
    for line in lines[start + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        body.append(line)
    return '\n'.join(body)


class AnthropicCallSiteTests(SimpleTestCase):
    """Which profile each site uses is decided by where it runs, not by preference."""

    CALL_SITES = [
        # (file, function, profile) -- query extraction runs inside ZeldaAskAPIView's
        # request; the rest run in Celery tasks.
        ('zelda_api/intelligence_pipeline.py', '_call_claude_for_query_extraction', 'web_request_anthropic_client'),
        ('zelda_api/intelligence_pipeline.py', '_call_claude_for_memo', 'background_anthropic_client'),
        ('zelda_api/intelligence_pipeline.py', '_call_claude_for_valuation', 'background_anthropic_client'),
        ('zelda_api/truth_delta_engine.py', '_call_claude_for_verification', 'background_anthropic_client'),
        ('zelda_api/embeddings.py', '__init__', 'background_anthropic_client'),
    ]
    PROFILES = ('web_request_anthropic_client', 'background_anthropic_client')

    def test_each_call_site_uses_the_profile_for_where_it_runs(self):
        for path, function, profile in self.CALL_SITES:
            with self.subTest(site=f'{path}::{function}'):
                body = _function_body((ROOT / path).read_text(encoding='utf-8'), function)
                self.assertIn(f'{profile}(', body)
                other = next(p for p in self.PROFILES if p != profile)
                self.assertNotIn(f'{other}(', body)

    def test_no_anthropic_client_is_built_without_an_explicit_timeout(self):
        """A new bare Anthropic(...) would quietly bring back the 10-minute default."""
        offenders = []
        for app in ('accounts', 'billing', 'blog', 'config', 'growth', 'jobs', 'matchmaking',
                    'notifications', 'ops', 'pages', 'sharing', 'usersettings', 'zelda_api'):
            for path in (ROOT / app).rglob('*.py'):
                relative = path.relative_to(ROOT).as_posix()
                if relative == 'zelda_api/anthropic_client.py' or '/migrations/' in relative or path.name.startswith('test'):
                    continue
                if re.search(r'\bAnthropic\(', path.read_text(encoding='utf-8', errors='ignore')):
                    offenders.append(relative)
        self.assertEqual(offenders, [])


class IdempotencyExclusionTests(SimpleTestCase):

    def test_the_stale_health_path_is_gone(self):
        """/api/v1/health/ never had a route; the real check is /api/v1/zelda/health/."""
        self.assertNotIn('/api/v1/health/', settings.IDEMPOTENCY_EXCLUDED_PATHS)
