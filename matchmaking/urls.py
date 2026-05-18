from django.urls import path
from . import views

app_name = 'matchmaking'

urlpatterns = [
    path('dashboard/investor/', views.investor_dashboard, name='investor_dashboard'),
    path('dashboard/founder/', views.founder_dashboard, name='founder_dashboard'),
    path('bulletin/', views.founder_bulletin_board, name='bulletin_board'),
    path('founder/matches/', views.founder_matchmaker, name='founder_matchmaker'),
    path('intro/request/<int:application_id>/<int:investor_id>/', views.request_intro, name='request_intro'),
    path('vote/record/', views.record_vote, name='record_vote'),
    
    # Secure Deal Room Main View
    path('deal-room/', views.deal_room_workspace, name='diligence_chat'),
    
    path('chat/initiate/<int:target_user_id>/', views.initiate_direct_chat, name='initiate_direct_chat'),
]