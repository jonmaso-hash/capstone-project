import json

from django.http import JsonResponse
from django.utils import timezone

from .models import Notification

HISTORY_PAGE_SIZE = 50


def _visible_notifications(user):
    return Notification.objects.filter(recipient=user, dismissed_at__isnull=True)


def notification_list_api(request):
    """Read-only history, including read items; paginate by oldest returned ID."""
    if not request.user.is_authenticated:
        return JsonResponse([], safe=False)
    notifications = _visible_notifications(request.user).order_by('-id')
    before = request.GET.get('before')
    if before is not None:
        try:
            before = int(before)
            if before <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid history cursor'}, status=400)
        notifications = notifications.filter(id__lt=before)
    data = [{
        'id': item.id,
        'message': item.message,
        'target_url': item.target_url,
        'is_read': item.is_read,
        'created_at': item.created_at.isoformat(),
        'can_dismiss': item.can_dismiss,
    } for item in notifications[:HISTORY_PAGE_SIZE]]
    return JsonResponse(data, safe=False)


def unread_count_api(request):
    count = (_visible_notifications(request.user).filter(is_read=False).count()
             if request.user.is_authenticated else 0)
    return JsonResponse({'count': count})


def notification_mark_read_api(request):
    """Acknowledge only notifications the user has actually displayed."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    from ops.impersonation import is_impersonating
    if is_impersonating():
        return JsonResponse({'error': 'Read-only while viewing as another user'}, status=403)
    try:
        payload = json.loads(request.body)
        ids = payload.get('ids') if isinstance(payload, dict) else None
        if not isinstance(ids, list) or len(ids) > HISTORY_PAGE_SIZE:
            raise ValueError
        if any(type(value) is not int or value <= 0 for value in ids):
            raise ValueError
    except (ValueError, TypeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Provide up to 50 notification IDs'}, status=400)
    updated = _visible_notifications(request.user).filter(id__in=ids, is_read=False).update(is_read=True)
    count = _visible_notifications(request.user).filter(is_read=False).count()
    return JsonResponse({'updated': updated, 'count': count})


def notification_delete_api(request, notification_id):
    """Legacy route: dismiss ordinary notices without destroying their records."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    from ops.impersonation import is_impersonating
    if is_impersonating():
        return JsonResponse({'error': 'Read-only while viewing as another user'}, status=403)
    item = _visible_notifications(request.user).filter(id=notification_id).first()
    if item is None:
        return JsonResponse({'dismissed': False})
    if not item.can_dismiss:
        return JsonResponse({'error': 'This system notice is retained in your history'}, status=403)
    _visible_notifications(request.user).filter(id=item.id).update(dismissed_at=timezone.now(), is_read=True)
    return JsonResponse({'dismissed': True})
