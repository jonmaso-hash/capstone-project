# zelda_api/urls.py
from django.urls import path
from .views import DocumentIntakeAPIView, InvestorPortfolioIntakeAPIView
from .views import FounderMatchRadarAPIView
from . import views
from .views import (
    ZeldaGlobalSearchAPIView,
    MatchRadarAPIView,
    DocumentIntakeAPIView,
    WebExplorationAPIView,
    DocumentDirectScraperAPIView,
    MarketHealthAnalyticsAPIView,
    InvestmentMemoGeneratorAPIView,
    MemoIntelligenceView,
    ZeldaGatewayAPIView,
    SandboxScanView,  
    SummarizeView,
)

app_name = 'zelda_api'

urlpatterns = [
    # Core Engine Architecture
    path('summarize/', SummarizeView.as_view(), name='zelda-summarize'),  
    path('search/', ZeldaGlobalSearchAPIView.as_view(), name='global_search'),
    path('match/', MatchRadarAPIView.as_view(), name='match_radar'),
    path('crawl/', WebExplorationAPIView.as_view(), name='web_exploration'),
    path('documents/analyze/', DocumentIntakeAPIView.as_view(), name='document_intake'),
    
    # Sandbox / Testing Engine
    path('sandbox/scan/', SandboxScanView.as_view(), name='sandbox_scan'), # <-- Added the new endpoint
    
    # Advanced Institutional Layer Features
    path('documents/scrape/', DocumentDirectScraperAPIView.as_view(), name='document_direct_scraper'),
    path('analytics/market/', MarketHealthAnalyticsAPIView.as_view(), name='market_analytics'),
    path('gateway/<str:source_name>/', ZeldaGatewayAPIView.as_view(), name='zelda_gateway'),
    path('api/v1/zelda/documents/analyze/', DocumentIntakeAPIView.as_view(), name='founder_document_intake'),
    path('api/v1/zelda/investors/portfolio/', InvestorPortfolioIntakeAPIView.as_view(), name='investor_portfolio_intake'),
    path('api/v1/zelda/founder/match-radar/', FounderMatchRadarAPIView.as_view(), name='founder_competitive_match_radar'),
    path('<str:startup_name>/', views.MemoIntelligenceView.as_view(), name='memo-intelligence'),  
]