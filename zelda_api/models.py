# zelda_api/models.py
from django.db import models
from django.conf import settings
from django.utils.text import slugify
from zelda_api.protocol import FoundryStandardMixin 
from jobs_api.models import JobListing, JobApplication


# ==========================================
# CONTENT & KNOWLEDGE ENGINE MODELS
# ==========================================
class ArticleCategory(FoundryStandardMixin, models.Model):
    source_name = "articles_category"
    
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        app_label = 'zelda_api'
        verbose_name = "Article Category"
        verbose_name_plural = "Article Categories"

    def get_serialized_data(self):
        return {"name": self.name, "slug": self.slug}

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ArticlePost(FoundryStandardMixin, models.Model):
    source_name = "articles"
    
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
    zelda_seo_analytics = models.JSONField(default=dict, blank=True)
    
    # ADDED TIMESTAMPS TO FIX THE (models.E015) ORDERING ERROR
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'zelda_api'
        ordering = ['-created_at']

    def get_serialized_data(self):
        return {
            "title": self.title,
            "status": self.status,
            "seo_analytics": self.zelda_seo_analytics
        }

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title