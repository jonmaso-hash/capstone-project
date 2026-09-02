from django.urls import path
from . import views

app_name = 'usersettings'

urlpatterns = [
    path('', views.settings_home, name='home'),
    path('toggle/', views.toggle_setting, name='toggle_setting'),
    path('profile-picture/', views.update_profile_picture, name='update_profile_picture'),
    path('username/', views.update_username, name='update_username'),
    path('profile/archive/', views.archive_profile, name='archive_profile'),
    path('profile/unarchive/', views.unarchive_profile, name='unarchive_profile'),
    path('profile/delete/', views.delete_profile_confirm, name='delete_profile_confirm'),
    path('profile/founder/', views.edit_founder_profile, name='edit_founder_profile'),
    path('profile/investor/', views.edit_investor_profile, name='edit_investor_profile'),
    path('profile/seller/', views.edit_seller_profile, name='edit_seller_profile'),
    path('profile/buyer/', views.edit_buyer_profile, name='edit_buyer_profile'),
]
