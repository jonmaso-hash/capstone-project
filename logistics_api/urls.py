# logistics_api/urls.py
from django.urls import path
from .views import WarehouseStockCatalogAPIView, StageFreightShipmentAPIView

app_name = 'logistics_api'

urlpatterns = [
    path('inventory/', WarehouseStockCatalogAPIView.as_view(), name='stock_catalog'),
    path('freight/stage/', StageFreightShipmentAPIView.as_view(), name='stage_freight'),
]