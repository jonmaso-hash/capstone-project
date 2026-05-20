# marketplace_api/urls.py
from django.urls import path
from .views import ProductCatalogAPIView, ProcessCheckoutAPIView

app_name = 'marketplace_api'

urlpatterns = [
    path('products/', ProductCatalogAPIView.as_view(), name='product_catalog'),
    path('checkout/', ProcessCheckoutAPIView.as_view(), name='process_checkout'),
]