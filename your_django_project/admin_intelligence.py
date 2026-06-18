# zelda_api/admin_intelligence.py
"""
Django Admin configuration for Zelda Intelligence Pipeline models.
Provides full management interface for documents, chunks, insights, and memos.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from .vector_models import DocumentSource, DocumentChunk, IntelligenceInsight, IntelligenceMemo


@admin.register(DocumentSource)
class DocumentSourceAdmin(admin.ModelAdmin):
    """Admin interface for uploaded documents."""
    
    list_display = [
        'filename_link',
        'document_type',
        'source_entity',
        'status_badge',
        'confidence_score',
        'chunk_count',
        'created_at_short',
    ]
    list_filter = [
        'status',
        'document_type',
        'created_at',
        'confidence_score',
    ]
    search_fields = [
        'filename',
        'source_entity',
        'uploaded_by__username',
    ]
    readonly_fields = [
        'created_at',
        'updated_at',
        'processed_at',
        'raw_text_preview',
        'intelligence_display',
    ]
    fieldsets = (
        ('Document Info', {
            'fields': ('filename', 'document_type', 'source_entity', 'uploaded_by')
        }),
        ('Processing Status', {
            'fields': ('status', 'error_message'),
            'classes': ('collapse',),
        }),
        ('Analysis Results', {
            'fields': (
                'confidence_score',
                'intelligence_rank',
                'total_pages',
                'total_word_count',
                'raw_text_preview',
            ),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'processed_at'),
            'classes': ('collapse',),
        }),
        ('Intelligence Summary', {
            'fields': ('intelligence_display',),
            'classes': ('collapse',),
        }),
    )
    
    ordering = ['-created_at']
    
    def filename_link(self, obj):
        """Link to view document details."""
        url = reverse('admin:zelda_api_documentsource_change', args=[obj.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.filename[:50]
        )
    filename_link.short_description = 'Document'
    
    def status_badge(self, obj):
        """Display status as a colored badge."""
        colors = {
            'ingested': '#99ccff',
            'chunking': '#ffcc99',
            'chunked': '#ccff99',
            'embedding': '#ffff99',
            'embedded': '#99ff99',
            'analyzing': '#ff99cc',
            'analyzed': '#99ccff',
            'error': '#ff6666',
        }
        color = colors.get(obj.status, '#cccccc')
        return format_html(
            '<span style="background-color: {}; padding: 3px 8px; border-radius: 3px; color: #333;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def chunk_count(self, obj):
        """Display number of chunks created."""
        return obj.chunks.count()
    chunk_count.short_description = 'Chunks'
    
    def created_at_short(self, obj):
        """Display creation date in short format."""
        return obj.created_at.strftime('%Y-%m-%d %H:%M')
    created_at_short.short_description = 'Created'
    
    def intelligence_display(self, obj):
        """Display intelligence pipeline summary."""
        chunks = obj.chunks.count()
        insights = obj.insights.count()
        has_memo = hasattr(obj, 'memo')
        
        summary = f"""
        <strong>Pipeline Progress:</strong><br>
        • Chunks: {chunks}<br>
        • Insights: {insights}<br>
        • Memo Generated: {'✓ Yes' if has_memo else '✗ No'}<br>
        <br>
        <strong>Quality Metrics:</strong><br>
        • Confidence Score: {obj.confidence_score:.1%}<br>
        • Intelligence Rank: {obj.intelligence_rank}<br>
        """
        
        return format_html(summary)
    intelligence_display.short_description = 'Intelligence Summary'


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    """Admin interface for document chunks."""
    
    list_display = [
        'chunk_id_short',
        'document_link',
        'page_number',
        'section_title',
        'token_count',
        'is_key_insight_badge',
        'relevance_score',
    ]
    list_filter = [
        'document__document_type',
        'is_key_insight',
        'relevance_score',
        'embedded_at',
    ]
    search_fields = [
        'raw_text',
        'section_title',
        'document__filename',
    ]
    readonly_fields = [
        'document',
        'chunk_index',
        'created_at',
        'embedded_at',
        'raw_text_display',
        'embedding_vector_display',
    ]
    fieldsets = (
        ('Chunk Location', {
            'fields': ('document', 'chunk_index', 'page_number', 'section_title')
        }),
        ('Content', {
            'fields': ('raw_text_display', 'token_count'),
        }),
        ('Intelligence', {
            'fields': ('is_key_insight', 'relevance_score'),
        }),
        ('Embeddings', {
            'fields': ('embedding_model', 'embedding_vector_display', 'embedded_at'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )
    
    ordering = ['document', 'chunk_index']
    
    def chunk_id_short(self, obj):
        """Display chunk ID."""
        return f"#{obj.chunk_index}"
    chunk_id_short.short_description = 'Chunk #'
    
    def document_link(self, obj):
        """Link to parent document."""
        url = reverse('admin:zelda_api_documentsource_change', args=[obj.document.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.document.filename[:30]
        )
    document_link.short_description = 'Document'
    
    def is_key_insight_badge(self, obj):
        """Display key insight status."""
        if obj.is_key_insight:
            return format_html('<span style="color: #ff6600;">★ Key</span>')
        return '—'
    is_key_insight_badge.short_description = 'Key Insight'
    
    def raw_text_display(self, obj):
        """Display text in readable format."""
        return format_html('<pre>{}</pre>', obj.raw_text[:500])
    raw_text_display.short_description = 'Text Preview'
    
    def embedding_vector_display(self, obj):
        """Display embedding vector info."""
        if obj.embedding_vector:
            return f"Vector of {len(obj.embedding_vector)} dimensions"
        return "No embedding yet"
    embedding_vector_display.short_description = 'Embedding'


@admin.register(IntelligenceInsight)
class IntelligenceInsightAdmin(admin.ModelAdmin):
    """Admin interface for extracted insights."""
    
    list_display = [
        'category',
        'insight_type_badge',
        'document_link',
        'confidence_badge',
        'source_count',
        'metric_display',
    ]
    list_filter = [
        'insight_type',
        'category',
        'confidence_score',
        'created_at',
    ]
    search_fields = [
        'insight_text',
        'category',
        'document__filename',
    ]
    readonly_fields = [
        'document',
        'created_at',
        'verified_at',
        'source_chunks_display',
    ]
    fieldsets = (
        ('Insight Info', {
            'fields': ('document', 'insight_type', 'category')
        }),
        ('Content', {
            'fields': ('insight_text', 'confidence_score'),
        }),
        ('Quantification', {
            'fields': ('metric_value', 'metric_unit', 'source_attribution'),
        }),
        ('Sources', {
            'fields': ('source_chunks_display',),
        }),
        ('Status', {
            'fields': ('created_at', 'verified_at'),
            'classes': ('collapse',),
        }),
    )
    
    ordering = ['-confidence_score', '-created_at']
    
    def insight_type_badge(self, obj):
        """Display insight type as badge."""
        colors = {
            'metric': '#66ccff',
            'trend': '#ffcc66',
            'risk': '#ff6666',
            'opportunity': '#66ff66',
            'statement': '#cccccc',
            'assumption': '#ffcccc',
            'recommendation': '#ccffcc',
        }
        color = colors.get(obj.insight_type, '#cccccc')
        return format_html(
            '<span style="background-color: {}; padding: 2px 6px; border-radius: 3px;">{}</span>',
            color,
            obj.get_insight_type_display()
        )
    insight_type_badge.short_description = 'Type'
    
    def document_link(self, obj):
        """Link to document."""
        url = reverse('admin:zelda_api_documentsource_change', args=[obj.document.id])
        return format_html('<a href="{}">{}</a>', url, obj.document.filename[:30])
    document_link.short_description = 'Document'
    
    def confidence_badge(self, obj):
        """Display confidence as visual badge."""
        if obj.confidence_score >= 0.8:
            color = '#66ff66'
        elif obj.confidence_score >= 0.6:
            color = '#ffff66'
        else:
            color = '#ff9999'
        return format_html(
            '<span style="background-color: {}; padding: 2px 6px; border-radius: 3px;">{:.0%}</span>',
            color,
            obj.confidence_score
        )
    confidence_badge.short_description = 'Confidence'
    
    def source_count(self, obj):
        """Count of source chunks."""
        return obj.source_chunks.count()
    source_count.short_description = 'Sources'
    
    def metric_display(self, obj):
        """Display metric if present."""
        if obj.metric_value:
            return f"{obj.metric_value} {obj.metric_unit}".strip()
        return '—'
    metric_display.short_description = 'Metric'
    
    def source_chunks_display(self, obj):
        """Display linked source chunks."""
        chunks = obj.source_chunks.all()
        if not chunks:
            return "No source chunks linked"
        
        links = []
        for chunk in chunks[:5]:
            url = reverse('admin:zelda_api_documentchunk_change', args=[chunk.id])
            links.append(f'<a href="{url}">Chunk #{chunk.chunk_index}</a>')
        
        text = ', '.join(links)
        if chunks.count() > 5:
            text += f" ... and {chunks.count() - 5} more"
        
        return format_html(text)
    source_chunks_display.short_description = 'Source Chunks'


@admin.register(IntelligenceMemo)
class IntelligenceMemoAdmin(admin.ModelAdmin):
    """Admin interface for intelligence memos."""
    
    list_display = [
        'document_link',
        'recommendation_badge',
        'completeness_score',
        'citations_count',
        'created_at_short',
    ]
    list_filter = [
        'recommendation',
        'completeness_score',
        'created_at',
    ]
    search_fields = [
        'document__filename',
        'executive_summary',
    ]
    readonly_fields = [
        'document',
        'created_at',
        'updated_at',
        'summary_preview',
        'insights_used_display',
    ]
    fieldsets = (
        ('Memo Info', {
            'fields': ('document', 'recommendation'),
        }),
        ('Executive Summary', {
            'fields': ('summary_preview',),
        }),
        ('Analysis Sections', {
            'fields': (
                'problem_solution',
                'market_analysis',
                'team_assessment',
                'financial_analysis',
                'risk_assessment',
                'investment_thesis',
            ),
            'classes': ('collapse',),
        }),
        ('Quality', {
            'fields': ('completeness_score', 'citations_count', 'insights_used_display'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    ordering = ['-created_at']
    
    def document_link(self, obj):
        """Link to document."""
        url = reverse('admin:zelda_api_documentsource_change', args=[obj.document.id])
        return format_html('<a href="{}">{}</a>', url, obj.document.filename[:30])
    document_link.short_description = 'Document'
    
    def recommendation_badge(self, obj):
        """Display recommendation as colored badge."""
        colors = {
            'strong_pass': '#ff6666',
            'pass': '#ff9999',
            'consider': '#ffff66',
            'interview': '#99ccff',
            'strong_interest': '#66ff66',
        }
        color = colors.get(obj.recommendation, '#cccccc')
        labels = {
            'strong_pass': '❌ Pass',
            'pass': '✗ Pass',
            'consider': '⚠ Consider',
            'interview': 'Interview',
            'strong_interest': '✓ Strong',
        }
        label = labels.get(obj.recommendation, obj.get_recommendation_display())
        
        return format_html(
            '<span style="background-color: {}; padding: 4px 8px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            label
        )
    recommendation_badge.short_description = 'Recommendation'
    
    def completeness_score(self, obj):
        """Format completeness score."""
        return f"{obj.completeness_score:.0%}"
    completeness_score.short_description = 'Completeness'
    
    def summary_preview(self, obj):
        """Preview of executive summary."""
        return format_html('<pre>{}</pre>', obj.executive_summary[:500])
    summary_preview.short_description = 'Executive Summary'
    
    def insights_used_display(self, obj):
        """Display insights used in memo."""
        insights = obj.insights_used.all()
        items = [f"• {i.category}: {i.insight_text[:50]}" for i in insights]
        return format_html('<br>'.join(items) if items else "No insights linked")
    insights_used_display.short_description = 'Insights Used'
    
    def created_at_short(self, obj):
        """Short date format."""
        return obj.created_at.strftime('%Y-%m-%d %H:%M')
    created_at_short.short_description = 'Created'