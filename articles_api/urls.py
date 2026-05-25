# articles_api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ArticlePostViewSet

app_name = 'articles_api'

router = DefaultRouter()
router.register(r'posts', ArticlePostViewSet, basename='articlepost')

urlpatterns = [
    # The router handles GET /posts/ (feed) and POST /posts/ingest_draft/
    path('', include(router.urls)),
]