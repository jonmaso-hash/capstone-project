from django.db.models.signals import post_delete
from django.dispatch import receiver
from shared_utils.file_cleanup import delete_file_field
from .models import JobApplication


@receiver(post_delete, sender=JobApplication)
def delete_resume_attachment_from_storage(sender, instance, **kwargs):
    delete_file_field(instance, 'resume_attachment')
