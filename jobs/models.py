from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

def default_expiry():
    return timezone.now() + timedelta(days=30)

class JobListing(models.Model):
    JOB_TYPES = [
        ('FT', 'Full-Time'),
        ('PT', 'Part-Time'),
        ('C', 'Contract'),
        ('I', 'Internship'),
    ]

    # Links to whoever is hiring (the founder/company account)
    poster = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='job_listings')
    company_name = models.CharField(max_length=255, help_text="Company or Startup Name")
    title = models.CharField(max_length=255, verbose_name="Job Title")
    description = models.TextField(help_text="Detailed job description and responsibilities")
    location = models.CharField(max_length=150, default="Remote", help_text="e.g., San Diego, CA or Remote")
    
    job_type = models.CharField(max_length=2, choices=JOB_TYPES, default='FT')
    salary_range = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., $120k - $150k")
    equity_range = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., 0.1% - 0.5%")
    
    # Monetization & Status Flags
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Premium paid placement boost")
    click_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(default=default_expiry)

    class Meta:
        ordering = ['-is_featured', '-created_at']

    def __str__(self):
        return f"{self.title} at {self.company_name}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


class JobApplication(models.Model):
    job = models.ForeignKey(JobListing, on_delete=models.CASCADE, related_name='applications')
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='job_applications')
    cover_letter = models.TextField(blank=True, null=True)
    resume_attachment = models.FileField(upload_to='resumes/%Y/%m/%d/', blank=True, null=True)
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-applied_at']
        unique_together = ('job', 'applicant')  # Prevents applying to the exact same job twice

    def __str__(self):
        return f"{self.applicant.username} applied to {self.job.title}"