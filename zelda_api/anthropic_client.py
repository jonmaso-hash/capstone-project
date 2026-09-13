"""
Anthropic clients with explicit, bounded timeouts.

Every client used to be built as anthropic.Anthropic(api_key=...), which takes
the SDK defaults: a 10-minute timeout and 2 retries. Background work can live
with a long wait, but Ask Zelda calls Claude inside the web request
(ZeldaAskAPIView -> _call_claude_for_query_extraction), where gunicorn's worker
timeout is the real ceiling. A slow reply got the worker killed and the user a
502, however long the SDK was prepared to wait.

So there are two profiles, each with its own ceiling:

- web request: someone is waiting on the response. Short, and no retries --
  every retry repeats the whole wait. Its worst case, timeout x (retries + 1),
  has to finish well inside GUNICORN_TIMEOUT (gunicorn.conf.py); a test pins it.
- background: Celery work -- memo, valuation, Truth Delta verification. Longer,
  with retries, because nobody is holding a connection open.

The values live in settings and can be overridden from the environment, so a
provider slowdown can be answered with configuration rather than a deploy.
"""
import anthropic
from django.conf import settings


def _client(timeout, max_retries, api_key):
    return anthropic.Anthropic(
        api_key=settings.ANTHROPIC_API_KEY if api_key is None else api_key,
        timeout=timeout,
        max_retries=max_retries,
    )


def web_request_anthropic_client(api_key=None):
    """For a Claude call made while a user's HTTP request is open."""
    return _client(
        settings.ANTHROPIC_WEB_REQUEST_TIMEOUT_SECONDS, settings.ANTHROPIC_WEB_REQUEST_MAX_RETRIES, api_key)


def background_anthropic_client(api_key=None):
    """For a Claude call made from a Celery task."""
    return _client(
        settings.ANTHROPIC_BACKGROUND_TIMEOUT_SECONDS, settings.ANTHROPIC_BACKGROUND_MAX_RETRIES, api_key)
