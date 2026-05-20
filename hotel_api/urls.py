from django.urls import path
from .views import PropertyExplorerAPIView, ExecuteRoomBookingAPIView

app_name = 'hotel_api'

urlpatterns = [
    path('properties/', PropertyExplorerAPIView.as_view(), name='property_catalog'),
    path('reserve/', ExecuteRoomBookingAPIView.as_view(), name='execute_reservation'),
]