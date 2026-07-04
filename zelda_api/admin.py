# zelda_api/admin.py
"""
Django Admin Configuration for Zelda API
"""
from django.contrib import admin

# Import intelligent models admin (already registered via decorator)
from .admin_intelligence import (  # noqa: F401
    DocumentSourceAdmin,
    DocumentChunkAdmin,
    IntelligenceInsightAdmin,
    IntelligenceMemoAdmin,
)

