# zelda_api/models.py
from django.db import models
from django.conf import settings
from django.utils.text import slugify

# ==========================================
# CONTENT & KNOWLEDGE ENGINE MODELS
# ==========================================
class ArticleCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        app_label = 'zelda_api'
        verbose_name = "Article Category"
        verbose_name_plural = "Article Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ArticlePost(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('review', 'Under AI Review'),
        ('published', 'Published'),
    ]
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='zelda_articles')
    category = models.ForeignKey(ArticleCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='zelda_articles')
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    content_body = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    view_count = models.PositiveIntegerField(default=0)
    zelda_seo_analytics = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'zelda_api'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


# ==========================================
# MATCHMAKING & MARKETPLACE MODELS
# ==========================================
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
    
    # 🎯 FIX: Changed related_name from 'posted_jobs' to 'zelda_posted_jobs'
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='zelda_posted_jobs'
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    company_name = models.CharField(max_length=255)
    location = models.CharField(max_length=150, default="Remote")
    job_type = models.CharField(max_length=20, choices=JOB_TYPES, default='full_time')
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_LEVELS, default='mid')
    description_text = models.TextField()
    skills_required = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'zelda_api'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

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
    
    # 🎯 FIX: Changed related_name from 'applications' to 'zelda_applications'
    job = models.ForeignKey(
        JobListing, 
        on_delete=models.CASCADE, 
        related_name='zelda_applications'
    )
    
    # 🎯 FIX: Changed related_name from 'api_job_applications' to 'zelda_job_applications'
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='zelda_job_applications'
    )
    
    cover_letter_text = models.TextField(blank=True, null=True)
    resume_file_url = models.URLField(max_length=500, blank=True, null=True)
    current_stage = models.CharField(max_length=20, choices=APPLICATION_STAGES, default='applied')
    zelda_match_score = models.FloatField(default=0.0)
    extracted_talent_profile = models.JSONField(default=dict, blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'zelda_api'
        ordering = ['-applied_at']

    def __str__(self):
        return f"{self.applicant.username} -> {self.job.title}"