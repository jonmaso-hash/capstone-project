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
    path('dashboard/founder/highlight/', views.activate_founder_highlight, name='activate_founder_highlight'),
    path('dashboard/seller/highlight/', views.activate_seller_highlight, name='activate_seller_highlight'),

    # =====================================================================
    # DIGEST ENGAGEMENT TRACKING (email open pixel / click redirect)
    # =====================================================================
    path('digest/pixel/<uuid:token>/', views.digest_open_pixel, name='digest_open_pixel'),
    path('digest/click/<uuid:token>/<str:destination>/', views.digest_click_redirect, name='digest_click_redirect'),

    # =====================================================================
    # MATCHMAKING ENGINE & BULLETIN ROUTING
    # =====================================================================
    # This matches the synced /matchmaking/bulletin/ target mapped in accounts
    path('bulletin/', views.founder_bulletin_board, name='bulletin_board'),

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
    path('acquisitions/bulletin/export/', views.export_acquisition_csv, name='export_acquisition_csv'),
    path('acquisitions/intro/request/<int:seller_id>/<int:buyer_id>/', views.request_acquisition_intro, name='request_acquisition_intro'),
    path('acquisitions/intro/request-from-seller/<int:buyer_id>/', views.request_intro_from_seller, name='request_intro_from_seller'),
    path('acquisitions/action/', views.acquisition_connection_action_view, name='acquisition_connection_action'),
    path('acquisitions/vote/record/', views.record_deal_vote, name='record_deal_vote'),
    path('acquisitions/seller/interest-analytics/', views.seller_interest_analytics, name='seller_interest_analytics'),


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

    # =====================================================================
    # DATA ROOM
    # =====================================================================
    path('data-room/<str:username>/', views.data_room, name='data_room'),
    path('data-room/<str:username>/upload/', views.data_room_upload, name='data_room_upload'),
    path('data-room/document/<int:document_id>/', views.data_room_document_serve, name='data_room_document_serve'),
    path('data-room/document/<int:document_id>/delete/', views.data_room_delete, name='data_room_delete'),
    path('data-room/document/<int:document_id>/request/', views.data_room_request_access, name='data_room_request_access'),
    path('data-room/request/<int:request_id>/decide/', views.data_room_decide_request, name='data_room_decide_request'),
    path('data-room/<str:username>/request-information/', views.data_room_request_information, name='data_room_request_information'),
    path('data-room/information-request/<int:request_id>/decline/', views.data_room_decline_information_request, name='data_room_decline_information_request'),

    # =====================================================================
    # PITCH VIDEO & PROFILE DWELL-TIME TELEMETRY
    # =====================================================================
    path('video/<int:application_id>/telemetry/', views.record_video_telemetry, name='record_video_telemetry'),
    path('profile/<str:username>/duration/', views.record_profile_duration, name='record_profile_duration'),
    # NOTE: deck_analytics was removed — Profile Analysis (accounts:profile_analysis) replaces it.

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
    path('deal-workspace/<int:connection_id>/', views.deal_workspace_view, name='deal_workspace'),
    path('deal-workspace/acquisition/<int:connection_id>/', views.acquisition_deal_workspace_view, name='acquisition_deal_workspace'),
    path('deal-pulse/<int:connection_id>/toggle-attention/', views.toggle_deal_attention, name='toggle_deal_attention'),
    path('deal-pulse/<int:connection_id>/notes/', views.update_deal_notes, name='update_deal_notes'),

    # =====================================================================
    # PITCH VIDEOS SECTION
    # =====================================================================
    path('pitch-videos/', views.pitch_videos_section, name='pitch_videos'),
    path('pitch-videos/<str:role>/<int:profile_id>/play/', views.log_pitch_video_play, name='log_pitch_video_play'),
    path('pitch-videos/<str:role>/<int:profile_id>/like/', views.toggle_pitch_video_like, name='toggle_pitch_video_like'),
    path('pitch-videos/<str:role>/<int:profile_id>/save/', views.toggle_pitch_video_save, name='toggle_pitch_video_save'),
    path('pitch-videos/<str:role>/<int:profile_id>/comment/', views.post_pitch_video_comment, name='post_pitch_video_comment'),
    path('pitch-videos/comment/<int:comment_id>/delete/', views.delete_pitch_video_comment, name='delete_pitch_video_comment'),
    path('pitch-videos/settings/toggle/', views.toggle_pitch_video_setting, name='toggle_pitch_video_setting'),
    path('pitch-videos/settings/visibility/', views.set_pitch_video_visibility, name='set_pitch_video_visibility'),

    # =====================================================================
    # EXPLORE / ELEVATOR PITCHES — anonymous short-form discovery feed
    # =====================================================================
    # The feed page itself is served top-level at /explore/ (see config/urls.py);
    # these are the action endpoints it posts to.
    path('explore/<int:video_id>/play/', views.elevator_pitch_play, name='elevator_pitch_play'),
    path('explore/<int:video_id>/interested/', views.elevator_pitch_interested, name='elevator_pitch_interested'),
    path('explore/<int:video_id>/report/', views.elevator_pitch_report, name='elevator_pitch_report'),
    path('explore/manage/', views.manage_elevator_pitch, name='manage_elevator_pitch'),
]