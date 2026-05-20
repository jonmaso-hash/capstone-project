from django.urls import path
from .views import GridAssetRegistryAPIView, GridTelemetryIngestAPIView


urlpatterns = [
    # Asset Inventory endpoints
    path('assets/', GridAssetRegistryAPIView.as_view(), name='asset_registry'),
    
    # Live sensor data ingestion node pipelines
    path('telemetry/submit/', GridTelemetryIngestAPIView.as_view(), name='telemetry_submit'),
]