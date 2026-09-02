from django.urls import path
from . import views

app_name = 'sharing'

urlpatterns = [
    path('resolve/', views.resolve_share, name='resolve_share'),
    path('user-search/', views.user_search, name='user_search'),
]
