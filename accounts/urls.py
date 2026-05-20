from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

# Application namespace utilized by {% url 'accounts:...' %} template tags
app_name = 'accounts'

urlpatterns = [
    # ==========================================
    # AUTHENTICATION ENGINE ROUTES
    # ==========================================
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', LogoutView.as_view(next_page='pages:home'), name='logout'),

    # ==========================================
    # USER PROFILE DISPATCH LAYER
    # ==========================================
    path('profile/', views.redirect_to_own_profile, name='profile_self'),
    path('profile/<str:username>/', views.profile, name='profile'),

    # ==========================================
    # WORKSPACE MATCHMAKING ONBOARDING FLOWS
    # ==========================================
    path('seeking-investment/', views.seeking_investment, name='seeking_investment'),
    path('investor-form/', views.investor_form, name='investor_form'),

    # ==========================================
    # DATA & COMMUNICATIONS ENDPOINTS (APIs)
    # ==========================================
    path('api/stream-token/', views.get_stream_token, name='stream_token'),
    
    # ==========================================
    # AI ASSISTANCE SEARCH ENGINE CANVAS
    # ==========================================
    # Fixed naming collision: Explicit route paths for the UI workspaces
    path('ai_search/', views.ai_search_page, name='ai_search_page'),
    path('assistant/', views.ai_search_page, name='ai_assistant_page'),
]