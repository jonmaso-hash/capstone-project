# C:\Users\jonathan\Desktop\KCV\shared_utils\middleware.py
from django.http import JsonResponse
from django.conf import settings

class IdempotencyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST":
            # 1. Bypass check on structural system exclusions
            excluded_paths = getattr(settings, 'IDEMPOTENCY_EXCLUDED_PATHS', [])
            if any(request.path.startswith(path) for path in excluded_paths):
                return self.get_response(request)

            # 2. Extract key from body field payload first, falling back to headers
            idempotency_key = (
                request.POST.get("idempotency_payload_key") or
                request.META.get("HTTP_X_IDEMPOTENCY_KEY") or 
                request.META.get("HTTP_IDEMPOTENCY_KEY") or
                request.headers.get("Idempotency-Key")
            )
            
            print("IDEMPOTENCY KEY FOUND IN PIPELINE:", idempotency_key)

            # 3. Deny if no key sequence exists
            if not idempotency_key:
                return JsonResponse({
                    "error": "Idempotency-Key header is missing.",
                    "code": "missing_idempotency_key",
                    "message": "All POST requests must include a unique Idempotency-Key header."
                }, status=400)

        return self.get_response(request)