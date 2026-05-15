from django.db import models
from django.contrib.auth.models import User

class Article(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='articles', null=True, blank=True)
    title = models.CharField(max_length=128)
    company_name = models.CharField(max_length=128, blank=True, null=True) 
    body = models.TextField()
    image = models.ImageField(upload_to='imgProject/')
    created_on = models.DateTimeField(auto_now_add=True)
    likes = models.ManyToManyField(User, related_name='blog_likes', blank=True)
    favorites = models.ManyToManyField(User, related_name='favorite_articles', blank=True)

    def total_likes(self):
        return self.likes.count()

    def __str__(self):
        return f'{self.title} -- {self.created_on}'
    
class Comment(models.Model):
    article = models.ForeignKey('Article', on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField()
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Comment by {self.author} on {self.article}'