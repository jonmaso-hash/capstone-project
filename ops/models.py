import secrets

from django.conf import settings
from django.db import models


class UserReport(models.Model):
    """A user-submitted report against another user's conduct — feeds the
    Reported Users queue in the ops dashboard."""

    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('RESOLVED', 'Resolved'),
        ('DISMISSED', 'Dismissed'),
    ]

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reports_filed'
    )
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reports_received'
    )
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports_resolved'
    )
    resolution_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"Report: {self.reported_user.username} ({self.status})"


class Invite(models.Model):
    """Beta invite tracking — outreach/CRM tooling only, does not gate
    signup (signup stays fully open)."""

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('EXPIRED', 'Expired'),
    ]

    email = models.EmailField()
    code = models.CharField(max_length=32, unique=True, editable=False)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='invites_sent')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = secrets.token_urlsafe(16)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invite: {self.email} ({self.status})"


class WaitlistEntry(models.Model):
    """A prospect who asked to be notified before signing up — outreach
    tooling only, does not gate signup."""

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255, blank=True)
    role_interest = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    invited = models.BooleanField(default=False)
    invited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.email


class Announcement(models.Model):
    """Site-wide banner shown near the top of every page while active."""

    title = models.CharField(max_length=255)
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='announcements')
    created_at = models.DateTimeField(auto_now_add=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class BulkEmailLog(models.Model):
    """Audit trail for a bulk-announcement email blast — one row per send,
    not per recipient."""

    AUDIENCE_CHOICES = [
        ('ALL', 'All Users'),
        ('FOUNDER', 'Founders'),
        ('INVESTOR', 'Investors'),
        ('SELLER', 'Sellers'),
        ('BUYER', 'Buyers'),
    ]

    subject = models.CharField(max_length=255)
    body = models.TextField()
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bulk_emails_sent')
    sent_at = models.DateTimeField(auto_now_add=True)
    recipient_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.subject} → {self.get_audience_display()} ({self.recipient_count})"


class ImpersonationLog(models.Model):
    """Audit trail for staff impersonation — who impersonated whom and for
    how long. Never deleted from the ops UI."""

    impersonator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='impersonation_sessions_started'
    )
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='impersonation_sessions_received'
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        status = "active" if not self.ended_at else "ended"
        return f"{self.impersonator.username} → {self.target.username} ({status})"


class FailedTaskLog(models.Model):
    """
    Dead-letter record — written when a Celery task's retries are exhausted
    (bind=True, max_retries=3 tasks in matchmaking/tasks.py and
    zelda_api/tasks.py), so a failure is visible and requeueable from the
    ops dashboard instead of just a log line that scrolls away.
    """

    task_name = models.CharField(max_length=255, help_text="Dotted Celery task path, e.g. 'matchmaking.tasks.send_weekly_digests'.")
    args_json = models.JSONField(default=list, blank=True, help_text="Positional args the task was originally called with, for requeueing.")
    exception_message = models.TextField()
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-attempted_at']

    def __str__(self):
        return f"{self.task_name} failed at {self.attempted_at:%Y-%m-%d %H:%M}"


def log_failed_task(task_name, args, exception_message):
    """
    Fire-and-forget — mirrors matchmaking.models.log_training_example's
    "never break the calling task" contract. Called from the retries-
    exhausted branch of each bind=True Celery task, so a failure is always
    visible on the ops Failed Tasks page instead of only in logs.
    """
    try:
        FailedTaskLog.objects.create(
            task_name=task_name, args_json=list(args), exception_message=str(exception_message),
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to log failed task: {str(e)}")
