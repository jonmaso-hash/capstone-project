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
    path('', include('pages.urls', namespace='pages')), 
    path('', include('blog.urls')),
    path('jobs/', include('jobs.urls', namespace='jobs')),
    path('search/', global_search, name='global_search'),
    path('blog/', include('blog.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)