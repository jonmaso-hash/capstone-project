from django.db import connection
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import (
    Application, InvestorApplication, Connection, DataRoomDocument, Document,
    SellerApplication, FounderMilestone, founder_description_meets_word_count,
)
from matchmaking.services.ai_engine import generate_profile_embedding
from shared_utils.file_cleanup import delete_file_field

# --- 1. AI VECTOR AUTOMATION ---

@receiver(post_save, sender=Application)
def update_founder_vector(sender, instance, created, **kwargs):
    """Automatically generates AI vectors for founders when profiles are saved."""
    # Logic: Only run if vector is missing and the description clears the
    # minimum word count (see founder_description_meets_word_count) — this
    # is the one gate that determines "profile complete" everywhere it's read.
    description_vector = None
    if not instance.description_vector and founder_description_meets_word_count(instance.description):
        description_vector = generate_profile_embedding(instance.description)

        # Guard against failed API calls or empty responses
        if description_vector:
            # .update() modifies the DB without triggering post_save recursively
            Application.objects.filter(pk=instance.pk).update(description_vector=description_vector)

    # Multi-vector chunking backfill — same lazy, one-field-at-a-time
    # pattern as description_vector above, just repeated per chunk. Additive:
    # description_vector keeps being generated/used exactly as before.
    chunk_updates = {}
    if not instance.problem_solution_vector and instance.description:
        # extra_info folded in here — it's additional "about the company"
        # narrative in the same spirit as description, and previously fed
        # no vector at all despite being a VECTOR_FIELDS member.
        problem_solution_text = instance.description
        if instance.extra_info:
            problem_solution_text = f"{problem_solution_text} {instance.extra_info}"
        chunk_vector = generate_profile_embedding(problem_solution_text)
        if chunk_vector:
            chunk_updates['problem_solution_vector'] = chunk_vector

    if not instance.capital_plan_vector and instance.reason_for_capital:
        # Burn rate and prior amount raised folded in as descriptive text —
        # both are capital-plan-relevant numbers that previously had no
        # semantic representation, so an investor's capital-focused thesis
        # language couldn't match against them at all.
        capital_plan_text = instance.reason_for_capital
        capital_context = []
        if instance.monthly_burn_rate:
            capital_context.append(f"Burns approximately ${instance.monthly_burn_rate:,.0f} per month.")
        if instance.prior_amount_raised:
            capital_context.append(f"Has raised ${instance.prior_amount_raised:,.0f} prior to this round.")
        if capital_context:
            capital_plan_text = f"{capital_plan_text} {' '.join(capital_context)}"
        chunk_vector = generate_profile_embedding(capital_plan_text)
        if chunk_vector:
            chunk_updates['capital_plan_vector'] = chunk_vector

    market_context_text = ' '.join(filter(None, [instance.sector, instance.stage, instance.geography]))
    if not instance.market_context_vector and market_context_text.strip():
        chunk_vector = generate_profile_embedding(market_context_text)
        if chunk_vector:
            chunk_updates['market_context_vector'] = chunk_vector

    if chunk_updates:
        Application.objects.filter(pk=instance.pk).update(**chunk_updates)

    # Postgres-only ANN shadow column backfill — see
    # Application.description_vector_pg's docstring. The field only exists
    # as a real column on Postgres (migration 0049), so this must never run
    # on SQLite/other backends. Reuses the embedding computed above when
    # available (same local model, same dimensionality — no separate
    # reduced-size call needed).
    if connection.vendor == 'postgresql' and not instance.description_vector_pg and founder_description_meets_word_count(instance.description):
        pg_vector = description_vector if description_vector is not None else generate_profile_embedding(instance.description)
        if pg_vector:
            Application.objects.filter(pk=instance.pk).update(description_vector_pg=pg_vector)

    # description_vector is the field AIMatch scores against — a fresh one
    # means every cached match for this founder is now stale. Async so the
    # profile-save request never blocks on scanning every investor.
    if description_vector:
        from .tasks import refresh_matches_for_founder_task
        refresh_matches_for_founder_task.delay(instance.pk, "Founder updated their profile")


@receiver(post_save, sender=InvestorApplication)
def update_investor_vector(sender, instance, created, **kwargs):
    """Automatically generates AI vectors for investors when profiles are saved."""
    focus_vector = None
    if not instance.focus_vector and instance.investment_focus:
        focus_vector = generate_profile_embedding(instance.investment_focus)

        if focus_vector:
            InvestorApplication.objects.filter(pk=instance.pk).update(focus_vector=focus_vector)

    # Multi-vector chunking backfill (see update_founder_vector above for
    # the same pattern). thesis_vector falls back to investment_focus when
    # investment_thesis_summary is blank, since that field is optional.
    if not instance.thesis_vector:
        thesis_text = instance.investment_thesis_summary or instance.investment_focus
        if thesis_text:
            chunk_vector = generate_profile_embedding(thesis_text)
            if chunk_vector:
                InvestorApplication.objects.filter(pk=instance.pk).update(thesis_vector=chunk_vector)

    # Postgres-only ANN shadow column backfill — see update_founder_vector above.
    if connection.vendor == 'postgresql' and not instance.focus_vector_pg and instance.investment_focus:
        pg_vector = focus_vector if focus_vector is not None else generate_profile_embedding(instance.investment_focus)
        if pg_vector:
            InvestorApplication.objects.filter(pk=instance.pk).update(focus_vector_pg=pg_vector)

    # Same reasoning as update_founder_vector above — a fresh focus_vector
    # means every cached match for this investor is now stale.
    if focus_vector:
        from .tasks import refresh_matches_for_investor_task
        refresh_matches_for_investor_task.delay(instance.pk, "Investor updated their thesis")


@receiver(post_save, sender=FounderMilestone)
def refresh_match_freshness_on_milestone(sender, instance, created, **kwargs):
    """A milestone doesn't change the score, but it's a reason to look again."""
    if created:
        from .tasks import mark_milestone_change_task
        mark_milestone_change_task.delay(instance.founder_id, instance.title)


# --- 2. CONNECTION WORKFLOW AUTOMATION ---

def handle_connection_lifecycle(sender, instance, created, **kwargs):
    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
    admin_recipient = getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL)

    if created:
        # Notify Admin
        send_mail(
            subject=f"🚀 New Intro Request: {instance.founder.company_name}",
            message=f"Investor '{instance.investor.company_name}' requested intro to '{instance.founder.company_name}'.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_recipient],
            fail_silently=True
        )

    elif instance.status == 'APPROVED' and not getattr(instance, '_match_email_sent', False):
        send_investor_match_email(instance)
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


# --- 3. UPLOADED FILE STORAGE CLEANUP ---
# post_delete (not a delete() override) is required everywhere here — see
# shared_utils/file_cleanup.py::delete_file_field's docstring for why.

@receiver(post_delete, sender=DataRoomDocument)
def delete_data_room_file_from_storage(sender, instance, **kwargs):
    delete_file_field(instance, 'file')


@receiver(post_delete, sender=Application)
def delete_application_files_from_storage(sender, instance, **kwargs):
    delete_file_field(instance, 'pitch_deck')
    delete_file_field(instance, 'pitch_video')


@receiver(post_delete, sender=Document)
def delete_deal_room_document_file_from_storage(sender, instance, **kwargs):
    delete_file_field(instance, 'file')


@receiver(post_delete, sender=SellerApplication)
def delete_seller_files_from_storage(sender, instance, **kwargs):
    delete_file_field(instance, 'cim_document')
    delete_file_field(instance, 'pitch_video')
