from django.contrib import admin
from .models import UserSettings


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'accept_invitation_requests', 'accept_follow_requests',
                     'blog_likes_enabled', 'blog_comments_enabled',
                     'show_job_postings', 'show_articles', 'show_business_connections',
                     'show_profile_view_count']
    search_fields = ['user__username']
