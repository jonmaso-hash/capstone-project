#!/bin/sh
set -e

# collectstatic needs a real SECRET_KEY (and other env-backed settings) to
# even import settings.py, which aren't available at `docker build` time —
# secrets are injected at container runtime instead, so this runs here.
# Safe to run on every container start: it's idempotent.
python manage.py collectstatic --noinput

# The live Render service is not currently managed by render.yaml, so its
# preDeployCommand is not applied. Allow exactly one service (the web
# service) to opt into migrations explicitly via RUN_MIGRATIONS=1.
# The worker leaves this unset, preventing concurrent migration races.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    python manage.py migrate --noinput
fi

exec "$@"
