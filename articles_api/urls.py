# articles_api/urls.py
from django.urls import path
from .views import PublicArticleFeedAPIView, CreateArticleAPIView

app_name = 'articles_api'

urlpatterns = [
    path('articles/', PublicArticleFeedAPIView.as_view(), name='article_feed'),
    path('articles/create/', CreateArticleAPIView.as_view(), name='create_article'),
]