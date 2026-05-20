from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Article, Comment
from .forms import ArticleUploadForm

def blog_view(request):
    if request.method == 'POST':
        if request.user.is_authenticated:
            form = ArticleUploadForm(request.POST, request.FILES)
            if form.is_valid():
                article = form.save(commit=False)
                article.author = request.user
                article.save()
                return redirect('blog:blog_view') # Fixed namespace
        else:
            return redirect('accounts:login') # Fixed namespace
    else:
        form = ArticleUploadForm()

    # Capture the sorting query string parameter
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
            return redirect('blog:blog_view') # Fixed namespace
    else:
        form = ArticleUploadForm(instance=article)
        
    return render(request, 'blog/edit_article.html', {'form': form, 'article': article})

@login_required
def delete_article(request, pk):
    article = get_object_or_404(Article, pk=pk, author=request.user)
    if request.method == "POST":
        article.delete()
        return redirect('blog:blog_view') # Fixed namespace
        
    return render(request, 'blog/delete_confirm.html', {'article': article})

def add_comment(request, pk):
    article = get_object_or_404(Article, pk=pk)
    if request.method == "POST" and request.user.is_authenticated:
        body = request.POST.get('body')
        if body:
            Comment.objects.create(article=article, author=request.user, body=body)
    return redirect('blog:blog_view') # Fixed namespace

def like_article(request, pk):
    article = get_object_or_404(Article, pk=pk) # Fixed id to pk lookup
    if article.likes.filter(id=request.user.id).exists():
        article.likes.remove(request.user)
    else:
        article.likes.add(request.user)
    return redirect('blog:blog_view') # Fixed namespace

@login_required
def favorites_list(request):
    # This filters by articles the user explicitly favorited
    favorite_posts = Article.objects.filter(favorites=request.user).order_by('-created_on')
    return render(request, 'blog/favorites.html', {'favorite_posts': favorite_posts})

def article_detail(request, pk):
    article = get_object_or_404(Article, pk=pk)
    return render(request, 'blog/article_detail.html', {'article': article})

@login_required
def toggle_favorite(request, pk):
    article = get_object_or_404(Article, pk=pk)
    if article.favorites.filter(id=request.user.id).exists():
        article.favorites.remove(request.user)
    else:
        article.favorites.add(request.user)
    return redirect('blog:article_detail', pk=pk) # Fixed namespace