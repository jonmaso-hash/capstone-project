# messaging_api/admin.py
from django.contrib import admin
from .models import ChatThread, ChatMessage

@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'thread_type', 'created_at')
    list_filter = ('thread_type', 'created_at')
    search_fields = ('title', 'id')
    filter_horizontal = ('participants',)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'thread', 'sender', 'is_read', 'timestamp')
    list_filter = ('is_read', 'timestamp', 'thread__thread_type')
    search_fields = ('body_text', 'sender__username', 'thread__id')
    ordering = ('timestamp',)