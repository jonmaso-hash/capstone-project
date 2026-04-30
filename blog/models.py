from django.db import models

def __str__(self):
        return self.name

class Article(models.Model):
    title = models.CharField(max_length=128)
    body = models.TextField()
    image = models.ImageField(upload_to='imgProject/')
    created_on = models.DateTimeField(auto_now_add=True)

    
    def __str__(self):
        return f'{self.title} -- {self.created_on}'
