# articles_api/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import ArticlePost, ArticleCategory
from .serializers import ArticlePostSerializer, DraftArticlePayloadSerializer


class PublicArticleFeedAPIView(APIView):
    """
    GET /api/v1/content/articles/
    Returns a list of live, published articles with category slug filtering overlays.
    """
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        articles = ArticlePost.objects.filter(status='published')
        
        category_slug = request.query_params.get('category')
        if category_slug:
            articles = articles.filter(category__slug=category_slug)
            
        serializer = ArticlePostSerializer(articles, many=True)
        return Response({
            "status": "success",
            "published_articles_count": articles.count(),
            "articles": serializer.data
        }, status=status.HTTP_200_OK)


class CreateArticleAPIView(APIView):
    """
    POST /api/v1/content/articles/create/
    Ingests raw copy text, pushing structural blocks to Zelda for automated tags and summaries.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DraftArticlePayloadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        category_obj = None
        cat_id = serializer.validated_data.get('category_id')
        if cat_id:
            category_obj = get_object_or_404(ArticleCategory, id=cat_id)
            
        title_text = serializer.validated_data['title']
        body_text = serializer.validated_data['content_body']
        ai_review_requested = serializer.validated_data['submit_for_ai_review']
        
        word_count = len(body_text.split())
        estimated_read_time_mins = max(1, round(word_count / 200))
        
        zelda_seo_block = {
            "seo_meta_title": f"{title_text} | Interlink Insights",
            "seo_meta_description": body_text[:155].strip() + "...",
            "readability_index": "EXCELLENT_FLESCH_KINCADE" if word_count > 300 else "SHORT_FORM_POST",
            "content_telemetry": {
                "total_word_count": word_count,
                "estimated_minutes_to_read": estimated_read_time_mins
            },
            "suggested_tags": ["Venture Capital", "Startup Ecosystem", "Tech Innovation"]
        }
        
        target_status = 'review' if ai_review_requested else 'draft'
        
        return Response({
            "status": "content_staged",
            "current_workflow_state": target_status.upper(),
            "article_manifest": {
                "author_identity": request.user.username,
                "assigned_category": category_obj.name if category_obj else "Uncategorized"
            },
            "zelda_automated_seo_enrichment": zelda_seo_block
        }, status=status.HTTP_201_CREATED)