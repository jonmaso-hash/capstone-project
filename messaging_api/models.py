# messaging_api/models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class ChatThread(models.Model):
    THREAD_TYPES = [
        ('direct', 'Direct Message (1-on-1)'),
        ('group', 'Group Venture Channel'),
        ('deal_room', 'Secure Deal Room Negotiation'),
    ]

    title = models.CharField(max_length=255, blank=True, null=True, help_text="Optional name for groups/deal rooms.")
    thread_type = models.CharField(max_length=15, choices=THREAD_TYPES, default='direct')
    participants = models.ManyToManyField(User, related_name='chat_threads')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'messaging_api'
        verbose_name = "Chat Thread"
        verbose_name_plural = "Chat Threads"

    def __str__(self):
        if self.title:
            return f"{self.get_thread_type_display()}: {self.title}"
        return f"{self.get_thread_type_display()} Thread ({self.id})"


class ChatMessage(models.Model):
    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    body_text = models.TextField()
    is_read = models.BooleanField(default=False)
    
    # Structured AI enrichment blocks calculated by Zelda
    zelda_moderation_metadata = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="Stores parsed sentiment metrics, safety scores, or urgency flags."
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'messaging_api'
        verbose_name = "Chat Message"
        verbose_name_plural = "Chat Messages"
        ordering = ['timestamp']

    def __str__(self):
        return f"Msg {self.id} from {self.sender.username} at {self.timestamp.strftime('%M:%S')}"