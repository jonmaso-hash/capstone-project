# accounts/urls.py
from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views
from zelda_api.views import ZeldaGlobalSearchAPIView

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
    
    # 👑 FIXED: Exact matches must live ABOVE dynamic parameters
    path('profile/toggle-privacy/', views.toggle_privacy_view, name='toggle_privacy'),
    
    path('profile/<str:username>/', views.profile, name='profile'),

    # ==========================================
    # WORKSPACE MATCHMAKING ONBOARDING FLOWS
    # ==========================================
    path('seeking-investment/', views.seeking_investment, name='seeking_investment'),
    path('investor-form/', views.investor_form, name='investor_form'),

    # ==========================================
    # DATA & COMMUNICATIONS ENDPOINTS (APIs)
    # ==========================================
    path('stream-token/', views.get_stream_token, name='stream_token'),
    
    # 🎯 ADD THIS NEW LINE RIGHT HERE:
    path('search-api/', ZeldaGlobalSearchAPIView.as_view(), name='search_api'),
    
    # ==========================================
    # AI ASSISTANCE SEARCH ENGINE CANVAS
    # ==========================================
    path('ai_search/', views.ai_search_page, name='ai_search_page'),
    path('assistant/', views.ai_search_page, name='ai_assistant_page'),
    
    path('stream-token/', views.get_stream_token, name='stream_token'),
    
    path('update-metrics/', views.update_criteria, name='update_metrics'),   
    path('update-criteria/', views.update_criteria, name='update_criteria'),
    path('dashboard/', views.zelda_dashboard_view, name='zelda_dashboard'),
]