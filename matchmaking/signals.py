from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings

# Updated model names to match our clean models.py
from .models import Application, InvestorApplication, Connection
from .services.ai_engine import generate_vector

# --- 1. AI VECTOR AUTOMATION ---

@receiver(post_save, sender=Application)
def update_founder_vector(sender, instance, created, **kwargs):
    """Automatically generates AI vectors for founders when profiles are saved."""
    # Logic: Only run if vector is missing or description changed
    if not instance.description_vector and instance.description:
        vector = generate_vector(instance.description)
        # .update() is key here: it prevents an infinite post_save loop
        Application.objects.filter(pk=instance.pk).update(description_vector=vector)

@receiver(post_save, sender=InvestorApplication)
def update_investor_vector(sender, instance, created, **kwargs):
    """Automatically generates AI vectors for investors when profiles are saved."""
    if not instance.focus_vector and instance.investment_focus:
        vector = generate_vector(instance.investment_focus)
        InvestorApplication.objects.filter(pk=instance.pk).update(focus_vector=vector)


# --- 2. CONNECTION WORKFLOW AUTOMATION ---

@receiver(post_save, sender=Connection)
def handle_connection_lifecycle(sender, instance, created, **kwargs):
    """
    Automates the 'Brokerage' part of Interlink Foundry:
    1. Alert Admin when an intro is requested.
    2. Alert Investor when Admin approves the intro.
    """
    if created:
        # Step A: Notify the Admin (You) that a lead was generated
        subject = f"🚀 New Intro Request: {instance.founder.company_name}"
        message = (
            f"Investor {instance.investor.company_name} has requested an intro to {instance.founder.company_name}.\n\n"
            f"Review/Approve in Admin: {settings.SITE_URL}/admin/matchmaking/connection/{instance.id}/change/"
        )
        # Using fail_silently=True so a bad email config doesn't crash your whole app
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [settings.ADMIN_EMAIL], fail_silently=True)

    else:
        # Step B: Check for 'APPROVED' status (The Handshake)
        # Note: 'APPROVED' must match the STATUS_CHOICES in models.py
        if instance.status == 'APPROVED':
            send_investor_match_email(instance)

def send_investor_match_email(instance):
    """Helper to send the pitch details to the investor."""
    subject = f"Intro Confirmed: {instance.founder.company_name}"
    message = (
        f"Hello {instance.investor.full_name or 'there'},\n\n"
        f"Your request to connect with {instance.founder.company_name} has been approved.\n\n"
        f"Founder: {instance.founder.founder_name}\n"
        f"Sector: {instance.founder.sector}\n"
        f"Contact: {instance.founder.email}\n\n"
        f"Best,\nThe Interlink Foundry Team"
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [instance.investor.email], fail_silently=True)