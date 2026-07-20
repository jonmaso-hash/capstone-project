from django.urls import path
from . import views

app_name = 'ops'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    path('verification/', views.verification_queue, name='verification_queue'),
    path('verification/<str:role>/<int:profile_id>/action/', views.review_action, name='review_action'),
    path('verification/<str:role>/<int:profile_id>/flag/', views.flag_for_review, name='flag_for_review'),

    path('reports/', views.reported_users, name='reported_users'),
    path('reports/<int:report_id>/resolve/', views.resolve_report, name='resolve_report'),
    path('reports/submit/<str:username>/', views.submit_user_report, name='submit_user_report'),

    path('featured/', views.featured_profiles, name='featured_profiles'),
    path('featured/<str:role>/<int:profile_id>/toggle/', views.toggle_featured, name='toggle_featured'),

    path('intros/create/', views.manual_intro_create, name='manual_intro_create'),

    path('matches/', views.match_override, name='match_override'),
    path('matches/<str:conn_type>/<int:conn_id>/override/', views.override_connection_status, name='override_connection_status'),

    path('bulk-email/', views.bulk_email, name='bulk_email'),

    path('invites/', views.invite_management, name='invite_management'),
    path('invites/<int:invite_id>/revoke/', views.revoke_invite, name='revoke_invite'),

    path('waitlist/', views.waitlist_management, name='waitlist_management'),
    path('waitlist/<int:entry_id>/convert/', views.convert_waitlist_to_invite, name='convert_waitlist_to_invite'),

    path('announcements/', views.announcements_view, name='announcements'),
    path('announcements/<int:announcement_id>/toggle/', views.toggle_announcement, name='toggle_announcement'),

    path('users/', views.user_management, name='user_management'),
    path('users/<int:user_id>/toggle-active/', views.toggle_user_active, name='toggle_user_active'),
    path('users/<int:user_id>/impersonate/', views.start_impersonation, name='start_impersonation'),
    path('impersonate/stop/', views.stop_impersonation, name='stop_impersonation'),

    path('documents/', views.document_review, name='document_review'),
    path('documents/<int:document_id>/toggle-hidden/', views.toggle_document_hidden, name='toggle_document_hidden'),
    path('documents/<str:role>/<int:profile_id>/toggle-profile-hidden/', views.toggle_profile_document_hidden, name='toggle_profile_document_hidden'),

    path('training-data/', views.training_data, name='training_data'),
    path('training-data/export/', views.export_training_data, name='export_training_data'),

    path('failed-tasks/', views.failed_tasks, name='failed_tasks'),
    path('failed-tasks/<int:failure_id>/requeue/', views.requeue_failed_task, name='requeue_failed_task'),

    path('stale-documents/', views.stale_documents, name='stale_documents'),
    path('stale-documents/<int:document_id>/requeue/', views.requeue_stale_document, name='requeue_stale_document'),

    path('insight-reports/', views.insight_reports, name='insight_reports'),
    path('insight-reports/<int:report_id>/toggle-published/', views.toggle_insight_report_published, name='toggle_insight_report_published'),
]
