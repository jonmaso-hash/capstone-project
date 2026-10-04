"""
manage.py preflight [--local]

What a run is about to touch, read from the live objects, before it touches
anything. Run it before starting a local worker or server for a controlled run.

Two failures this exists because of, both from the Nike rerun (2026-10-04):

- THE BROKER. The local `.env` points Celery and the cache at a SHARED cloud
  Redis. A local worker started from it drained 213 tasks left there by test
  runs -- real model calls and a real memo overwritten -- while the
  experiment's own task sat stranded behind them. The protocol said "local
  Redis", and a local Redis process was even running; nothing used it.
- THE SCHEMA. The local database was six migrations behind the code. The gate
  could not see it, because tests build a fresh database. The run's
  verification failed on a missing column, and the document still reached
  `analyzed`.

So this prints the broker, result backend and cache Celery and Django will
ACTUALLY use (scheme and host only; a broker URI can carry a password), and
the unapplied migrations. Pending migrations always fail. With --local, any
broker, result backend or cache that is not on this machine also fails.

Celery's settings read CELERY_BROKER_URL from the environment before their
own config, so the broker is read from the app's connection, never from
settings.CELERY_BROKER_URL. The result backend is read from the live backend
object for the same reason: it is cached once built. A check that read the setting would agree with a
value the worker does not use.

Without --local a remote broker is reported, not refused: production runs on
one, and this command is also useful there.
"""
from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.executor import MigrationExecutor

LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1'}
IN_PROCESS = 'in-process'


def redacted(uri):
    """Scheme and host only."""
    if uri == IN_PROCESS:
        return uri
    parts = urlsplit(uri or '')
    return '%s://%s' % (parts.scheme, parts.hostname or '')


def is_local(uri):
    # Nothing configured (no result backend) sends nothing anywhere.
    if uri in (IN_PROCESS, ''):
        return True
    parts = urlsplit(uri or '')
    if parts.scheme == 'disabled':           # Celery's DisabledBackend: results are not stored
        return True
    return 'memory' in parts.scheme or (parts.hostname or '') in LOCAL_HOSTS


def effective_targets():
    """(name, uri) for everything a run would send work or state to."""
    from config.celery import app

    with app.connection_for_write() as connection:
        write = connection.as_uri()
    with app.connection_for_read() as connection:
        read = connection.as_uri()
    cache = settings.CACHES['default']
    cache_uri = cache.get('LOCATION') if 'redis' in cache['BACKEND'].lower() else IN_PROCESS
    return [
        ('broker (write)', write),
        ('broker (read)', read),
        # The live backend object, not app.conf.result_backend: Celery caches
        # the backend once built, so the config can read memory while results
        # still go to the old store (measured). as_uri() masks the password;
        # redacted() then keeps only scheme and host.
        ('result backend', app.backend.as_uri() or ''),
        ('cache', cache_uri or ''),
    ]


def pending_migrations(alias=DEFAULT_DB_ALIAS):
    executor = MigrationExecutor(connections[alias])
    return [str(migration) for migration, _ in executor.migration_plan(executor.loader.graph.leaf_nodes())]


class Command(BaseCommand):
    help = 'Report the broker, result backend, cache and unapplied migrations a run would use; fail on pending migrations, and with --local on anything remote.'

    def add_arguments(self, parser):
        parser.add_argument('--local', action='store_true',
                            help='Also fail unless the broker, result backend and cache are on this machine.')

    def handle(self, *args, **options):
        problems = []
        for name, uri in effective_targets():
            local = is_local(uri)
            self.stdout.write('%-15s %s%s' % (name, redacted(uri), '' if local else '  (REMOTE)'))
            if options['local'] and not local:
                problems.append('%s is remote: %s' % (name, redacted(uri)))

        pending = pending_migrations()
        self.stdout.write('%-15s %d pending%s' % ('migrations', len(pending), (': ' + ', '.join(pending)) if pending else ''))
        if pending:
            problems.append('%d unapplied migration(s); run `manage.py migrate` first' % len(pending))

        if problems:
            raise CommandError('Preflight failed:\n  ' + '\n  '.join(problems))
        self.stdout.write('preflight ok')
