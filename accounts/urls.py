from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # ----------------------
    # Authentication
    # ----------------------
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),

    # ----------------------
    # User Profile
    # ----------------------
    path('profile/<str:username>/', views.profile_view, name='profile'),

    # ----------------------
    # Founder Application Flow
    # ----------------------
    path('apply/', views.seeking_investment, name='apply'),
    path('thank-you/', views.thank_you, name='thank_you'),

    # ----------------------
    # Admin-style Applications Dashboard
    # ----------------------
    path('applications/', views.applications_list, name='applications'),
]