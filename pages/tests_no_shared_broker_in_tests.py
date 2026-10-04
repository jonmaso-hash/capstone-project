"""
No test publishes to a real Celery queue.

The local `.env` points CELERY_BROKER_URL at a shared cloud Redis, and focused
test runs leave CELERY_TASK_ALWAYS_EAGER off. Every `.delay()` a test
triggered went to that queue and stayed there: 213 tasks by 2026-10-04, which
a local worker then ran -- real model calls, a real memo overwritten. The gate
never saw it because the gate script exports memory:// itself, so these tests
set a remote broker THEMSELVES rather than relying on the environment they
happen to run in. That is what lets them fail in CI.

Every negative is paired with a positive control, as in
tests_no_network_in_tests: a refusal that also broke task publishing would
pass "nothing reaches the queue" while taking every .delay() down with it.
"""
import os
from unittest import mock

from django.test import SimpleTestCase

from config.celery import app
from config.test_runner import (
    IN_MEMORY_BROKER, SharedBrokerInTests, isolate_celery, verify_celery_isolated)

REMOTE = 'redis://default:not-a-real-password@broker.invalid:6379/0'
REMOTE_ENV = {'CELERY_BROKER_URL': REMOTE, 'CELERY_RESULT_BACKEND': REMOTE,
              'CELERY_BROKER_WRITE_URL': REMOTE}


def point_celery_at_remote():
    """What a focused run looked like before the runner isolated it: env, config, backend and publish pool all remote."""
    app.conf.broker_url = REMOTE
    app.conf.result_backend = REMOTE
    app._backend_cache = None
    if hasattr(app._local, 'backend'):
        del app._local.backend
    app._pool = None
    if 'amqp' in app.__dict__:
        app.amqp._producer_pool = None
    app.backend                      # cache a remote backend, as an earlier import may have
    app.amqp.producer_pool           # and a remote publish pool, which is what .delay() uses


class TheRunnerIsolatedThisRunTests(SimpleTestCase):
    """Positive control on the real runner: this very test process is on the in-memory broker."""

    def test_the_live_connection_is_in_memory(self):
        with app.connection_for_write() as connection:
            self.assertTrue(connection.as_uri().startswith('memory://'), connection.as_uri())

    def test_the_live_result_backend_is_in_memory(self):
        self.assertEqual(type(app.backend).__name__, 'CacheBackend')

    def test_the_publish_pool_is_in_memory(self):
        self.assertTrue(app.amqp.producer_pool.connections.connection.as_uri().startswith('memory://'))

    def test_a_task_can_still_be_published(self):
        # The refusal must not take publishing down with it.
        self.assertTrue(app.send_task('pages.tests.no_such_task', args=[1]).id)


class IsolationOverridesARemoteBrokerTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(isolate_celery)          # leave the rest of the run on memory

    def test_isolation_wins_over_the_environment_and_a_cached_backend(self):
        with mock.patch.dict(os.environ, REMOTE_ENV):
            point_celery_at_remote()
            self.assertEqual(type(app.backend).__name__, 'RedisBackend')   # the setup really was remote
            isolate_celery()
            with app.connection_for_write() as connection:
                self.assertTrue(connection.as_uri().startswith('memory://'))
            self.assertEqual(type(app.backend).__name__, 'CacheBackend')
            self.assertTrue(app.amqp.producer_pool.connections.connection.as_uri().startswith('memory://'))
            self.assertEqual(os.environ['CELERY_BROKER_URL'], IN_MEMORY_BROKER)
            self.assertNotIn('CELERY_BROKER_WRITE_URL', os.environ)

    def test_setting_the_config_alone_would_not_have_worked(self):
        # Why isolate_celery sets the environment: Celery reads
        # CELERY_BROKER_URL from os.environ before its own config.
        with mock.patch.dict(os.environ, REMOTE_ENV):
            app.conf.broker_url = IN_MEMORY_BROKER
            self.assertIn('broker.invalid', app.conf.broker_url)


class VerificationRefusesARemoteBrokerTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(isolate_celery)

    def test_a_remote_broker_is_refused(self):
        with mock.patch.dict(os.environ, REMOTE_ENV):
            point_celery_at_remote()
            with self.assertRaises(SharedBrokerInTests) as caught:
                verify_celery_isolated(app)
        message = str(caught.exception)
        self.assertIn('broker.invalid', message)
        self.assertNotIn('not-a-real-password', message)    # a broker URI can carry a password

    def test_a_stale_publish_pool_is_refused_even_when_a_fresh_connection_is_in_memory(self):
        # The case a settings-only check misses: everything a fresh connection
        # reports is memory, but .delay() would still publish through the old pool.
        with mock.patch.dict(os.environ, REMOTE_ENV):
            point_celery_at_remote()
        with mock.patch.dict(os.environ, {'CELERY_BROKER_URL': IN_MEMORY_BROKER,
                                          'CELERY_RESULT_BACKEND': 'cache+memory://'}):
            app.conf.broker_url = IN_MEMORY_BROKER
            app.conf.result_backend = 'cache+memory://'
            app._backend_cache = None
            if hasattr(app._local, 'backend'):
                del app._local.backend
            with app.connection_for_write() as connection:
                self.assertTrue(connection.as_uri().startswith('memory://'))     # the fresh view looks fine
            with self.assertRaises(SharedBrokerInTests) as caught:
                verify_celery_isolated(app)
        self.assertIn('publish pool: redis://broker.invalid', str(caught.exception))

    def test_the_refusal_cannot_be_swallowed_by_except_exception(self):
        self.assertFalse(issubclass(SharedBrokerInTests, Exception))

    def test_the_isolated_state_passes_verification(self):
        isolate_celery()
        verify_celery_isolated(app)      # positive control: no raise
