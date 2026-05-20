from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

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
    Ingests resume structures and passes text nodes to Zelda for real-time semantic alignment matching.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SubmitApplicationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        target_job = get_object_or_404(JobListing, id=serializer.validated_data['job_id'], is_active=True)
        resume_content = serializer.validated_data['raw_resume_text'].lower()
        
        # Zelda AI Matching Core Simulation Logic
        # Compares array keywords in the target description with candidate text tokens
        matched_tokens = []
        for skill in target_job.skills_required:
            if skill.lower() in resume_content:
                matched_tokens.append(skill)
                
        # Calculate mock vector similarity baseline
        total_skills = len(target_job.skills_required)
        sim_score = round((len(matched_tokens) / total_skills), 2) if total_skills > 0 else 0.50
        
        return Response({
            "status": "application_processed",
            "pipeline_routing_stage": "SCREENING",
            "position": target_job.title,
            "company": target_job.company_name,
            "zelda_vector_match_telemetry": {
                "fit_index_score": sim_score,
                "confidence_interval": "HIGH_MATCH_PROPOSAL" if sim_score >= 0.75 else "STANDARD_REVIEW",
                "intersecting_skill_vectors": matched_tokens,
                "automated_screening_recommendation": f"Candidate demonstrates {int(sim_score * 100)}% structural capability alignment with target core parameters."
            }
        }, status=status.HTTP_201_CREATED)