from django.urls import path
from . import views

app_name = 'growth'

urlpatterns = [
    path('investors/<str:sector_slug>/<str:stage_slug>/<str:location_slug>/', views.investor_directory, name='investor_directory'),
    path('startups/<str:sector_slug>/<str:stage_slug>/<str:location_slug>/', views.founder_directory, name='founder_directory'),
    path('badge/<str:role>/<str:username>.svg', views.readiness_badge, name='readiness_badge'),
    path('referral/invite/', views.create_referral_invite, name='create_referral_invite'),
    path('insights/', views.insights_list, name='insights_list'),
    path('insights/<slug:period_slug>/', views.insights_detail, name='insights_detail'),
]
