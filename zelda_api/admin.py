# zelda_api/admin.py
from django.contrib import admin
from .models import JobListing, JobApplication

@admin.register(JobListing)
class JobListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'company_name', 'location', 'job_type', 'experience_level', 'is_active', 'created_at')
    list_filter = ('is_active', 'job_type', 'experience_level', 'created_at')
    search_fields = ('title', 'company_name', 'description_text')
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = (
        ('Core Details', {
            'fields': ('posted_by', 'title', 'slug', 'company_name', 'location')
        }),
        ('Job Parameters', {
            'fields': ('job_type', 'experience_level', 'is_active')
        }),
        ('Content & Requirements', {
            'fields': ('description_text', 'skills_required')
        }),
    )


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ('get_applicant_username', 'get_job_title', 'current_stage', 'zelda_match_score', 'applied_at')
    list_filter = ('current_stage', 'applied_at')
    search_fields = ('applicant__username', 'job__title', 'cover_letter_text')
    readonly_fields = ('zelda_match_score', 'extracted_talent_profile', 'applied_at')

    @admin.display(ordering='applicant__username', description='Applicant')
    def get_applicant_username(self, obj):
        return obj.applicant.username

    @admin.display(ordering='job__title', description='Target Job')
    def get_job_title(self, obj):
        return obj.job.title