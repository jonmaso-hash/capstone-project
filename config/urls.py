from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from matchmaking.views import global_search
from django.views.generic import TemplateView
from django.shortcuts import render
from zelda_api import views


def memo_dashboard_view(request, startup_name):
    # This ensures startup_name is available in the template context
    return render(request, 'search/memo_dashboard.html', {'startup_name': startup_name})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('pages.urls')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('matchmaking/', include('matchmaking.urls')), 
    path('jobs/', include('jobs.urls', namespace='jobs')),
    path('search/', global_search, name='global_search'),
    path('blog/', include('blog.urls')),
    path('api/v1/zelda/', include('zelda_api.urls')),
    path('memo-dashboard/', include(('zelda_api.urls', 'zelda_api'), namespace='zelda_api_dashboard')),
    path('api/v1/marketing/', include('marketing_api.urls')),
    path('api/v1/legal/', include('legal_api.urls')),
    path('api/v1/banking/', include('banking_api.urls')),
    path('api/v1/energy/', include('energy_api.urls')),    
    path('api/v1/articles/', include('articles_api.urls')),
    path('api/v1/automotive/', include('automotive_api.urls')),
    path('api/v1/hotel/', include('hotel_api.urls')),
    path('api/v1/insurance/', include('insurance_api.urls')), 
    path('api/v1/jobs/', include('jobs_api.urls')), 
    path('api/v1/logistics/', include('logistics_api.urls')), 
    path('api/v1/marketplace/', include('marketplace_api.urls')), 
    path('api/v1/messaging/', include('messaging_api.urls')), 
    path('<str:startup_name>/', views.MemoIntelligenceView.as_view(), name='memo-intelligence'),
    path('notifications/', include('notifications.urls')),
]
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)