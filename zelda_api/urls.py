# zelda_api/urls.py
from django.urls import path
from . import views as standard_views
from .pipeline_views import (
    DocumentIngestView,
    DocumentStatusView,
    DocumentMemoView,
    DocumentValuationView,
    DocumentChunksView,
    DocumentInsightsView,
    DocumentSearchView,
    DocumentRAGView,
)
from .truth_delta_views import (
    TruthDeltaScoreView,
    TruthDeltaVerifyView,
)

app_name = 'zelda_api'

urlpatterns = [
    # ──────────────────────────────────────────────────────────────────────────
    # PIPELINE & TRUTH DELTA (New Standard)
    # ──────────────────────────────────────────────────────────────────────────
    path('documents/ingest/', DocumentIngestView.as_view(), name='document_ingest'),
    path('documents/<int:document_id>/status/', DocumentStatusView.as_view(), name='document_status'),
    path('documents/<int:document_id>/memo/', DocumentMemoView.as_view(), name='document_memo'),
    path('documents/<int:document_id>/valuation/', DocumentValuationView.as_view(), name='document_valuation'),
    path('documents/<int:document_id>/chunks/', DocumentChunksView.as_view(), name='document_chunks'),
    path('documents/<int:document_id>/insights/', DocumentInsightsView.as_view(), name='document_insights'),
    path('documents/<int:document_id>/search/', DocumentSearchView.as_view(), name='document_search'),
    path('documents/<int:document_id>/rag/', DocumentRAGView.as_view(), name='document_rag'),

    # Truth Delta Diligence
    path('documents/<int:document_id>/truth-delta/', TruthDeltaScoreView.as_view(), name='truth_delta_score'),
    path('documents/<int:document_id>/truth-delta/verify/', TruthDeltaVerifyView.as_view(), name='truth_delta_verify'),

    # ──────────────────────────────────────────────────────────────────────────
    # LEGACY & UI ENDPOINTS (Maintained for Compatibility)
    # ──────────────────────────────────────────────────────────────────────────
    path('health/', standard_views.ZeldaHealthCheckAPIView.as_view(), name='health_check'),
    # NOTE: this used to be registered at 'api/v1/zelda/search/' while this whole
    # urls.py is *also* mounted at 'api/v1/zelda/' in config/urls.py — making the
    # real path '/api/v1/zelda/api/v1/zelda/search/', which nothing ever called.
    # Every fetch() in the Zelda sidebar hits '/api/v1/zelda/search/', which was
    # actually matching the dead HTML stub below (zelda_search_view, hardcoded
    # empty results) instead of this real search API. Fixed: this is now the one
    # at the path the frontend actually calls.
    path('search/', standard_views.ZeldaGlobalSearchAPIView.as_view(), name='global_search_api'),
    path('ask/', standard_views.ZeldaAskAPIView.as_view(), name='ask'),
    path('journey-status/', standard_views.JourneyStatusAPIView.as_view(), name='journey_status'),
    path('pitch-analysis/', standard_views.PitchDeckAnalysisAPIView.as_view(), name='pitch_analysis'),
    path('documents/analyze/', standard_views.DocumentIntakeAPIView.as_view(), name='document_intake'),
    path('intelligence-memo/', standard_views.IntelligenceMemoAPIView.as_view(), name='intelligence_memo'),
    path('summarize/', standard_views.SummarizePageAPIView.as_view(), name='summarize'),
    path('dashboard/intelligence/', standard_views.zelda_intelligence_dashboard, name='intelligence_dashboard'),
    path('ui/search/', standard_views.zelda_search_view, name='zelda_search_ui'),
    path('documents/<int:document_id>/verification/', standard_views.truth_delta_ui_view, name='truth_delta_ui'),
    path('documents/<int:document_id>/truth-delta/claims/<str:category>/flag/', standard_views.flag_truth_delta_claim, name='truth_delta_claim_flag'),
    path('truth-delta/claims/<int:clarification_id>/respond/', standard_views.respond_to_clarification_request, name='truth_delta_claim_respond'),
    path('analyze/founder/<str:founder_username>/', standard_views.analyze_founder_profile, name='analyze_founder'),
    path('analyze/founder/<str:founder_username>/confirm/', standard_views.confirm_analyze_founder_profile, name='analyze_founder_confirm'),
    path('documents/<int:document_id>/ic-memo/', standard_views.ic_memo_view, name='ic_memo'),
    path('documents/<int:document_id>/ic-memo/download/', standard_views.ic_memo_download_view, name='ic_memo_download'),

    # ──────────────────────────────────────────────────────────────────────────
    # BUSINESS VALUATION
    # ──────────────────────────────────────────────────────────────────────────
    path('valuation/request/', standard_views.valuation_request_view, name='valuation_request'),
    path('valuation/history/', standard_views.valuation_history_view, name='valuation_history'),
    path('valuation/<int:document_id>/', standard_views.valuation_report_view, name='valuation_report'),

]