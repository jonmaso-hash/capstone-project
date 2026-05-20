from django.urls import path
from blog import views

app_name = 'blog'

urlpatterns = [
    # Change "blog/" to "" so it uses the root defined in config/urls.py
    path("", views.blog_view, name="blog_view"),
    
    # Change "blog/edit/..." to "edit/..."
    path("edit/<int:pk>/", views.edit_article, name="edit_article"),
    
    # Change "blog/delete/..." to "delete/..."
    path("delete/<int:pk>/", views.delete_article, name="delete_article"),
    
    path('article/<int:pk>/comment/', views.add_comment, name='add_comment'),
    path('like/<int:pk>/', views.like_article, name='like_article'),
    path('favorites/', views.favorites_list, name='favorites_list'),
    path('<int:pk>/', views.article_detail, name='article_detail'), 
    path('article/<int:pk>/favorite/', views.toggle_favorite, name='toggle_favorite'),
]