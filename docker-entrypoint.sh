#!/bin/sh
set -e

# collectstatic needs a real SECRET_KEY (and other env-backed settings) to
# even import settings.py, which aren't available at `docker build` time —
# secrets are injected at container runtime instead, so this runs here.
# Safe to run on every container start: it's idempotent.
python manage.py collectstatic --noinput

# Deliberately NOT running `manage.py migrate` here. Auto-migrating on every
# container boot is fine for a single instance but races when multiple
# instances start at once — run migrations as an explicit, separate step
# in your deploy process instead (see the production-readiness checklist's
# note on migration strategy: blue-green/canary/rolling).

exec "$@"
