from django.urls import path
from . import views

app_name = 'jobs'

urlpatterns = [
    path('', views.JobListView.as_view(), name='index'),   
    path('<int:pk>/', views.JobDetailView.as_view(), name='detail'),
    path('create/', views.JobCreateView.as_view(), name='create'),
    path('<int:pk>/apply/', views.JobApplyView.as_view(), name='apply'),
]