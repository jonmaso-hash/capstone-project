# zelda_api/urls.py
"""
URL configuration for Zelda AI API endpoints.
Include in your main urls.py with: path('api/v1/zelda/', include('zelda_api.urls'))
"""
from django.urls import path
from . import views

app_name = 'zelda_api'

urlpatterns = [
    # Health & Status
    path('health/', views.ZeldaHealthCheckAPIView.as_view(), name='health_check'),
    
    # Search & Discovery
    path('search/', views.ZeldaGlobalSearchAPIView.as_view(), name='global_search'),
    
    # Document Analysis
    path('pitch-analysis/', views.PitchDeckAnalysisAPIView.as_view(), name='pitch_analysis'),
    
    # Founder Intelligence
    path('founder/match-radar/', views.FounderMatchRadarAPIView.as_view(), name='founder_match_radar'),
    
    # Intelligence & Memos
    path('intelligence-memo/', views.IntelligenceMemoAPIView.as_view(), name='intelligence_memo'),
    
    # Text Analysis
    path('summarize/', views.SummarizePageAPIView.as_view(), name='summarize'),
]