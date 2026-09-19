import datetime
import logging

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts import rate_limits

from notifications.models import Notification
from .disclosures import plan_price_usd, renewal_terms
from .emails import send_subscription_cancelled_email, send_subscription_started_email
from .models import Subscription, SubscriptionConsent

logger = logging.getLogger(__name__)

from .pricing import subscription_prices

stripe.api_key = settings.STRIPE_SECRET_KEY


def _get_role_and_price(user):
    """(plan, price_id) for the user's role, or (None, None) if they have
    no founder/investor/seller/buyer profile."""
    if getattr(user, 'match_founder_profile', None):
        return Subscription.Plan.FOUNDER_PREMIUM, settings.STRIPE_FOUNDER_PRICE_ID
    if getattr(user, 'match_investor_profile', None):
        return Subscription.Plan.INVESTOR_PREMIUM, settings.STRIPE_INVESTOR_PRICE_ID
    if getattr(user, 'match_seller_profile', None):
        return Subscription.Plan.SELLER_PREMIUM, settings.STRIPE_SELLER_PRICE_ID
    if getattr(user, 'match_buyer_profile', None):
        return Subscription.Plan.BUYER_PREMIUM, settings.STRIPE_BUYER_PRICE_ID
    return None, None


def _apply_premium_flag(user, is_premium):
    founder_profile = getattr(user, 'match_founder_profile', None)
    investor_profile = getattr(user, 'match_investor_profile', None)
    seller_profile = getattr(user, 'match_seller_profile', None)
    buyer_profile = getattr(user, 'match_buyer_profile', None)
    if founder_profile:
        founder_profile.is_premium = is_premium
        founder_profile.save(update_fields=['is_premium'])
    if investor_profile:
        investor_profile.is_premium = is_premium
        investor_profile.save(update_fields=['is_premium'])
    if seller_profile:
        seller_profile.is_premium = is_premium
        seller_profile.save(update_fields=['is_premium'])
    if buyer_profile:
        buyer_profile.is_premium = is_premium
        buyer_profile.save(update_fields=['is_premium'])


@login_required
def billing_page(request):
    from zelda_api.quotas import (
        FREE_CREDITS, PREMIUM_CREDITS,
        VALUATION_INVESTOR_BUYER_MONTHLY_LIMIT, VALUATION_OVERAGE_PRICE_USD,
        VALUATION_FIRM_MONTHLY_LIMIT, VALUATION_FIRM_OVERAGE_PRICE_USD,
        VALUATION_REPORT_PRICE_USD,
    )
    from matchmaking.views import DAILY_INTRO_REQUEST_LIMIT, FREE_CRM_LEAD_LIMIT
    from matchmaking.models import Firm

    subscription = Subscription.objects.filter(user=request.user).order_by('-created_at').first()
    plan, price_id = _get_role_and_price(request.user)

    firm_membership = getattr(request.user, 'firm_membership', None)
    return render(request, 'billing/billing.html', {
        **subscription_prices(),
        'subscription': subscription,
        'plan': plan,
        # Stated once in billing/disclosures.py so the sentence on the card, the
        # one beside the checkbox, and the one stored with the consent match.
        'renewal_terms': renewal_terms(plan) if plan else '',
        'current_plan_price': plan_price_usd(subscription.plan) if subscription else 0,
        'stripe_configured': bool(settings.STRIPE_SECRET_KEY and price_id),
        'free_ai_credits': FREE_CREDITS,
        'premium_ai_credits': PREMIUM_CREDITS,
        'daily_intro_limit': DAILY_INTRO_REQUEST_LIMIT,
        'free_crm_lead_limit': FREE_CRM_LEAD_LIMIT,
        'firm_membership': firm_membership,
        'firm_max_seats': Firm.MAX_SEATS,
        'stripe_firm_configured': bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_FIRM_PRICE_ID),
        'valuation_investor_buyer_monthly_limit': VALUATION_INVESTOR_BUYER_MONTHLY_LIMIT,
        'valuation_overage_price': VALUATION_OVERAGE_PRICE_USD,
        'valuation_firm_monthly_limit': VALUATION_FIRM_MONTHLY_LIMIT,
        'valuation_firm_overage_price': VALUATION_FIRM_OVERAGE_PRICE_USD,
        'valuation_report_price': VALUATION_REPORT_PRICE_USD,
    })


@login_required
@require_POST
def create_checkout_session(request):
    plan, price_id = _get_role_and_price(request.user)
    if not plan or not price_id:
        messages.error(request, "Complete your founder, investor, seller, or buyer profile first to see premium options.")
        return redirect('billing:billing_page')

    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, "Payments aren't configured yet. Contact support.")
        return redirect('billing:billing_page')

    # ROSCA and the strictest state rules want affirmative consent to the
    # recurring terms, kept on the record. No tick, no checkout — and the row
    # stores the exact sentence that was on screen, not a pointer to wording
    # that may have changed since.
    if not request.POST.get('agree_to_renewal'):
        messages.error(request, "Please confirm you understand the subscription renews automatically.")
        return redirect('billing:billing_page')

    terms = renewal_terms(plan)
    consent = SubscriptionConsent.objects.create(
        user=request.user, plan=plan, price_usd=plan_price_usd(plan),
        interval='year' if plan == 'INVESTOR_FIRM' else 'month',
        terms_text=terms, ip_address=rate_limits.client_ip(request) or None,
    )

    try:
        session = stripe.checkout.Session.create(
            mode='subscription',
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            customer_email=request.user.email or None,
            client_reference_id=str(request.user.id),
            # The authoritative jurisdiction for the consumer rules, recorded on
            # the consent row once Stripe returns it.
            billing_address_collection='required',
            success_url=request.build_absolute_uri(reverse('billing:billing_page')) + '?checkout=success',
            cancel_url=request.build_absolute_uri(reverse('billing:billing_page')) + '?checkout=canceled',
            metadata={'user_id': str(request.user.id), 'plan': plan, 'consent_id': str(consent.id)},
        )
    except stripe.error.StripeError as e:
        logger.error(f"Stripe checkout session creation failed: {str(e)}")
        messages.error(request, "Couldn't start checkout. Please try again.")
        return redirect('billing:billing_page')

    SubscriptionConsent.objects.filter(pk=consent.pk).update(
        stripe_checkout_session_id=str(getattr(session, 'id', '') or ''))
    return redirect(session.url)


@login_required
@require_POST
def cancel_subscription(request):
    """
    Cancel here rather than sending the customer to Stripe's portal.

    `cancel_at_period_end` because they paid for this period: access continues
    until it ends, and nothing is taken away mid-period. Stripe stays the source
    of truth — the local flag mirrors it so the billing page can say what ends
    and when. If Stripe refuses, nothing local changes and no email goes out;
    telling someone they cancelled when they did not is the one outcome worth
    avoiding above all.
    """
    subscription = (
        Subscription.objects.filter(user=request.user, status=Subscription.Status.ACTIVE)
        .order_by('-created_at').first()
    )
    if not subscription:
        messages.error(request, "You don't have an active subscription to cancel.")
        return redirect('billing:billing_page')

    try:
        stripe.Subscription.modify(subscription.stripe_subscription_id, cancel_at_period_end=True)
    except Exception:
        logger.exception("Stripe refused to cancel subscription %s", subscription.stripe_subscription_id)
        messages.error(request, "Couldn't cancel the subscription just now. Nothing has changed — please try again.")
        return redirect('billing:billing_page')

    subscription.cancel_at_period_end = True
    subscription.save(update_fields=['cancel_at_period_end', 'updated_at'])
    send_subscription_cancelled_email(subscription)
    messages.success(request, "Your subscription is cancelled and will not renew. You keep access until the end of the period you have paid for.")
    return redirect('billing:billing_page')


@login_required
@require_POST
def create_firm_checkout_session(request):
    """
    Starts a new $5,000/mo Firm subscription for an investor with a
    verified business email — the domain becomes the join key teammates
    use (see join_firm). One firm per domain; the founding member becomes
    its owner once the checkout webhook actually creates the Firm row
    (_handle_firm_checkout_completed) — nothing is created here yet.
    """
    from matchmaking.models import BusinessEmailVerification, Firm

    investor_profile = getattr(request.user, 'match_investor_profile', None)
    if not investor_profile:
        messages.error(request, "Complete your investor profile first to start a Firm plan.")
        return redirect('billing:billing_page')

    verification = BusinessEmailVerification.objects.filter(
        user=request.user, status='VERIFIED',
    ).order_by('-verified_at').first()
    if not verification:
        messages.error(request, "Verify your business email before starting a Firm plan.")
        return redirect('accounts:business_verification')

    domain = verification.business_email.rsplit('@', 1)[-1]
    if Firm.objects.filter(verified_domain=domain).exists():
        messages.error(request, "A firm already exists for this email domain — ask its admin to add you as a seat instead.")
        return redirect('billing:billing_page')

    firm_name = (request.POST.get('firm_name') or investor_profile.company_name or '').strip()
    if not firm_name:
        messages.error(request, "Enter a firm name.")
        return redirect('billing:billing_page')

    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_FIRM_PRICE_ID:
        messages.error(request, "Payments aren't configured yet. Contact support.")
        return redirect('billing:billing_page')

    try:
        session = stripe.checkout.Session.create(
            mode='subscription',
            payment_method_types=['card'],
            line_items=[{'price': settings.STRIPE_FIRM_PRICE_ID, 'quantity': 1}],
            customer_email=request.user.email or None,
            client_reference_id=str(request.user.id),
            success_url=request.build_absolute_uri(reverse('billing:billing_page')) + '?checkout=success',
            cancel_url=request.build_absolute_uri(reverse('billing:billing_page')) + '?checkout=canceled',
            metadata={
                'user_id': str(request.user.id),
                'plan': Subscription.Plan.INVESTOR_FIRM,
                'firm_name': firm_name,
                'firm_domain': domain,
            },
        )
    except stripe.error.StripeError as e:
        logger.error(f"Stripe firm checkout session creation failed: {str(e)}")
        messages.error(request, "Couldn't start checkout. Please try again.")
        return redirect('billing:billing_page')

    return redirect(session.url)


@login_required
@require_POST
def join_firm(request):
    """
    Adds a seat to an existing Firm — no payment, since the firm's flat
    $5,000/mo already covers up to Firm.MAX_SEATS. Gated on the same
    verified-business-email-domain match a firm is defined by, so this
    can't be used to piggyback on someone else's plan.
    """
    from matchmaking.models import BusinessEmailVerification, Firm, FirmMembership

    investor_profile = getattr(request.user, 'match_investor_profile', None)
    if not investor_profile:
        messages.error(request, "Complete your investor profile first.")
        return redirect('billing:billing_page')

    if getattr(request.user, 'firm_membership', None):
        messages.error(request, "You're already part of a firm.")
        return redirect('billing:billing_page')

    verification = BusinessEmailVerification.objects.filter(
        user=request.user, status='VERIFIED',
    ).order_by('-verified_at').first()
    if not verification:
        messages.error(request, "Verify your business email first.")
        return redirect('accounts:business_verification')

    domain = verification.business_email.rsplit('@', 1)[-1]
    firm = Firm.objects.filter(verified_domain=domain).first()
    if not firm:
        messages.error(request, "No firm found for your email domain yet — ask your firm's admin to start one, or subscribe individually.")
        return redirect('billing:billing_page')

    if firm.memberships.count() >= Firm.MAX_SEATS:
        messages.error(request, f"{firm.name} has reached its {Firm.MAX_SEATS}-seat limit.")
        return redirect('billing:billing_page')

    FirmMembership.objects.create(firm=firm, user=request.user)
    _apply_premium_flag(request.user, True)
    messages.success(request, f"You've joined {firm.name} — Premium features and a higher AI weekly allowance are now active.")
    return redirect('billing:billing_page')


VALUATION_PURCHASE_PRICE_IDS = {
    'report': lambda: settings.STRIPE_VALUATION_REPORT_PRICE_ID,
    'overage': lambda: settings.STRIPE_VALUATION_OVERAGE_PRICE_ID,
    'firm_overage': lambda: settings.STRIPE_VALUATION_FIRM_OVERAGE_PRICE_ID,
}


@login_required
@require_POST
def create_valuation_purchase_checkout_session(request):
    """
    One-time (mode='payment', not 'subscription') Stripe Checkout that
    unlocks ONE specific preview-tier business valuation report into
    'full' — the free-preview paywall's purchase path (Founder/Seller pay
    $9.99 flat since valuation is never bundled into their plan;
    Investor/Buyer/Firm get a discounted $5 / $1.99 rate for the same
    reason their monthly allowances are cheaper). See
    zelda_api/quotas.py::valuation_unlock_price() for the role-based
    pricing and zelda_api/quotas.py::unlock_valuation_document() for what
    the webhook (below) does once Stripe confirms payment — nothing is
    unlocked here before that.
    """
    from zelda_api.vector_models import DocumentSource
    from zelda_api.quotas import valuation_unlock_price

    document_id = request.POST.get('document_id')
    document = DocumentSource.objects.filter(
        id=document_id, uploaded_by=request.user, document_type='business_valuation',
    ).first()
    if not document:
        messages.error(request, "Valuation report not found.")
        return redirect('zelda_api:valuation_request')
    if document.valuation_tier == 'full':
        messages.info(request, "This report is already unlocked.")
        return redirect('zelda_api:valuation_report', document_id=document.id)

    purchase_type, _price = valuation_unlock_price(request.user)
    price_id = VALUATION_PURCHASE_PRICE_IDS[purchase_type]()
    if not settings.STRIPE_SECRET_KEY or not price_id:
        messages.error(request, "Payments aren't configured yet. Contact support.")
        return redirect('zelda_api:valuation_report', document_id=document.id)

    try:
        session = stripe.checkout.Session.create(
            mode='payment',
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            customer_email=request.user.email or None,
            client_reference_id=str(request.user.id),
            success_url=request.build_absolute_uri(
                reverse('zelda_api:valuation_report', kwargs={'document_id': document.id})
            ) + '?purchase=success',
            cancel_url=request.build_absolute_uri(
                reverse('zelda_api:valuation_report', kwargs={'document_id': document.id})
            ) + '?purchase=canceled',
            metadata={
                'user_id': str(request.user.id), 'purpose': 'valuation_purchase',
                'purchase_type': purchase_type, 'document_id': str(document.id),
            },
        )
    except stripe.error.StripeError as e:
        logger.error(f"Stripe valuation checkout session creation failed: {str(e)}")
        messages.error(request, "Couldn't start checkout. Please try again.")
        return redirect('zelda_api:valuation_report', document_id=document.id)

    return redirect(session.url)


@login_required
@require_POST
def create_billing_portal_session(request):
    subscription = Subscription.objects.filter(user=request.user).order_by('-created_at').first()
    if not subscription or not subscription.stripe_customer_id:
        messages.error(request, "No billing account found.")
        return redirect('billing:billing_page')

    try:
        session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=request.build_absolute_uri(reverse('billing:billing_page')),
        )
    except stripe.error.StripeError as e:
        logger.error(f"Stripe billing portal session creation failed: {str(e)}")
        messages.error(request, "Couldn't open billing portal. Please try again.")
        return redirect('billing:billing_page')

    return redirect(session.url)


# Stripe subscription status -> local status. Only ACTIVE grants Premium.
# Anything not listed -- `paused`, or a status Stripe adds later -- is stored
# as INCOMPLETE, so it never does.
STRIPE_SUBSCRIPTION_STATUSES = {
    'active': Subscription.Status.ACTIVE,
    'trialing': Subscription.Status.ACTIVE,
    'past_due': Subscription.Status.PAST_DUE,
    'unpaid': Subscription.Status.PAST_DUE,
    'canceled': Subscription.Status.CANCELED,
    'incomplete_expired': Subscription.Status.CANCELED,
    'incomplete': Subscription.Status.INCOMPLETE,
}


def _utc_from_timestamp(value):
    """An aware UTC datetime from a Unix timestamp, or None when it isn't a usable one."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return datetime.datetime.fromtimestamp(value, tz=datetime.timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _subscription_period_end(subscription):
    """
    When a Stripe subscription next renews, or None.

    Since API 2025-03-31.basil the billing period lives on each subscription
    item (items.data[].current_period_end), not on the subscription, so the
    earliest item end is the next renewal. A legacy payload's top-level
    current_period_end is used only when no item gives a usable one. Values
    that aren't usable timestamps are ignored rather than failing the webhook.
    """
    item_data = (subscription.get('items') or {}).get('data') or []
    ends = [
        end for end in (
            _utc_from_timestamp(item.get('current_period_end')) for item in item_data if isinstance(item, dict)
        ) if end
    ]
    if not ends:
        legacy = _utc_from_timestamp(subscription.get('current_period_end'))
        ends = [legacy] if legacy else []
    return min(ends) if ends else None


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Stripe can't send a Django CSRF token, so this endpoint is CSRF-exempt —
    the Stripe signature check (construct_event) is the actual authentication
    here, not Django's session/CSRF machinery.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        logger.error(f"Stripe webhook signature verification failed: {str(e)}")
        return HttpResponseBadRequest("Invalid signature")

    # construct_event returns a stripe.Event, and since stripe-python 15 a
    # StripeObject is no longer a dict: .get() on it raises AttributeError.
    # Convert once, here, so everything below reads plain dicts -- to_dict()
    # recurses, so nested objects such as metadata convert too.
    if isinstance(event, stripe.StripeObject):
        event = event.to_dict()

    event_type = event['type']
    data_object = event['data']['object']
    User = get_user_model()

    if event_type == 'checkout.session.completed':
        metadata = data_object.get('metadata') or {}
        user_id = metadata.get('user_id') or data_object.get('client_reference_id')
        plan = metadata.get('plan')
        stripe_customer_id = data_object.get('customer')
        stripe_subscription_id = data_object.get('subscription')

        # One-time valuation purchase (mode='payment') — no subscription
        # object at all, so this branches before the subscription check
        # below, which requires stripe_subscription_id.
        if metadata.get('purpose') == 'valuation_purchase':
            purchase_type = metadata.get('purchase_type')
            document_id = metadata.get('document_id')
            if user_id and purchase_type and document_id:
                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    logger.error(f"Stripe webhook: no user found for id {user_id}")
                    return HttpResponse(status=200)

                from zelda_api.vector_models import DocumentSource
                from zelda_api.quotas import unlock_valuation_document
                document = DocumentSource.objects.filter(id=document_id, uploaded_by=user).first()
                if not document:
                    logger.error(f"Stripe webhook: no document {document_id} found for user {user_id}")
                    return HttpResponse(status=200)

                unlock_valuation_document(document, purchase_type, data_object.get('id') or '')
                Notification.objects.create(
                    recipient=user, sender=None, notification_type='PAYMENT',
                    message=f"Payment received — your business valuation report for {document.source_entity} is fully unlocked.",
                )
            return HttpResponse(status=200)

        if user_id and stripe_subscription_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.error(f"Stripe webhook: no user found for id {user_id}")
                return HttpResponse(status=200)

            subscription, created = Subscription.objects.update_or_create(
                stripe_subscription_id=stripe_subscription_id,
                defaults={
                    'user': user,
                    'plan': plan or Subscription.Plan.FOUNDER_PREMIUM,
                    'stripe_customer_id': stripe_customer_id or '',
                    'status': Subscription.Status.ACTIVE,
                },
            )
            _apply_premium_flag(user, True)

            # The billing address is the authoritative jurisdiction for the
            # consumer-protection rules, and it only exists once the customer
            # has entered it at Stripe. Recorded on the consent row so each
            # subscription shows which state it was actually sold into.
            address = (data_object.get('customer_details') or {}).get('address') or {}
            consent_id = metadata.get('consent_id')
            if consent_id:
                SubscriptionConsent.objects.filter(pk=consent_id, user=user).update(
                    billing_country=(address.get('country') or '')[:2],
                    billing_state=(address.get('state') or '')[:64],
                )

            # Stripe sends a card receipt; it does not say what the plan
            # includes, when it renews, or how to stop it.
            if created:
                send_subscription_started_email(subscription)

            if plan == Subscription.Plan.INVESTOR_FIRM:
                from matchmaking.models import Firm, FirmMembership
                firm_domain = metadata.get('firm_domain')
                if firm_domain and not Firm.objects.filter(verified_domain=firm_domain).exists():
                    firm = Firm.objects.create(
                        name=metadata.get('firm_name') or 'Untitled Firm',
                        verified_domain=firm_domain,
                        owner=user,
                    )
                    FirmMembership.objects.get_or_create(user=user, defaults={'firm': firm})

            Notification.objects.create(
                recipient=user,
                sender=None,
                notification_type='PAYMENT',
                message="Your premium subscription is now active.",
            )

    elif event_type == 'customer.subscription.updated':
        stripe_subscription_id = data_object.get('id')
        stripe_status = data_object.get('status')
        sub = Subscription.objects.filter(stripe_subscription_id=stripe_subscription_id).first()
        if sub:
            new_status = STRIPE_SUBSCRIPTION_STATUSES.get(stripe_status, Subscription.Status.INCOMPLETE)
            update_fields = ['status', 'updated_at']
            # Stored only when the payload actually says when it renews.
            period_end = _subscription_period_end(data_object)
            if period_end:
                sub.current_period_end = period_end
                update_fields.append('current_period_end')
            sub.status = new_status
            sub.save(update_fields=update_fields)
            _apply_premium_flag(sub.user, new_status == Subscription.Status.ACTIVE)

    elif event_type == 'customer.subscription.deleted':
        stripe_subscription_id = data_object.get('id')
        sub = Subscription.objects.filter(stripe_subscription_id=stripe_subscription_id).first()
        if sub:
            sub.status = Subscription.Status.CANCELED
            sub.save(update_fields=['status', 'updated_at'])
            _apply_premium_flag(sub.user, False)
            Notification.objects.create(
                recipient=sub.user,
                sender=None,
                notification_type='PAYMENT',
                message="Your premium subscription has ended.",
            )

    elif event_type == 'invoice.payment_failed':
        stripe_customer_id = data_object.get('customer')
        sub = Subscription.objects.filter(
            stripe_customer_id=stripe_customer_id, status=Subscription.Status.ACTIVE
        ).first()
        if sub:
            sub.status = Subscription.Status.PAST_DUE
            sub.save(update_fields=['status', 'updated_at'])
            Notification.objects.create(
                recipient=sub.user,
                sender=None,
                notification_type='PAYMENT',
                message="Your last payment failed — please update your card to keep premium features.",
            )

    return HttpResponse(status=200)
