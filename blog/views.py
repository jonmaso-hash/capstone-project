from django.shortcuts import render
from django.views.generic import(
    ListView,
    CreateView,
    DetailView,
    UpdateView,
    DeleteView,
)
from .models import Post, Status
from django.urls import reverse_lazy
from django.contrib.auth.mixins import(
    LoginRequiredMixin,
    UserPassesTestMixin
)

#create your views here:
class PostListView(ListView):
    model = Post
    template_name = 'blog/list.html'
    

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            context['published_status'] = Status.objects.get(name="published")
        except Status.DoesNotExist:
            context['published_status'] = None
            
        return context

class PostDraftListView(LoginRequiredMixin, ListView):
    template_name = "posts/draft.html"
    context_object_name = "drafts"

    def get_queryset(self):
        try:
            draft_status = Status.objects.get(name="draft")
            return Post.objects.filter(status=draft_status).order_by("-created_on")
        except Status.DoesNotExist:
            return Post.objects.none()

class PostArchivedListView(LoginRequiredMixin, ListView):
    template_name = "posts/archived.html"
    context_object_name = "archives"

    def get_queryset(self):
        try:
            archived_status = Status.objects.get(name="archived")
            return Post.objects.filter(status=archived_status).order_by("-created_on")
        except Status.DoesNotExist:
            return Post.objects.none()



class PostCreateView(LoginRequiredMixin, CreateView):
    template_name = 'posts/new.html'
    model = Post
    fields = ["title", 'subtitle', 'body', 'status']

    def form_valid(self, form):
        form.instance.author=self.request.user
        return super().form_valid(form)

class PostDetailView(LoginRequiredMixin, DetailView): 
    template_name = "posts/detail.html"
    model = Post
    context_object_name = "post"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        print(context)
        return context


class PostUpdateView(LoginRequiredMixin,UserPassesTestMixin, UpdateView): 
    template_name = "posts/edit.html"
    model = Post
    fields = ["title", "subtitle", "body", "status"]

    def test_func(self):
        post = self.get_object()
        if self.request.user.is_authenticated:
            if self.request.user == post.author:
                return True
            else:
                return False
        else:
                return False


class PostDeleteView(LoginRequiredMixin,UserPassesTestMixin, DeleteView):
    model = Post
    template_name = "posts/delete.html"
    success_url = reverse_lazy("post_list")

    def test_func(self):
        post = self.get_object()
        if self.request.user.is_authenticated:
            if self.request.user == post.author:
                return True
            else:
                return False
        else:
                return False
        
