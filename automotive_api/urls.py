# automotive_api/urls.py
from django.urls import path
from .views import InventoryCatalogAPIView, RequestTestDriveAPIView

app_name = 'automotive_api'

urlpatterns = [
    # Inventory search routes
    path('inventory/', InventoryCatalogAPIView.as_view(), name='inventory_catalog'),
    
    # Booking schedule entry point
    path('drive/schedule/', RequestTestDriveAPIView.as_view(), name='schedule_drive'),
]