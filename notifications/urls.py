# notifications/urls.py
from django.urls import path
from . import views


urlpatterns = [
    path('', views.notification_history, name='notification-history'),
    path('settings/', views.notification_settings, name='notification-settings'),
    path('<int:notification_id>/close/', views.notification_close, name='notification-close'),
    path('api/list/', views.notification_list_api, name='api-list'),
    path('api/unread-count/', views.unread_count_api, name='api-unread-count'),
    path('api/read/', views.notification_mark_read_api, name='api-read'),
    path('api/<int:notification_id>/delete/', views.notification_delete_api, name='api-delete'),
]
