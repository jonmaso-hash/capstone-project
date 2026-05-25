from django.contrib import admin
from .models import JobListing, JobApplication

@admin.register(JobListing)
class JobListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'company_name', 'job_type', 'experience_level', 'is_active', 'created_at')
    list_filter = ('is_active', 'job_type', 'experience_level')
    search_fields = ('title', 'company_name', 'skills_required')
    ordering = ('-created_at',)

@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'job', 'current_stage', 'zelda_match_score', 'applied_at')
    list_filter = ('current_stage', 'applied_at')
    search_fields = ('applicant__username', 'job__title')
    readonly_fields = ('applied_at', 'zelda_match_score')
    ordering = ('-applied_at',)