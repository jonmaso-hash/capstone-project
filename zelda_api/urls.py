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
from . import views
from . import pipeline_views

app_name = 'zelda_api'

urlpatterns = [
    # ──────────────────────────────────────────────────────────────────────────
    # HEALTH & SYSTEM
    # ──────────────────────────────────────────────────────────────────────────
    path('health/', views.ZeldaHealthCheckAPIView.as_view(), name='health_check'),
    
    # ──────────────────────────────────────────────────────────────────────────
    # CENTRAL INTELLIGENCE PIPELINE
    # ──────────────────────────────────────────────────────────────────────────
    # Document ingestion and status polling
    path('documents/ingest/', pipeline_views.DocumentIngestView.as_view(), name='document_ingest'),
    path('documents/<int:document_id>/status/', pipeline_views.DocumentStatusView.as_view(), name='document_status'),
    
    # Pipeline results
    path('documents/<int:document_id>/memo/', pipeline_views.DocumentMemoView.as_view(), name='document_memo'),
    path('documents/<int:document_id>/chunks/', pipeline_views.DocumentChunksView.as_view(), name='document_chunks'),
    path('documents/<int:document_id>/insights/', pipeline_views.DocumentInsightsView.as_view(), name='document_insights'),
    
    # Vector retrieval
    path('documents/<int:document_id>/search/', pipeline_views.DocumentSearchView.as_view(), name='document_search'),
    path('documents/<int:document_id>/rag/', pipeline_views.DocumentRAGView.as_view(), name='document_rag'),
    
    # ──────────────────────────────────────────────────────────────────────────
    # LEGACY ENDPOINTS (BACKWARD COMPATIBILITY)
    # ──────────────────────────────────────────────────────────────────────────
    # Search & Discovery
    path('api/v1/zelda/search/', views.ZeldaGlobalSearchAPIView.as_view(), name='global_search_api'),
    
    # Document Analysis
    path('pitch-analysis/', views.PitchDeckAnalysisAPIView.as_view(), name='pitch_analysis'),
    path('documents/analyze/', views.DocumentIntakeAPIView.as_view(), name='document_intake'),
    
    # Founder Intelligence
    path('founder/match-radar/', views.FounderMatchRadarAPIView.as_view(), name='founder_match_radar'),
    
    # Intelligence & Memos
    path('intelligence-memo/', views.IntelligenceMemoAPIView.as_view(), name='intelligence_memo'),
    
    # Text Analysis
    path('summarize/', views.SummarizePageAPIView.as_view(), name='summarize'),
    
    # Vector matching
    path('match-radar/', views.MatchRadarAPIView.as_view(), name='match_radar'),
    
    # Gateway (universal orchestration)
    path('gateway/<str:source_name>/', views.ZeldaGatewayAPIView.as_view(), name='gateway'),
    
    path('dashboard/intelligence/', views.zelda_intelligence_dashboard, name='intelligence_dashboard'),
    
    path('search/', views.zelda_search_view, name='zelda_search'),
    
    path('ui/search/', views.zelda_search_view, name='zelda_search_ui'),
]