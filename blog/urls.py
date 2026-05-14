from django.urls import path
from blog import views



urlpatterns = [
    path("blog/", views.blog_view, name="blog_view"),
    path("blog/edit/<int:pk>/", views.edit_article, name="edit_article"),
    path("blog/delete/<int:pk>/", views.delete_article, name="delete_article"),
    path('article/<int:pk>/comment/', views.add_comment, name='add_comment'),
    path('like/<int:pk>/', views.like_article, name='like_article'),
]