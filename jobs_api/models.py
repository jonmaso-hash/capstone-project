from django.db import models
from django.contrib.auth import get_user_model

# 1. This defines the User variable so your ForeignKey doesn't throw a NameError
User = get_user_model()

# 2. This defines JobListing so that JobApplication can reference it below
class JobListing(models.Model):
    EXPERIENCE_LEVELS = [
        ('intern', 'Internship'),
        ('junior', 'Junior / Associate'),
        ('mid', 'Mid-Level'),
        ('senior', 'Senior / Lead'),
        ('executive', 'C-Suite / Executive'),
    ]
    JOB_TYPES = [
        ('full_time', 'Full-Time'),
        ('part_time', 'Part-Time'),
        ('contract', 'Contract / Freelance'),
    ]

    posted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posted_jobs')
    title = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255, help_text="Hiring startup or venture entity.")
    location = models.CharField(max_length=150, default="Remote")
    job_type = models.CharField(max_length=20, choices=JOB_TYPES, default='full_time')
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_LEVELS, default='mid')
    description_text = models.TextField()
    skills_required = models.JSONField(default=list, help_text="Array of target technical strings (e.g., Python, Django).")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'jobs_api'
        verbose_name = "Job Listing"
        verbose_name_plural = "Job Listings"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} at {self.company_name}"


class JobApplication(models.Model):
    APPLICATION_STAGES = [
        ('applied', 'Applied / Ingested'),
        ('screening', 'Zelda AI Screening'),
        ('interview', 'Interviewing'),
        ('offered', 'Offer Extended'),
        ('rejected', 'Archived'),
    ]

    job = models.ForeignKey(JobListing, on_delete=models.CASCADE, related_name='applications')
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_job_applications')
    
    cover_letter_text = models.TextField(blank=True, null=True)
    resume_file_url = models.URLField(max_length=500, blank=True, null=True)
    current_stage = models.CharField(max_length=20, choices=APPLICATION_STAGES, default='applied')
    
    zelda_match_score = models.FloatField(default=0.0)
    extracted_talent_profile = models.JSONField(default=dict, blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'jobs_api'
        verbose_name = "Job Application"
        verbose_name_plural = "Job Applications"
        ordering = ['-applied_at']

    def __str__(self):
        return f"{self.applicant.username} -> {self.job.title}"