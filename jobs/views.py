from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Case, When, Value, BooleanField
from .models import JobListing, JobApplication
from django.db import models

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
        # Prevent duplicate submissions
        JobApplication.objects.get_or_create(
            job=job,
            applicant=request.user,
            defaults={
                'cover_letter': request.POST.get('cover_letter', ''),
                'resume_attachment': request.FILES.get('resume_attachment')
            }
        )
        return redirect('jobs:detail', pk=pk)