from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

app_name = 'accounts'

urlpatterns = [
    # --- Authentication ---
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', LogoutView.as_view(next_page='pages:home'), name='logout'),

    # --- Profile & Redirection ---
    path('profile/', views.redirect_to_own_profile, name='profile_self'),
    path('profile/<str:username>/', views.profile, name='profile'),

    # --- Matchmaking Application Flow ---
    # Named 'apply' to fix the NoReverseMatch error in your profile template
    path('apply/', views.seeking_investment, name='seeking_investment'),
    path('investor-form/', views.investor_form, name='investor'),
]