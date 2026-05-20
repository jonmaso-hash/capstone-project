from django.urls import path
from .views import AccountBalanceAPIView, TransferFundsAPIView

app_name = 'banking_api'

urlpatterns = [
    # Get all active ledger pools
    path('accounts/', AccountBalanceAPIView.as_view(), name='account_balances'),
    
    # Post atomic peer-to-peer ledger updates
    path('ledger/transfer/', TransferFundsAPIView.as_view(), name='ledger_transfer'),
]