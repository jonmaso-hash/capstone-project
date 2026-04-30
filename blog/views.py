from django.shortcuts import render
from .models import Article

def blog_view(request):
   all_articles = Article.objects.all()
   return render(request, 'blog/article.html', {'blog': all_articles})