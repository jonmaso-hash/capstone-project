# zelda_api/urls.py
from django.urls import path
from . import views as standard_views
from .truth_delta_views import ContradictionAlertListView
from .pipeline_views import (
    DocumentIngestView,
    DocumentStatusView,
    DocumentMemoView,
    DocumentChunksView,
    DocumentInsightsView,
    DocumentSearchView,
    DocumentRAGView,
)
from .truth_delta_views import (
    TruthDeltaScoreView,
    TruthDeltaAnalysisView,
    TruthDeltaVerifyView,
    FlaggedClaimsView,
    CredibilityReportView,
)

app_name = 'zelda_api'

urlpatterns = [
    # ──────────────────────────────────────────────────────────────────────────
    # PIPELINE & TRUTH DELTA (New Standard)
    # ──────────────────────────────────────────────────────────────────────────
    path('documents/ingest/', DocumentIngestView.as_view(), name='document_ingest'),
    path('documents/<int:document_id>/status/', DocumentStatusView.as_view(), name='document_status'),
    path('documents/<int:document_id>/memo/', DocumentMemoView.as_view(), name='document_memo'),
    path('documents/<int:document_id>/chunks/', DocumentChunksView.as_view(), name='document_chunks'),
    path('documents/<int:document_id>/insights/', DocumentInsightsView.as_view(), name='document_insights'),
    path('documents/<int:document_id>/search/', DocumentSearchView.as_view(), name='document_search'),
    path('documents/<int:document_id>/rag/', DocumentRAGView.as_view(), name='document_rag'),

    # Truth Delta Diligence
    path('documents/<int:document_id>/truth-delta/', TruthDeltaScoreView.as_view(), name='truth_delta_score'),
    path('documents/<int:document_id>/truth-delta/analyses/', TruthDeltaAnalysisView.as_view(), name='truth_delta_analyses'),
    path('documents/<int:document_id>/truth-delta/verify/', TruthDeltaVerifyView.as_view(), name='truth_delta_verify'),
    path('documents/<int:document_id>/flags/', FlaggedClaimsView.as_view(), name='truth_delta_flags'),
    path('documents/<int:document_id>/report/', CredibilityReportView.as_view(), name='truth_delta_report'),

    # ──────────────────────────────────────────────────────────────────────────
    # LEGACY & UI ENDPOINTS (Maintained for Compatibility)
    # ──────────────────────────────────────────────────────────────────────────
    path('health/', standard_views.ZeldaHealthCheckAPIView.as_view(), name='health_check'),
    path('api/v1/zelda/search/', standard_views.ZeldaGlobalSearchAPIView.as_view(), name='global_search_api'),
    path('pitch-analysis/', standard_views.PitchDeckAnalysisAPIView.as_view(), name='pitch_analysis'),
    path('documents/analyze/', standard_views.DocumentIntakeAPIView.as_view(), name='document_intake'),
    path('founder/match-radar/', standard_views.FounderMatchRadarAPIView.as_view(), name='founder_match_radar'),
    path('intelligence-memo/', standard_views.IntelligenceMemoAPIView.as_view(), name='intelligence_memo'),
    path('summarize/', standard_views.SummarizePageAPIView.as_view(), name='summarize'),
    path('match-radar/', standard_views.MatchRadarAPIView.as_view(), name='match_radar'),
    path('gateway/<str:source_name>/', standard_views.ZeldaGatewayAPIView.as_view(), name='gateway'),
    path('dashboard/intelligence/', standard_views.zelda_intelligence_dashboard, name='intelligence_dashboard'),
    path('search/', standard_views.zelda_search_view, name='zelda_search'),
    path('ui/search/', standard_views.zelda_search_view, name='zelda_search_ui'),
    path('documents/<int:document_id>/verification/', standard_views.truth_delta_ui_view, name='truth_delta_ui'),
    path('alerts/', ContradictionAlertListView.as_view(), name='contradiction-alerts'),

]