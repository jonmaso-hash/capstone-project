from django.urls import path
from . import views
from .views import toggle_follow

app_name = 'matchmaking'

urlpatterns = [
    path('profile/toggle-privacy/', views.toggle_privacy_view, name='toggle_privacy'),
    # =====================================================================
    # ECOSYSTEM DASHBOARDS
    # =====================================================================
    path('dashboard/investor/', views.investor_dashboard, name='investor_dashboard'),
    path('dashboard/investor/shortlist/', views.investor_shortlist, name='investor_shortlist'),
    path('dashboard/founder/', views.founder_dashboard, name='founder_dashboard'),
    path('dashboard/buyer/', views.buyer_dashboard, name='buyer_dashboard'),
    path('dashboard/seller/', views.seller_dashboard, name='seller_dashboard'),

    # =====================================================================
    # MATCHMAKING ENGINE & BULLETIN ROUTING
    # =====================================================================
    # This matches the synced /matchmaking/bulletin/ target mapped in accounts
    path('bulletin/', views.founder_bulletin_board, name='bulletin_board'),
    path('founder/matches/', views.founder_matchmaker, name='founder_matchmaker'),
    
    # =====================================================================
    # INTROS & DEAL SCREENING ENGAGEMENT
    # =====================================================================
    path('intro/request/<int:application_id>/<int:investor_id>/', views.request_intro, name='request_intro'),
    path('intro/request-from-founder/<int:investor_id>/', views.request_intro_from_founder, name='request_intro_from_founder'),
    path('vote/record/', views.record_vote, name='record_vote'),

    # =====================================================================
    # BUSINESS MARKETPLACE (BUYER/SELLER M&A)
    # =====================================================================
    path('acquisitions/bulletin/', views.acquisition_bulletin_board, name='acquisition_bulletin_board'),
    path('acquisitions/intro/request/<int:seller_id>/<int:buyer_id>/', views.request_acquisition_intro, name='request_acquisition_intro'),
    path('acquisitions/intro/request-from-seller/<int:buyer_id>/', views.request_intro_from_seller, name='request_intro_from_seller'),
    path('acquisitions/action/', views.acquisition_connection_action_view, name='acquisition_connection_action'),
    path('acquisitions/vote/record/', views.record_deal_vote, name='record_deal_vote'),


    # =====================================================================
    # REALTIME CHAT & DILIGENCE ROOM SPACES
    # =====================================================================
    path('deal-room/', views.deal_room_view, name='diligence_chat'),    path('chat/initiate/<int:target_user_id>/', views.initiate_direct_chat, name='initiate_direct_chat'),
    path('action/', views.connection_action_view, name='connection_action'),
    path('stream-token/', views.get_stream_token, name='stream_token'),    
    path('memo/<str:company_slug>/', views.standalone_memo_view, name='standalone_memo'),
    path('follow/<str:username>/', toggle_follow, name='toggle_follow'),
    path('milestones/post/', views.post_milestone, name='post_milestone'),
    path('milestones/<int:milestone_id>/delete/', views.delete_milestone, name='delete_milestone'),
    
    path('search/', views.global_search, name='global_search'),
    path('search/export/', views.export_search_csv, name='export_search_csv'),
    path('metrics/', views.platform_metrics, name='platform_metrics'),

    # =====================================================================
    # PITCH DECK VIEWER & TELEMETRY
    # =====================================================================
    path('deck/<int:application_id>/view/', views.view_pitch_deck, name='view_pitch_deck'),
    path('deck/<int:application_id>/file/', views.pitch_deck_file, name='pitch_deck_file'),
    path('deck/<int:application_id>/telemetry/', views.record_deck_telemetry, name='record_deck_telemetry'),
    path('deck/<int:application_id>/analytics/', views.deck_analytics, name='deck_analytics'),

    # =====================================================================
    # FUNDRAISING CRM
    # =====================================================================
    path('crm/', views.fundraising_crm, name='fundraising_crm'),
    path('crm/lead/create/', views.create_lead, name='create_lead'),
    path('crm/lead/<int:lead_id>/stage/', views.update_lead_stage, name='update_lead_stage'),
    path('crm/lead/<int:lead_id>/delete/', views.delete_lead, name='delete_lead'),

    path('similar/<int:application_id>/', views.find_similar_startups, name='find_similar_startups'),

    # =====================================================================
    # DEAL PULSE (investor CRM)
    # =====================================================================
    path('deal-pulse/', views.deal_pulse, name='deal_pulse'),
    path('deal-pulse/<int:connection_id>/toggle-attention/', views.toggle_deal_attention, name='toggle_deal_attention'),
    path('deal-pulse/<int:connection_id>/notes/', views.update_deal_notes, name='update_deal_notes'),
]