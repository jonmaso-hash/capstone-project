from django.urls import path
from blog import views

app_name = 'blog'

urlpatterns = [
    # Main feed dashboard endpoint
    path("blog/", views.blog_view, name="blog_view"),
    
    # Author interaction management mechanics
    path("blog/edit/<int:pk>/", views.edit_article, name="edit_article"),
    path("blog/delete/<int:pk>/", views.delete_article, name="delete_article"),
    
    # Article feedback threads
    path('article/<int:pk>/comment/', views.add_comment, name='add_comment'),
    
    # Saved bookmarks & validation engines
    path('like/<int:pk>/', views.like_article, name='like_article'),
    path('favorites/', views.favorites_list, name='favorites_list'),
    path('article/<int:pk>/favorite/', views.toggle_favorite, name='toggle_favorite'),
    
    # Detailed focus view wrapper
    path('<int:pk>/', views.article_detail, name='article_detail'), 
]