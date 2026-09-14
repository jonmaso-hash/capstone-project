"""
Gunicorn settings, read from the environment with safe defaults.

The Dockerfile used to hard-code `--workers 3` and pass no `--timeout`, so the
30-second default applied, and nothing could be tuned without a new image.
A worker that exceeds `timeout` is killed and the user gets a 502.

Raising this number is not the fix for slow Claude calls on its own: the
Anthropic client made inside a web request has its own, shorter ceiling
(zelda_api/anthropic_client.py), and a test keeps that ceiling inside this one.

Flags passed on the gunicorn command line override this file, so the image's
CMD passes none of these.
"""
import os


def _int_env(name, default):
    value = os.environ.get(name, '').strip()
    return int(value) if value else default


# Render (and most PaaS hosts) tell the service which port to listen on.
bind = f"0.0.0.0:{_int_env('PORT', 8000)}"

# WEB_CONCURRENCY is the conventional name hosts use for worker count. Each
# worker loads the in-process sentence-transformers model, so memory, not CPU,
# sets the ceiling here; 3 is the previous value, unchanged.
workers = _int_env('WEB_CONCURRENCY', 3)

# Seconds a worker may go without checking in before it is killed and restarted.
# With threaded workers the check-in runs on the worker's own loop, so this
# catches a stuck worker rather than one slow request; the Anthropic client's
# ceiling (zelda_api/anthropic_client.py) is what bounds a slow Claude call.
timeout = _int_env('GUNICORN_TIMEOUT', 60)

# Seconds an in-flight request gets to finish during a restart or deploy.
graceful_timeout = _int_env('GUNICORN_GRACEFUL_TIMEOUT', 30)

# Seconds to hold an idle keep-alive connection from the host's proxy.
keepalive = _int_env('GUNICORN_KEEPALIVE', 5)

# gthread: each worker serves up to GUNICORN_THREADS requests at once, so one
# slow upload or Claude call holds a thread, not the whole worker. Threads share
# the worker's memory, embedding model included; the model's lazy load is locked
# (matchmaking/services/ai_utils.py) so two first requests can't load it twice.
worker_class = 'gthread'
threads = _int_env('GUNICORN_THREADS', 4)
