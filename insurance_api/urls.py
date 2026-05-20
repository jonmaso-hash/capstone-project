# insurance_api/urls.py
from django.urls import path
from .views import UserPoliciesAPIView, SubmitClaimAPIView

app_name = 'insurance_api'

urlpatterns = [
    # Active policy inquiries
    path('policies/', UserPoliciesAPIView.as_view(), name='user_policies'),
    
    # Claim ingestion submission routes
    path('claims/lodge/', SubmitClaimAPIView.as_view(), name='lodge_claim'),
]