from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from matchmaking.views import global_search

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('pages.urls')),
    path('accounts/', include('accounts.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('matchmaking/', include('matchmaking.urls')), 
    path('jobs/', include('jobs.urls', namespace='jobs')),
    path('search/', global_search, name='global_search'),
    path('blog/', include('blog.urls')),
    path('api/v1/zelda/', include('zelda_api.urls')),
    path('api/v1/real-estate/', include('real_estate_api.urls')),
    path('api/v1/marketing/', include('marketing_api.urls')),
    path('api/v1/legal/', include('legal_api.urls')),
    path('api/v1/banking/', include('banking_api.urls')),
    path('api/v1/energy/', include('energy_api.urls')),
    path('api/v1/articles/', include('articles_api.urls')),
    path('api/v1/automotive/', include('automotive_api.urls')),
    path('api/v1/energy/', include('energy_api.urls')),
    path('api/v1/hotel/', include('hotel_api.urls')),
    path('api/v1/insurance/', include('insurance_api.urls')), 
    path('api/v1/jobs/', include('jobs_api.urls')), 
    path('api/v1/logistics/', include('logistics_api.urls')), 
    path('api/v1/marketplace/', include('marketplace_api.urls')), 
    path('api/v1/messaging/', include('messaging_api.urls')), 
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)