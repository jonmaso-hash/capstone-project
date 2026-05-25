# shared_utils/middleware.py
from django.http import JsonResponse
from django.conf import settings

class IdempotencyMiddleware:
    """
    Globally enforces the presence of an Idempotency-Key header for POST requests.
    Excludes health checks and auth endpoints to maintain system usability.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Only enforce on POST requests (or add PUT/PATCH if needed)
        if request.method == "POST":
            
            # 2. Skip middleware for excluded paths (e.g., login, health-check)
            excluded_paths = getattr(settings, 'IDEMPOTENCY_EXCLUDED_PATHS', [])
            if any(request.path.startswith(path) for path in excluded_paths):
                return self.get_response(request)

            # 3. Enforce Header
            if 'HTTP_IDEMPOTENCY_KEY' not in request.META:
                return JsonResponse({
                    "error": "Idempotency-Key header is missing.",
                    "code": "missing_idempotency_key",
                    "message": "All POST requests must include a unique Idempotency-Key header."
                }, status=400)

        return self.get_response(request)