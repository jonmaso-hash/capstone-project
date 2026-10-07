import json

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from usersettings.models import UserSettings
from .history import visible_notifications, apply_retention
from django.utils import timezone

from .models import Notification

HISTORY_PAGE_SIZE = 50


def _visible_notifications(user):
    return visible_notifications(user)


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
    try:
        limit = int(request.GET.get('limit', HISTORY_PAGE_SIZE))
        if not 1 <= limit <= HISTORY_PAGE_SIZE:
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid history limit'}, status=400)
    data = [{
        'id': item.id,
        'message': item.message,
        'target_url': item.target_url,
        'is_read': item.is_read,
        'created_at': item.created_at.isoformat(),
        'can_dismiss': item.can_dismiss,
    } for item in notifications[:limit]]
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
    apply_retention(request.user)
    count = _visible_notifications(request.user).filter(is_read=False).count()
    return JsonResponse({'updated': updated, 'count': count})


def notification_delete_api(request, notification_id):
    """Legacy route: close a notice without destroying its record."""
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
    _visible_notifications(request.user).filter(id=item.id).update(dismissed_at=timezone.now(), is_read=True)
    return JsonResponse({'dismissed': True, 'count': _visible_notifications(request.user).filter(is_read=False).count()})


@login_required
def notification_history(request):
    page = Paginator(_visible_notifications(request.user).order_by('-id'), 25).get_page(request.GET.get('page'))
    return render(request, 'notifications/history.html', {'notification_page': page})


@login_required
@require_POST
def notification_close(request, notification_id):
    result = notification_delete_api(request, notification_id)
    if result.status_code != 200:
        return result
    page = request.POST.get('page', '1')
    from django.urls import reverse
    from urllib.parse import urlencode
    return redirect(reverse('notification-history') + '?' + urlencode({'page': page}))


@login_required
@require_POST
def notification_settings(request):
    from ops.impersonation import is_impersonating
    if is_impersonating():
        return JsonResponse({'error': 'Read-only while viewing as another user'}, status=403)
    try:
        days = int(request.POST.get('retention_days', ''))
        if days not in dict(UserSettings.NOTIFICATION_RETENTION_CHOICES):
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Choose a valid notification history setting'}, status=400)
    preferences = UserSettings.for_user(request.user)
    preferences.notification_retention_days = days
    preferences.save(update_fields=['notification_retention_days', 'updated_at'])
    apply_retention(request.user)
    return redirect('usersettings:home')
