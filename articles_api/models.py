# articles_api/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from zelda_api.protocol import FoundryStandardMixin

User = get_user_model()

class ArticleCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        app_label = 'articles_api'
        verbose_name = "Article Category"
        verbose_name_plural = "Article Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

# Pinnacle Standard Implemented
class ArticlePost(FoundryStandardMixin, models.Model):
    source_name = "articles_api" # Protocol Identity

    STATUS_CHOICES = [
        ('draft', 'Draft Work in Progress'),
        ('review', 'Pending Zelda AI Review'),
        ('published', 'Live / Publicly Visible'),
    ]

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='authored_articles')
    category = models.ForeignKey(ArticleCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='articles')
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    content_body = models.TextField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft')
    view_count = models.PositiveIntegerField(default=0)
    
    zelda_seo_analytics = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="Stores auto-generated meta descriptions, target keywords, and readability scores."
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'articles_api'
        verbose_name = "Article Post"
        verbose_name_plural = "Article Posts"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    # Pinnacle contract fulfilled
    def get_serialized_data(self):
        """Standardized interface for Zelda Orchestrator to ingest content."""
        return {
            "title": self.title,
            "category": self.category.name if self.category else "Uncategorized",
            "status": self.status,
            "analytics": self.zelda_seo_analytics,
            "view_count": self.view_count
        }