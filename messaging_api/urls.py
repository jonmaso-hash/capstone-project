# messaging_api/urls.py
from django.urls import path
from .views import ThreadHistoryAPIView, DispatchMessageAPIView

app_name = 'messaging_api'

urlpatterns = [
    path('threads/<int:thread_id>/messages/', ThreadHistoryAPIView.as_view(), name='thread_messages'),
    path('send/', DispatchMessageAPIView.as_view(), name='send_message'),
]