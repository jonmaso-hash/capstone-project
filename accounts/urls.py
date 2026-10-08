# accounts/urls.py
from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views
from . import staff_mfa
from zelda_api.views import ZeldaGlobalSearchAPIView

app_name = 'accounts' 

urlpatterns = [
    path('staff-mfa/setup/', staff_mfa.setup, name='staff_mfa_setup'),
    path('staff-mfa/verify/', staff_mfa.verify, name='staff_mfa_verify'),
    # ==========================================
    # AUTHENTICATION ENGINE ROUTES
    # ==========================================
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', LogoutView.as_view(next_page='pages:home'), name='logout'),
    path('post-login/', views.post_login_router, name='post_login_router'),
    path('choose-role/', views.choose_role, name='choose_role'),
    path('create-profile/', views.create_profile, name='create_profile'),
    path('my-dashboard/', views.dashboard, name='dashboard'),

    # ==========================================
    # USER PROFILE DISPATCH LAYER
    # ==========================================
    path('profile/', views.redirect_to_own_profile, name='profile_self'),
    
    # 👑 FIXED: Exact matches must live ABOVE dynamic parameters
    path('profile/toggle-privacy/', views.toggle_privacy_view, name='toggle_privacy'),
    
    path('profile/<str:username>/analysis/', views.profile_analysis, name='profile_analysis'),
    path('peer-benchmark/<int:benchmark_id>/', views.peer_market_benchmark_detail, name='peer_market_benchmark_detail'),
    path('peer-benchmark/<int:benchmark_id>/share-toggle/', views.peer_market_benchmark_share_toggle, name='peer_market_benchmark_share_toggle'),
    path('peer-benchmark/share/<uuid:share_token>/', views.peer_market_benchmark_share, name='peer_market_benchmark_share'),

    path('business-verification/', views.business_verification, name='business_verification'),
    path('business-verification/request/', views.business_verification_request, name='business_verification_request'),
    path('business-verification/confirm/', views.business_verification_confirm, name='business_verification_confirm'),
    path('business-verification/representation/attest/', views.company_representation_attest, name='company_representation_attest'),
    path('business-verification/representation/withdraw/', views.company_representation_withdraw, name='company_representation_withdraw'),

    path('profile/<str:username>/', views.profile, name='profile'),

    path('profile/id/<int:pk>/', views.profile, name='profile_by_id'),

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
    
    path('update-metrics/', views.update_criteria, name='update_metrics'),   
    path('update-criteria/', views.update_criteria, name='update_criteria'),
    path('dashboard/', views.zelda_dashboard_view, name='zelda_dashboard'),
    path('toggle-dm/', views.toggle_dm_view, name='toggle_dm'),
]
