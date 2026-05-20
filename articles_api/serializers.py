# articles_api/serializers.py
from rest_framework import serializers
from .models import ArticlePost, ArticleCategory

class ArticleCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleCategory
        fields = ['id', 'name', 'slug']


class ArticlePostSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = ArticlePost
        fields = [
            'id', 'author', 'author_username', 'category', 'category_name', 
            'title', 'slug', 'content_body', 'status', 'view_count', 
            'zelda_seo_analytics', 'created_at', 'updated_at'
        ]


class DraftArticlePayloadSerializer(serializers.Serializer):
    category_id = serializers.IntegerField(required=False, allow_null=True)
    title = serializers.CharField(required=True, min_length=5, max_length=255)
    content_body = serializers.CharField(required=True, min_length=20)
    submit_for_ai_review = serializers.BooleanField(default=False)