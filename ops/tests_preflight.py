"""
`manage.py preflight` reports what a run will really use, and fails closed.

Each refusal is paired with a positive control, because a preflight that
refused everything would pass every "it refuses" test and be switched off by
the first person it blocked.
"""
import os
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from ops.management.commands import preflight

REMOTE = 'redis://default:not-a-real-password@broker.invalid:6379/0'


def run(*args):
    out = StringIO()
    call_command('preflight', *args, stdout=out)
    return out.getvalue()


class PreflightPassesWhenEverythingIsLocalAndCurrentTests(TestCase):
    """Positive control: the test run itself is on an in-memory broker and a freshly migrated database."""

    def test_local_and_current_passes_with_local_flag(self):
        output = run('--local')
        self.assertIn('0 pending', output)
        self.assertIn('preflight ok', output)
        self.assertNotIn('REMOTE', output)


class PreflightRefusesPendingMigrationsTests(TestCase):

    def test_pending_migrations_fail_and_are_named(self):
        with mock.patch.object(preflight, 'pending_migrations', return_value=['zelda_api.0099_example']):
            with self.assertRaises(CommandError) as caught:
                run()
        self.assertIn('1 unapplied migration', str(caught.exception))

    def test_pending_migrations_fail_even_without_local_flag(self):
        with mock.patch.object(preflight, 'pending_migrations', return_value=['a.0001', 'b.0002']):
            with self.assertRaises(CommandError):
                run()

    def test_the_real_check_reads_the_database(self):
        # Not mocked: the test database is fully migrated, so the real plan is empty.
        self.assertEqual(preflight.pending_migrations(), [])


class PreflightRefusesARemoteBrokerWhenAskedForLocalTests(TestCase):

    def test_a_remote_broker_from_the_environment_fails_with_local(self):
        # The environment, not settings: that is where Celery reads it first.
        with mock.patch.dict(os.environ, {'CELERY_BROKER_URL': REMOTE}):
            with self.assertRaises(CommandError) as caught:
                run('--local')
        message = str(caught.exception)
        self.assertIn('broker (write) is remote: redis://broker.invalid', message)
        self.assertNotIn('not-a-real-password', message)

    def test_a_remote_broker_is_reported_not_refused_without_local(self):
        # Production runs on a remote broker; without --local that is information.
        with mock.patch.dict(os.environ, {'CELERY_BROKER_URL': REMOTE}):
            output = run()
        self.assertIn('redis://broker.invalid  (REMOTE)', output)
        self.assertNotIn('not-a-real-password', output)

    def test_a_remote_cache_fails_with_local(self):
        caches = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': REMOTE}}
        with self.settings(CACHES=caches):
            with self.assertRaises(CommandError) as caught:
                run('--local')
        self.assertIn('cache is remote', str(caught.exception))


class PreflightReadsTheLiveResultBackendTests(TestCase):

    def setUp(self):
        from config.test_runner import isolate_celery
        self.addCleanup(isolate_celery)          # leave the rest of the run on memory

    def test_a_cached_remote_backend_cannot_be_hidden_by_a_later_config_change(self):
        from config.celery import app
        with mock.patch.dict(os.environ, {'CELERY_RESULT_BACKEND': REMOTE}):
            app._backend_cache = None
            if hasattr(app._local, 'backend'):
                del app._local.backend
            self.assertEqual(type(app.backend).__name__, 'RedisBackend')       # built and cached
        with mock.patch.dict(os.environ, {'CELERY_RESULT_BACKEND': 'cache+memory://'}):
            app.conf.result_backend = 'cache+memory://'
            self.assertEqual(app.conf.result_backend, 'cache+memory://')         # the config now says memory
            with self.assertRaises(CommandError) as caught:
                run('--local')
        message = str(caught.exception)
        self.assertIn('result backend is remote: redis://broker.invalid', message)
        self.assertNotIn('not-a-real-password', message)


class LocalityRulesTests(TestCase):

    def test_what_counts_as_local(self):
        for uri in ('memory://localhost//', 'cache+memory://', 'redis://localhost:6379/0', 'redis://127.0.0.1:6379/1', preflight.IN_PROCESS, '', 'disabled://'):
            with self.subTest(uri=uri):
                self.assertTrue(preflight.is_local(uri))
        for uri in (REMOTE, 'rediss://default:x@pumped-koi.upstash.io:6379'):
            with self.subTest(uri=uri):
                self.assertFalse(preflight.is_local(uri))
