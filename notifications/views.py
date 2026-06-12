# notifications/views.py
from django.http import JsonResponse
from .models import Notification  # Ensure this points to the local model

def notification_list_api(request):
    if not request.user.is_authenticated:
        return JsonResponse([], safe=False)
    
    # FIX: Use 'target_url' instead of 'link'
    notifications = request.user.notifications.filter(is_read=False)
    data = list(notifications.values('message', 'target_url'))
    
    notifications.update(is_read=True)
    return JsonResponse(data, safe=False)

def unread_count_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({'count': 0})
        
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'count': count})