
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Article, Comment
from .forms import ArticleUploadForm

def blog_view(request):
    """
    Handles displaying the blog feed and processing new article submissions.
    """
    if request.method == 'POST':
        if request.user.is_authenticated:
            form = ArticleUploadForm(request.POST, request.FILES)
            if form.is_valid():
                article = form.save(commit=False)
                article.author = request.user
                article.save()
                return redirect('blog_view')
        else:
            # Redirect unauthenticated users trying to POST to login
            return redirect('login')
    else:
        form = ArticleUploadForm()

    # Order by newest first
    all_articles = Article.objects.all().order_by('-created_on')
    
    context = {
        'blog': all_articles, 
        'form': form
    }
    return render(request, 'blog/article.html', context)

@login_required
def edit_article(request, pk):
    """
    Allows the author to update an existing article.
    """
    # author=request.user ensures only the owner can access this specific object
    article = get_object_or_404(Article, pk=pk, author=request.user)
    
    if request.method == "POST":
        form = ArticleUploadForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            form.save()
            return redirect('blog_view')
    else:
        form = ArticleUploadForm(instance=article)
        
    return render(request, 'blog/edit_article.html', {
        'form': form, 
        'article': article
    })

@login_required
def delete_article(request, pk):
    """
    Allows the author to delete their article after a POST confirmation.
    """
    article = get_object_or_404(Article, pk=pk, author=request.user)
    
    if request.method == "POST":
        article.delete()
        return redirect('blog_view')
        
    return render(request, 'blog/delete_confirm.html', {'article': article})

def add_comment(request, pk):
    article = get_object_or_404(Article, pk=pk)
    if request.method == "POST" and request.user.is_authenticated:
        body = request.POST.get('body')
        if body:
            Comment.objects.create(article=article, author=request.user, body=body)
    # Change this line here:
    return redirect('blog_view')

def like_article(request, pk):
    article = get_object_or_404(Article, id=pk)
    if article.likes.filter(id=request.user.id).exists():
        article.likes.remove(request.user)
    else:
        article.likes.add(request.user)
    return redirect('blog_view') 

@login_required
def favorites_list(request):
    # This fetches only articles where the current user is in the 'likes' field
    favorite_posts = Article.objects.filter(likes=request.user).order_by('-created_on')
    
    return render(request, 'blog/favorites.html', {'favorite_posts': favorite_posts})

def article_detail(request, pk):
    # This fetches the specific article by its ID (pk)
    # or returns a 404 error if it doesn't exist
    article = get_object_or_404(Article, pk=pk)
    
    context = {
        'article': article,
    }
    return render(request, 'blog/article_detail.html', context)

@login_required
def toggle_favorite(request, pk):
    article = get_object_or_404(Article, pk=pk)
    if article.favorites.filter(id=request.user.id).exists():
        article.favorites.remove(request.user)
    else:
        article.favorites.add(request.user)
    return redirect('article_detail', pk=pk)