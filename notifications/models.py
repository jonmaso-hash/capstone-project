from django.db import models
from django.conf import settings

class Notification(models.Model):
    # Core identifying fields
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='notifications'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='sent_notifications'
    )
    
    # Context and content
    notification_type = models.CharField(max_length=50, default='INFO') 
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    target_url = models.URLField(blank=True, null=True)

    class Meta:
        # Performance: Indexing recipient and is_read optimizes your unread-count API
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.notification_type} for {self.recipient.username}: {self.message[:20]}..."