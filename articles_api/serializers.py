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
    
    # Pinnacle enforcement
    foundry_envelope = serializers.SerializerMethodField()

    class Meta:
        model = ArticlePost
        fields = [
            'id', 'author', 'author_username', 'category', 'category_name', 
            'title', 'slug', 'status', 'view_count', 'foundry_envelope',
            'created_at', 'updated_at'
            # Note: content_body removed from default list to keep payload light, 
            # it can be fetched via detail view if needed.
        ]

    def get_foundry_envelope(self, obj):
        return obj.to_foundry_envelope()

class DraftArticlePayloadSerializer(serializers.Serializer):
    # (Remains unchanged from original as it's an input validator)
    category_id = serializers.IntegerField(required=False, allow_null=True)
    title = serializers.CharField(required=True, min_length=5, max_length=255)
    content_body = serializers.CharField(required=True, min_length=20)
    submit_for_ai_review = serializers.BooleanField(default=False)