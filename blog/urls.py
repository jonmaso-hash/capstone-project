from django.urls import path
from .views import(
    PostListView,
    PostDetailView,
    PostCreateView,
    PostUpdateView,
    PostDeleteView,
    PostDraftListView,
    PostArchivedListView,
) 

urlpatterns = [
    path("list/", PostListView.as_view(), name="post_list"),
    path("drafts/", PostDraftListView.as_view(), name="post_drafts"),
    path("archives/", PostArchivedListView.as_view(), name="post_archives"),
    path("<int:pk>/", PostDetailView.as_view(), name="post_detail"),
    path("new/", PostCreateView.as_view(), name="post_new"),
    path("edit/<int:pk>/", PostUpdateView.as_view(), name="post_edit"),
    path("delete/<int:pk>/", PostDeleteView.as_view(), name="post_delete"),
]