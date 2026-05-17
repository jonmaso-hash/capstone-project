from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings

# Updated model names matching Interlink Foundry models
from .models import Application, InvestorApplication, Connection

# Verified Google GenAI unified pipeline integration
from matchmaking.services.ai_engine import generate_profile_embedding

# --- 1. AI VECTOR AUTOMATION ---

@receiver(post_save, sender=Application)
def update_founder_vector(sender, instance, created, **kwargs):
    """Automatically generates AI vectors for founders when profiles are saved."""
    # Logic: Only run if vector is missing and a description is present
    if not instance.description_vector and instance.description:
        vector = generate_profile_embedding(instance.description)
        
        # Guard against failed API calls or empty responses
        if vector:
            # .update() modifies the DB without triggering post_save recursively
            Application.objects.filter(pk=instance.pk).update(description_vector=vector)


@receiver(post_save, sender=InvestorApplication)
def update_investor_vector(sender, instance, created, **kwargs):
    """Automatically generates AI vectors for investors when profiles are saved."""
    if not instance.focus_vector and instance.investment_focus:
        vector = generate_profile_embedding(instance.investment_focus)
        
        if vector:
            InvestorApplication.objects.filter(pk=instance.pk).update(focus_vector=vector)


# --- 2. CONNECTION WORKFLOW AUTOMATION ---

@receiver(post_save, sender=Connection)
def handle_connection_lifecycle(sender, instance, created, **kwargs):
    """
    Automates the 'Brokerage' part of Interlink Foundry:
    1. Alert Admin when an intro is requested.
    2. Alert Investor when Admin approves the intro.
    """
    # Safe settings evaluation to ensure local development configurations don't throw Errors
    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
    admin_recipient = getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL)

    if created:
        # Step A: Notify the Admin that a lead database match was requested
        subject = f"🚀 New Intro Request: {instance.founder.company_name}"
        message = (
            f"Investor '{instance.investor.company_name}' has requested an intro to '{instance.founder.company_name}'.\n\n"
            f"Review/Approve in Admin: {site_url}/admin/matchmaking/connection/{instance.id}/change/"
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_recipient],
            fail_silently=True
        )

    else:
        # Step B: Check for 'APPROVED' status changes
        # Keeps from emailing the investor multiple times on edits
        if instance.status == 'APPROVED' and not getattr(instance, '_match_email_sent', False):
            send_investor_match_email(instance)
            # Flag instance state during request lifecycle
            instance._match_email_sent = True


def send_investor_match_email(instance):
    """Helper to send the validation match details to the investor."""
    # Fallback syntax handling missing investor names gracefully
    investor_name = getattr(instance.investor, 'full_name', None) or 'Investor Partner'
    
    subject = f"Intro Confirmed: {instance.founder.company_name}"
    message = (
        f"Hello {investor_name},\n\n"
        f"Your request to connect with {instance.founder.company_name} has been approved.\n\n"
        f"Founder: {instance.founder.founder_name}\n"
        f"Sector: {instance.founder.sector}\n"
        f"Contact: {instance.founder.email}\n\n"
        f"Best,\n"
        f"The Interlink Foundry Team"
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[instance.investor.email],
        fail_silently=True
    )