# banking_api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TransactionViewSet, AccountBalanceAPIView, TransferFundsAPIView

app_name = 'banking_api'

# Register the new Pinnacle router
router = DefaultRouter()
router.register(r'transactions', TransactionViewSet, basename='transaction')

urlpatterns = [
    # Legacy paths
    path('accounts/', AccountBalanceAPIView.as_view(), name='account_balances'),
    path('ledger/transfer/', TransferFundsAPIView.as_view(), name='ledger_transfer'),
    
    # New Pinnacle endpoints
    path('', include(router.urls)),
]