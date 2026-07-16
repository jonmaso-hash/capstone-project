from django.conf import settings
from django.db import models


class UserSettings(models.Model):
    """
    Per-user preference switches with no existing home on a profile model.
    Privacy (is_private) and Direct Messaging (allow_direct_messages) stay on
    the founder/investor profile models — this only covers new toggles.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='settings'
    )

    accept_invitation_requests = models.BooleanField(default=True)
    accept_follow_requests = models.BooleanField(default=True)
    blog_likes_enabled = models.BooleanField(default=True)
    blog_comments_enabled = models.BooleanField(default=True)
    show_job_postings = models.BooleanField(default=True)
    show_articles = models.BooleanField(default=True)
    show_business_connections = models.BooleanField(default=True)
    show_contact_info = models.BooleanField(default=True)
    show_milestones = models.BooleanField(default=True)
    show_profile_view_count = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    TOGGLE_FIELDS = [
        'accept_invitation_requests',
        'accept_follow_requests',
        'blog_likes_enabled',
        'blog_comments_enabled',
        'show_job_postings',
        'show_articles',
        'show_business_connections',
        'show_contact_info',
        'show_milestones',
        'show_profile_view_count',
    ]

    @classmethod
    def for_user(cls, user):
        obj, _ = cls.objects.get_or_create(user=user)
        return obj

    def __str__(self):
        return f"Settings for {self.user.username}"
