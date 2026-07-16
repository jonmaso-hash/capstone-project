import json
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse

class IdempotencyMiddleware:
    """
    Intercepts mutating HTTP requests, checks for a unique client-supplied 
    idempotency key across headers and body payloads, and returns cached data 
    on duplicates to guarantee execution safety.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Skip safe read-only operations (Process mutations: POST, PUT, PATCH, DELETE)
        if request.method not in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return self.get_response(request)

        # 2. Bypass check on structural system exclusions
        excluded_paths = getattr(settings, 'IDEMPOTENCY_EXCLUDED_PATHS', [])
        if any(request.path.startswith(path) for path in excluded_paths):
            return self.get_response(request)

        # 3. Extract key via comprehensive resolution hierarchy
        # NOTE: X-Requested-With was previously used as a last-resort
        # fallback key, but that header is sent as the literal string
        # "XMLHttpRequest" by virtually every AJAX client — it is not
        # unique per request, so it must never be used as an idempotency
        # key (it made every unkeyed AJAX POST from every user collide on
        # the same cache entry).
        idempotency_key = (
            request.POST.get("idempotency_payload_key") or
            request.META.get("HTTP_X_IDEMPOTENCY_KEY") or
            request.META.get("HTTP_IDEMPOTENCY_KEY") or
            (request.headers.get("Idempotency-Key") if hasattr(request, 'headers') else None)
        )

        # Graceful fallback: If basic actions don't pass a key, process normally
        if not idempotency_key:
            return self.get_response(request)

        # Scope the cache key to the requester's identity. A client-supplied
        # idempotency key is only guaranteed unique per-client — without this,
        # two different users who happen to send the same key (e.g. a shared
        # client library default) would collide on the same cache entry and
        # one user could be served the other's cached response.
        if request.user.is_authenticated:
            requester_id = f"user:{request.user.pk}"
        else:
            session_key = request.session.session_key
            if not session_key:
                # No stable identity to scope to yet — skip idempotency
                # protection rather than bucket every anonymous client
                # without a session together under the same key.
                return self.get_response(request)
            requester_id = f"session:{session_key}"

        cache_key = f"idempotency:{requester_id}:{idempotency_key}"
        cached_data = cache.get(cache_key)

        # 4. Handle identical incoming requests (In-Flight lock or Replay response)
        if cached_data:
            if cached_data == 'processing':
                return JsonResponse(
                    {"error": "A request with this configuration key is already being processed."}, 
                    status=409
                )
            
            # Reconstruct and serve the identical cached response safely
            response = HttpResponse(
                content=cached_data['content'],
                status=cached_data['status_code'],
                content_type=cached_data['content_type']
            )
            response['X-Cache-Lookup'] = 'HIT - Idempotency Protected'
            return response

        # 5. Acquire short-lived execution lock to catch rapid click overlaps
        cache.set(cache_key, 'processing', timeout=60)

        response = self.get_response(request)

        # 6. Persist the response lifecycle metadata
        if 200 <= response.status_code < 500:
            if not getattr(response, 'streaming', False):
                # Safe cross-version check for content-type headers
                content_type = 'application/json'
                if hasattr(response, 'headers'):
                    content_type = response.headers.get('Content-Type', content_type)
                else:
                    content_type = response.get('Content-Type', content_type)

                payload = {
                    'status_code': response.status_code,
                    'content': response.content,
                    'content_type': content_type
                }
                # Keep the resolution signature active for 24 hours
                cache.set(cache_key, payload, timeout=86400)
            else:
                # Free lock if the response cannot be cached explicitly (e.g. file downloads)
                cache.delete(cache_key)
        else:
            # If the backend crashed (5xx), strip the lock so the client can retry immediately
            cache.delete(cache_key)

        return response