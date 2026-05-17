from django.urls import path
from . import views

app_name = 'matchmaking'

urlpatterns = [
path('investor/dashboard/', views.investor_dashboard, name='investor_dashboard'),
path('founder/dashboard/', views.founder_dashboard, name='founder_index'),
path('request-intro/<int:application_id>/<int:investor_id>/', views.request_intro, name='request_intro'),
path('vote/', views.record_vote, name='record_vote'),
path('bulletin_board/', views.founder_bulletin_board, name='bulletin_board'),
path('founder/matches/', views.founder_matchmaker, name='founder_matchmaker'),
]