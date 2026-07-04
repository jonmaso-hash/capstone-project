from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse

class Article(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='articles', null=True, blank=True)
    title = models.CharField(max_length=200)
    company_name = models.CharField(max_length=128, blank=True, null=True) 
    body = models.TextField()
    image = models.ImageField(upload_to='imgProject/')
    created_on = models.DateTimeField(auto_now_add=True)
    likes = models.ManyToManyField(User, related_name='blog_likes', blank=True)
    favorites = models.ManyToManyField(User, related_name='favorite_articles', blank=True)
    views = models.PositiveIntegerField(default=0)

    def total_likes(self):
        return self.likes.count()

    def _author_settings(self):
        if not self.author:
            return None
        from usersettings.models import UserSettings
        return UserSettings.for_user(self.author)

    @property
    def likes_enabled(self):
        author_settings = self._author_settings()
        return author_settings.blog_likes_enabled if author_settings else True

    @property
    def comments_enabled(self):
        author_settings = self._author_settings()
        return author_settings.blog_comments_enabled if author_settings else True

    def get_absolute_url(self):
        return reverse('blog:article_detail', kwargs={'pk': self.pk})

    def __str__(self):
        return f'{self.title} -- {self.created_on}'
    
class Comment(models.Model):
    article = models.ForeignKey('Article', on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField()
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Comment by {self.author} on {self.article}'