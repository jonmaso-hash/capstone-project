# zelda_api/urls.py
"""
URL configuration for Zelda AI API endpoints.
Include in your main urls.py with: path('api/v1/zelda/', include('zelda_api.urls'))

Endpoints organized by pipeline stage:
- Document Ingestion: /documents/ingest/
- Pipeline Status: /documents/{id}/status/
- Results: /documents/{id}/memo/, /documents/{id}/insights/, etc.
"""
from django.urls import path
from . import views as standard_views      # Alias for original views
from . import pipeline_views
from . import truth_delta_views as td_views # Alias for Truth Delta views

app_name = 'zelda_api'

urlpatterns = [
    # ──────────────────────────────────────────────────────────────────────────
    # HEALTH & SYSTEM
    # ──────────────────────────────────────────────────────────────────────────
    path('health/', standard_views.ZeldaHealthCheckAPIView.as_view(), name='health_check'),
    
    # ... (Keep pipeline_views paths as they are) ...
    
    # ──────────────────────────────────────────────────────────────────────────
    # LEGACY ENDPOINTS (Update these to standard_views)
    # ──────────────────────────────────────────────────────────────────────────
    # Search & Discovery
    path('api/v1/zelda/search/', standard_views.ZeldaGlobalSearchAPIView.as_view(), name='global_search_api'),
    
    # Document Analysis
    path('pitch-analysis/', standard_views.PitchDeckAnalysisAPIView.as_view(), name='pitch_analysis'),
    path('documents/analyze/', standard_views.DocumentIntakeAPIView.as_view(), name='document_intake'),
    
    # Founder Intelligence
    path('founder/match-radar/', standard_views.FounderMatchRadarAPIView.as_view(), name='founder_match_radar'),
    
    # Intelligence & Memos
    path('intelligence-memo/', standard_views.IntelligenceMemoAPIView.as_view(), name='intelligence_memo'),
    
    # Text Analysis
    path('summarize/', standard_views.SummarizePageAPIView.as_view(), name='summarize'),
    
    # Vector matching
    path('match-radar/', standard_views.MatchRadarAPIView.as_view(), name='match_radar'),
    
    # Gateway (universal orchestration)
    path('gateway/<str:source_name>/', standard_views.ZeldaGatewayAPIView.as_view(), name='gateway'),
    
    path('dashboard/intelligence/', standard_views.zelda_intelligence_dashboard, name='intelligence_dashboard'),
    
    path('search/', standard_views.zelda_search_view, name='zelda_search'),
    
    path('ui/search/', standard_views.zelda_search_view, name='zelda_search_ui'),
    # ──────────────────────────────────────────────────────────────────────────
    # Truth Delta EndPoints
    # ──────────────────────────────────────────────────────────────────────────
    path('documents/<int:pk>/truth-delta/',  td_views.TruthDeltaScoreView.as_view(), name='truth-delta-score'),
    path('documents/<int:pk>/truth-delta/analyses/', td_views.TruthDeltaAnalysisView.as_view(), name='truth-delta-analyses'),
    path('documents/<int:pk>/truth-delta/verify/', td_views.TruthDeltaVerifyView.as_view(), name='truth-delta-verify'),
    path('documents/<int:pk>/truth-delta/flags/', td_views.FlaggedClaimsView.as_view(), name='truth-delta-flags'),
    path('documents/<int:pk>/truth-delta/report/', td_views.CredibilityReportView.as_view(), name='truth-delta-report'),
    
    # ──────────────────────────────────────────────────────────────────────────
    # UI FRONTEND PAGES
    # ──────────────────────────────────────────────────────────────────────────
    path('documents/<int:document_id>/verification/', standard_views.truth_delta_ui_view, name='truth_delta_ui'),
]