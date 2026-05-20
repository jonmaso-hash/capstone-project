# marketing_api/urls.py
from django.urls import path
from .views import LeadICPScoringAPIView, CompetitorAuditorAPIView

# Namespacing allows you to reverse lookups via 'marketing_api:icp_score'
app_name = 'marketing_api'

urlpatterns = [
    # ICP Semantic Lead Scorer Endpoint
    path('icp/score/', LeadICPScoringAPIView.as_view(), name='icp_score'),
    
    # Competitor Scraper & Landscape Auditor Endpoint
    path('crawl/audit/', CompetitorAuditorAPIView.as_view(), name='competitor_audit'),
]