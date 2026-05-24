from django.urls import path
from .views import MatchRadarAPIView, DocumentIntakeAPIView, WebExplorationAPIView
from .views import (
    ZeldaGlobalSearchAPIView,
    MatchRadarAPIView,
    DocumentIntakeAPIView,
    WebExplorationAPIView,
    DocumentDirectScraperAPIView,
    MarketHealthAnalyticsAPIView,
    InvestmentMemoGeneratorAPIView,
    MemoIntelligenceView,
)

app_name = 'zelda_api'

urlpatterns = [
# Core Engine Architecture
    path('search/', ZeldaGlobalSearchAPIView.as_view(), name='global_search'),
    path('match/', MatchRadarAPIView.as_view(), name='match_radar'),
    path('crawl/', WebExplorationAPIView.as_view(), name='web_exploration'),
    path('documents/analyze/', DocumentIntakeAPIView.as_view(), name='document_intake'),
    
    # Advanced Institutional Layer Features
    path('documents/scrape/', DocumentDirectScraperAPIView.as_view(), name='document_direct_scraper'),
    path('analytics/market/', MarketHealthAnalyticsAPIView.as_view(), name='market_analytics'),
    path('memo/generate/', InvestmentMemoGeneratorAPIView.as_view(), name='memo_generate'),
    path('<str:startup_name>/', MemoIntelligenceView.as_view(), name='memo-intelligence'),
]