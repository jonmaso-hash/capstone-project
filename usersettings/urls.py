from django.urls import path
from . import views

app_name = 'usersettings'

urlpatterns = [
    path('', views.settings_home, name='home'),
    path('toggle/', views.toggle_setting, name='toggle_setting'),
    path('profile/founder/', views.edit_founder_profile, name='edit_founder_profile'),
    path('profile/investor/', views.edit_investor_profile, name='edit_investor_profile'),
    path('profile/seller/', views.edit_seller_profile, name='edit_seller_profile'),
    path('profile/buyer/', views.edit_buyer_profile, name='edit_buyer_profile'),
]
