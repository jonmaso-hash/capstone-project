from django.db import models
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from .models import Article, Comment
from .forms import ArticleUploadForm
from notifications.models import Notification

def blog_view(request):
    if request.method == 'POST':
        if request.user.is_authenticated:
            form = ArticleUploadForm(request.POST, request.FILES)
            if form.is_valid():
                article = form.save(commit=False)
                article.author = request.user
                article.save()
                return redirect('blog:blog_view')
        else:
            return redirect('accounts:login')
    else:
        form = ArticleUploadForm()

    sort_by = request.GET.get('sort', 'newest')

    if sort_by == 'oldest':
        all_articles = Article.objects.all().order_by('created_on')
    else:
        all_articles = Article.objects.all().order_by('-created_on')
    
    context = {
        'blog': all_articles, 
        'form': form,
        'current_sort': sort_by
    }
    return render(request, 'blog/article.html', context)

@login_required
def edit_article(request, pk):
    article = get_object_or_404(Article, pk=pk, author=request.user)
    if request.method == "POST":
        form = ArticleUploadForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            form.save()
            return redirect('blog:blog_view')
    else:
        form = ArticleUploadForm(instance=article)
        
    return render(request, 'blog/edit_article.html', {'form': form, 'article': article})

@login_required
def delete_article(request, pk):
    article = get_object_or_404(Article, pk=pk, author=request.user)
    if request.method == "POST":
        article.delete()
        return redirect('blog:blog_view')
        
    return render(request, 'blog/delete_confirm.html', {'article': article})

def add_comment(request, pk):
    article = get_object_or_404(Article, pk=pk)
    if request.method == "POST" and request.user.is_authenticated:
        body = request.POST.get('body')
        if body and article.comments_enabled:
            Comment.objects.create(article=article, author=request.user, body=body)
    return redirect('blog:blog_view')

@login_required # Added to prevent anonymous user errors when liking
def like_article(request, pk):
    article = get_object_or_404(Article, pk=pk)

    if article.likes.filter(id=request.user.id).exists():
        article.likes.remove(request.user)
    elif article.likes_enabled:
        article.likes.add(request.user)
        # CONSOLIDATED LOGIC: Trigger notification only on "Like" (not unlike)
        if article.author != request.user:
            try:
                Notification.objects.create(
                    recipient=article.author, 
                    sender=request.user, 
                    notification_type='LIKE', 
                    message=f"{request.user.username} liked your post: {article.title}", 
                    target_url=article.get_absolute_url()
                )
            except Exception as e:
                print(f"CRITICAL ERROR creating notification: {e}")
                
    return redirect('blog:blog_view')

@login_required
def favorites_list(request):
    favorite_posts = Article.objects.filter(favorites=request.user).order_by('-created_on')
    return render(request, 'blog/favorites.html', {'favorite_posts': favorite_posts})

def article_detail(request, pk):
    article = get_object_or_404(Article, pk=pk)
    Article.objects.filter(pk=pk).update(views=models.F('views') + 1)
    article.refresh_from_db(fields=['views'])
    return render(request, 'blog/article_detail.html', {'article': article})

@login_required
def toggle_favorite(request, pk):
    article = get_object_or_404(Article, pk=pk)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if article.favorites.filter(id=request.user.id).exists():
        article.favorites.remove(request.user)
    elif article.likes_enabled:
        article.favorites.add(request.user)
        # CONSOLIDATED LOGIC: Trigger notification only on "Favorite" (not unfavorite)
        if article.author != request.user:
            try:
                Notification.objects.create(
                    recipient=article.author,
                    sender=request.user,
                    notification_type='FAVORITE', # Updated type to differentiate from LIKE
                    message=f"{request.user.username} favorited your post: {article.title}",
                    target_url=article.get_absolute_url()
                )
            except Exception as e:
                print(f"CRITICAL ERROR creating notification: {e}")

    if is_ajax:
        return JsonResponse({
            'status': 'success',
            'is_favorited': article.favorites.filter(id=request.user.id).exists(),
            'count': article.favorites.count(),
        })

    return redirect('blog:article_detail', pk=pk)

@login_required
def toggle_comment_like(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if comment.likes.filter(id=request.user.id).exists():
        comment.likes.remove(request.user)
    else:
        comment.likes.add(request.user)

    if is_ajax:
        return JsonResponse({
            'status': 'success',
            'is_liked': comment.likes.filter(id=request.user.id).exists(),
            'count': comment.total_likes(),
        })

    return redirect('blog:article_detail', pk=comment.article.pk)