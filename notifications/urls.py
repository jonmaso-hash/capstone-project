# notifications/urls.py
from django.urls import path
from . import views


urlpatterns = [
    path('api/list/', views.notification_list_api, name='api-list'),
    path('api/unread-count/', views.unread_count_api, name='api-unread-count'),
    path('api/<int:notification_id>/delete/', views.notification_delete_api, name='api-delete'),
]