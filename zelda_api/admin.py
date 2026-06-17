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

# Try to import jobs models if available
try:
    from jobs_api.models import JobListing, JobApplication
except ImportError:
    JobListing = None
    JobApplication = None