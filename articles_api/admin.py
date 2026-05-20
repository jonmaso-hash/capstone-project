# articles_api/admin.py
from django.contrib import admin
from .models import ArticleCategory, ArticlePost

@admin.register(ArticleCategory)
class ArticleCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ArticlePost)
class ArticlePostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'category', 'status', 'view_count', 'created_at')
    list_filter = ('status', 'category', 'created_at')
    search_fields = ('title', 'content_body', 'author__username')
    prepopulated_fields = {'slug': ('title',)}
    ordering = ('-created_at',)