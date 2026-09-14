import os

from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, View
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Case, When, Value, BooleanField
from shared_utils.upload_limits import MB, RESUME_MAX_MB
from .models import JobListing, JobApplication
from django.db import models

# The bytes each accepted resume format starts with, so a renamed file is refused.
RESUME_SIGNATURES = {
    'pdf': b'%PDF-',
    'docx': b'PK\x03\x04',                      # a zip container
    'doc': b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1',  # an OLE compound document
}


def _resume_problem(resume):
    """Why this resume can't be accepted, or None. Size first, so nothing reads an oversized file."""
    if resume.size > RESUME_MAX_MB * MB:
        return f"Your resume is too large. The limit is {RESUME_MAX_MB} MB."
    signature = RESUME_SIGNATURES.get(os.path.splitext(resume.name)[1].lower().lstrip('.'))
    if signature is None:
        return "Your resume must be a PDF, DOC or DOCX file."
    head = resume.read(len(signature))
    resume.seek(0)
    if head != signature:
        return "Your resume doesn't look like the PDF, DOC or DOCX file its name says it is."
    return None


class JobListView(ListView):
    model = JobListing
    template_name = 'jobs/job_list.html'
    context_object_name = 'jobs'
    paginate_by = 20

    def get_queryset(self):
        # Founder Premium's monthly highlight (see matchmaking.models.
        # Application.is_highlighted) sorts highlighted posters' jobs first,
        # ahead of the model's default -is_featured/-created_at ordering —
        # annotated at the DB level so it stays correct under pagination.
        from matchmaking.models import HIGHLIGHT_DURATION
        highlight_cutoff = timezone.now() - HIGHLIGHT_DURATION
        qs = JobListing.objects.filter(
            is_active=True,
            expires_at__gt=timezone.now()
        ).annotate(
            poster_is_highlighted=Case(
                When(poster__match_founder_profile__last_highlight_at__gte=highlight_cutoff, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            )
        )

        q = self.request.GET.get('q', '').strip()
        job_type = self.request.GET.get('job_type', '').strip()
        location = self.request.GET.get('location', '').strip()

        if q:
            qs = qs.filter(
                models.Q(title__icontains=q) |
                models.Q(company_name__icontains=q) |
                models.Q(description__icontains=q)
            )
        if job_type:
            qs = qs.filter(job_type=job_type)
        if location:
            qs = qs.filter(location__icontains=location)

        return qs.order_by('-poster_is_highlighted', '-is_featured', '-created_at')

class JobDetailView(DetailView):
    model = JobListing
    template_name = 'jobs/job_detail.html'
    context_object_name = 'job'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Skip the poster viewing their own listing — matches the pattern used
        # for pitch deck/video telemetry, where owner self-views aren't interest.
        if not self.request.user.is_authenticated or self.request.user != self.object.poster:
            JobListing.objects.filter(pk=self.object.pk).update(click_count=models.F('click_count') + 1)
            self.object.refresh_from_db(fields=['click_count'])
        if self.request.user.is_authenticated:
            context['already_applied'] = JobApplication.objects.filter(
                job=self.object, applicant=self.request.user
            ).exists()
        return context

class JobCreateView(LoginRequiredMixin, CreateView):
    model = JobListing
    fields = ['company_name', 'title', 'job_type', 'location', 'salary_range', 'equity_range', 'description']
    template_name = 'jobs/job_form.html'
    success_url = reverse_lazy('jobs:index')

    def form_valid(self, form):
        # Assign the poster to the current user
        form.instance.poster = self.request.user
        return super().form_valid(form)

class JobApplyView(LoginRequiredMixin, View):
    def post(self, request, pk):
        job = get_object_or_404(JobListing, pk=pk, is_active=True)
        resume = request.FILES.get('resume_attachment')
        problem = _resume_problem(resume) if resume else None
        if problem:
            messages.error(request, problem)
            return redirect('jobs:detail', pk=pk)
        # Prevent duplicate submissions
        JobApplication.objects.get_or_create(
            job=job,
            applicant=request.user,
            defaults={
                'cover_letter': request.POST.get('cover_letter', ''),
                'resume_attachment': resume
            }
        )
        return redirect('jobs:detail', pk=pk)