
from django.urls import path
from .views import JobBoardFeedAPIView, ApplyToJobAPIView

app_name = 'jobs_api'

urlpatterns = [
    # General job exploration feed route
    path('listings/', JobBoardFeedAPIView.as_view(), name='job_feed'),
    
    # Live ingestion entry point for applicant submissions
    path('apply/', ApplyToJobAPIView.as_view(), name='job_apply'),
]