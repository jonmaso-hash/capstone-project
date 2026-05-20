from rest_framework import serializers
from .models import JobListing, JobApplication

class JobListingSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobListing
        fields = ['id', 'title', 'company_name', 'location', 'job_type', 'experience_level', 'description_text', 'skills_required', 'is_active', 'created_at']


class SubmitApplicationSerializer(serializers.Serializer):
    job_id = serializers.IntegerField(required=True)
    cover_letter = serializers.CharField(required=False, max_length=5000, allow_blank=True)
    resume_url = serializers.URLField(required=True)
    raw_resume_text = serializers.CharField(required=True, min_length=50, help_text="Extracted text payload for Zelda parsing.")