from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction

from .models import JobListing, JobApplication
from .serializers import JobListingSerializer, SubmitApplicationSerializer

class JobBoardFeedAPIView(APIView):
    """
    GET /api/v1/jobs/listings/
    Returns a filterable catalog of all active operational job openings.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        listings = JobListing.objects.filter(is_active=True)
        
        # Quick query filter overlays
        exp = request.query_params.get('experience')
        if exp:
            listings = listings.filter(experience_level__iexact=exp)
            
        serializer = JobListingSerializer(listings, many=True)
        return Response({
            "status": "success",
            "active_postings_count": listings.count(),
            "jobs": serializer.data
        }, status=status.HTTP_200_OK)


class ApplyToJobAPIView(APIView):
    """
    POST /api/v1/jobs/apply/
    Ingests resume structures, checks idempotency, passes text nodes to Zelda for matching, 
    and securely persists the application to the database.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = SubmitApplicationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        job_id = serializer.validated_data['job_id']
        target_job = get_object_or_404(JobListing, id=job_id, is_active=True)
        
        # PINNACLE UPGRADE: Business Logic Idempotency
        # Prevent the user from applying to the exact same job twice.
        existing_app = JobApplication.objects.filter(job=target_job, applicant=request.user).first()
        if existing_app:
            return Response({
                "status": "already_applied",
                "message": "You have already submitted an application for this position.",
                "zelda_match_score": existing_app.zelda_match_score
            }, status=status.HTTP_200_OK)

        resume_content = serializer.validated_data['raw_resume_text'].lower()
        
        # Zelda AI Matching Core Simulation Logic
        matched_tokens = []
        for skill in target_job.skills_required:
            if skill.lower() in resume_content:
                matched_tokens.append(skill)
                
        # Calculate mock vector similarity baseline
        total_skills = len(target_job.skills_required)
        sim_score = round((len(matched_tokens) / total_skills), 2) if total_skills > 0 else 0.50
        
        # PINNACLE UPGRADE: Database Persistence
        # We must actually create the record in the database so it appears in admin.py
        application = JobApplication.objects.create(
            job=target_job,
            applicant=request.user,
            cover_letter_text=serializer.validated_data.get('cover_letter', ''),
            resume_file_url=serializer.validated_data['resume_url'],
            current_stage='screening',
            zelda_match_score=sim_score,
            extracted_talent_profile={"matched_vectors": matched_tokens}
        )
        
        return Response({
            "status": "application_processed",
            "pipeline_routing_stage": application.current_stage,
            "application_id": application.id,
            "position": target_job.title,
            "company": target_job.company_name,
            "zelda_vector_match_telemetry": {
                "fit_index_score": sim_score,
                "confidence_interval": "HIGH_MATCH_PROPOSAL" if sim_score >= 0.75 else "STANDARD_REVIEW",
                "intersecting_skill_vectors": matched_tokens,
                "automated_screening_recommendation": f"Candidate demonstrates {int(sim_score * 100)}% structural capability alignment with target core parameters."
            }
        }, status=status.HTTP_201_CREATED)