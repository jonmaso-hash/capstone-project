# messaging_api/serializers.py
from rest_framework import serializers
from .models import ChatMessage, ChatThread

class ChatMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)

    class Meta:
        model = ChatMessage
        fields = ['id', 'sender', 'sender_username', 'body_text', 'is_read', 'zelda_moderation_metadata', 'timestamp']


class SendMessagePayloadSerializer(serializers.Serializer):
    thread_id = serializers.IntegerField(required=True)
    body_text = serializers.CharField(required=True, min_length=1, max_length=10000)