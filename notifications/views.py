# notifications/views.py
from django.http import JsonResponse
from django.utils import timezone

from .models import Notification


def notification_list_api(request):
    if not request.user.is_authenticated:
        return JsonResponse([], safe=False)

    # History and read state are separate concerns. A row remains visible after
    # it has been read unless the recipient explicitly dismisses it.
    notifications = request.user.notifications.filter(
        dismissed_at__isnull=True,
    ).order_by('-created_at')[:100]
    rows = list(notifications)
    data = [
        {
            'id': notification.id,
            'message': notification.message,
            'target_url': notification.target_url,
            'notification_type': notification.notification_type,
            'is_read': notification.is_read,
            'created_at': notification.created_at.isoformat(),
            'can_dismiss': not notification.is_retention_protected,
        }
        for notification in rows
    ]

    # Staff viewing as this user see history without changing the user's read
    # state. For the real recipient, opening the list clears unread status but
    # does not remove the history row.
    from ops.impersonation import is_impersonating
    if not is_impersonating():
        request.user.notifications.filter(
            id__in=[notification.id for notification in rows],
            is_read=False,
        ).update(is_read=True)

    return JsonResponse(data, safe=False)


def unread_count_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({'count': 0})

    count = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
        dismissed_at__isnull=True,
    ).count()
    return JsonResponse({'count': count})


def notification_dismiss_api(request, notification_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    notification = Notification.objects.filter(
        id=notification_id,
        recipient=request.user,
        dismissed_at__isnull=True,
    ).first()
    if notification is None:
        return JsonResponse({'dismissed': False})

    if notification.is_retention_protected:
        return JsonResponse(
            {
                'dismissed': False,
                'protected': True,
                'error': 'This system record is retained in notification history.',
            },
            status=403,
        )

    notification.dismissed_at = timezone.now()
    notification.save(update_fields=['dismissed_at'])
    return JsonResponse({'dismissed': True})
