from django.db.models.signals import post_delete
from django.dispatch import receiver
from shared_utils.file_cleanup import delete_file_field
from .models import Article


@receiver(post_delete, sender=Article)
def delete_article_image_from_storage(sender, instance, **kwargs):
    delete_file_field(instance, 'image')
