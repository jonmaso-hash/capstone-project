from django.urls import path
from .views import ContractAnalysisAPIView, ConflictCheckAPIView

# Namespacing lets you reverse lookups globally via 'legal_api:contract_analyze'
app_name = 'legal_api'

urlpatterns = [
    # Document Risk & Clause Scraper Endpoint
    path('contracts/analyze/', ContractAnalysisAPIView.as_view(), name='contract_analyze'),
    
    # Semantic Conflict of Interest Checking Endpoint
    path('compliance/conflict-check/', ConflictCheckAPIView.as_view(), name='conflict_check'),
]