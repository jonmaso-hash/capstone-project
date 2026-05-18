from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from .models import JobListing, JobApplication

class JobListView(ListView):
    model = JobListing
    template_name = 'jobs/job_list.html'
    context_object_name = 'jobs'
    paginate_by = 10

    def get_queryset(self):
        # Only fetch unexpired, active job roles
        return JobListing.objects.filter(is_active=True, expires_at__gt=timezone.now())

class JobDetailView(DetailView):
    model = JobListing
    template_name = 'jobs/job_detail.html'
    context_object_name = 'job'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            # Check if current user already submitted an application
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
        # Automatically assign the poster to the current log-in session user
        form.instance.poster = self.request.user
        return super().form_valid(form)

class JobApplyView(LoginRequiredMixin, View):
    def post(self, request, pk):
        job = get_object_or_404(JobListing, pk=pk, is_active=True)
        cover_letter = request.POST.get('cover_letter', '')
        resume = request.FILES.get('resume_attachment')

        # Prevent duplicate submissions safely
        JobApplication.objects.get_or_create(
            job=job,
            applicant=request.user,
            defaults={
                'cover_letter': cover_letter,
                'resume_attachment': resume
            }
        )
        return redirect('jobs:detail', pk=pk)