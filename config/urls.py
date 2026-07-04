from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from matchmaking.views import global_search
from matchmaking.enterprise_views import EnterpriseFounderSearchView, EnterprisePlatformStatsView
from django.views.generic import TemplateView
from django.shortcuts import render
from zelda_api import views


def memo_dashboard_view(request, startup_name):
    # This ensures startup_name is available in the template context
    return render(request, 'search/memo_dashboard.html', {'startup_name': startup_name})

urlpatterns = [
    path(settings.ADMIN_URL_PATH, admin.site.urls),
    path('', include('pages.urls')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('matchmaking/', include('matchmaking.urls')), 
    path('jobs/', include('jobs.urls', namespace='jobs')),
    path('search/', global_search, name='global_search'),
    path('blog/', include('blog.urls')),
    path('api/v1/zelda/', include('zelda_api.urls')),
    path('memo-dashboard/', include(('zelda_api.urls', 'zelda_api'), namespace='zelda_api_dashboard')),
    path('api/v1/enterprise/founders/', EnterpriseFounderSearchView.as_view(), name='enterprise_founder_search'),
    path('api/v1/enterprise/stats/', EnterprisePlatformStatsView.as_view(), name='enterprise_platform_stats'),
    path('settings/', include('usersettings.urls', namespace='usersettings')),
    path('<str:startup_name>/', views.MemoIntelligenceView.as_view(), name='memo-intelligence'),
    path('notifications/', include('notifications.urls')),
]
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)