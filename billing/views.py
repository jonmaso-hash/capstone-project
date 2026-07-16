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
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from notifications.models import Notification
from .models import Subscription

logger = logging.getLogger(__name__)

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
    subscription = Subscription.objects.filter(user=request.user).order_by('-created_at').first()
    plan, price_id = _get_role_and_price(request.user)
    return render(request, 'billing/billing.html', {
        'subscription': subscription,
        'plan': plan,
        'stripe_configured': bool(settings.STRIPE_SECRET_KEY and price_id),
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

    try:
        session = stripe.checkout.Session.create(
            mode='subscription',
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            customer_email=request.user.email or None,
            client_reference_id=str(request.user.id),
            success_url=request.build_absolute_uri(reverse('billing:billing_page')) + '?checkout=success',
            cancel_url=request.build_absolute_uri(reverse('billing:billing_page')) + '?checkout=canceled',
            metadata={'user_id': str(request.user.id), 'plan': plan},
        )
    except stripe.error.StripeError as e:
        logger.error(f"Stripe checkout session creation failed: {str(e)}")
        messages.error(request, "Couldn't start checkout. Please try again.")
        return redirect('billing:billing_page')

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

    event_type = event['type']
    data_object = event['data']['object']
    User = get_user_model()

    if event_type == 'checkout.session.completed':
        metadata = data_object.get('metadata') or {}
        user_id = metadata.get('user_id') or data_object.get('client_reference_id')
        plan = metadata.get('plan')
        stripe_customer_id = data_object.get('customer')
        stripe_subscription_id = data_object.get('subscription')

        if user_id and stripe_subscription_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.error(f"Stripe webhook: no user found for id {user_id}")
                return HttpResponse(status=200)

            Subscription.objects.update_or_create(
                stripe_subscription_id=stripe_subscription_id,
                defaults={
                    'user': user,
                    'plan': plan or Subscription.Plan.FOUNDER_PREMIUM,
                    'stripe_customer_id': stripe_customer_id or '',
                    'status': Subscription.Status.ACTIVE,
                },
            )
            _apply_premium_flag(user, True)
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
            if stripe_status == 'active':
                new_status = Subscription.Status.ACTIVE
            elif stripe_status == 'past_due':
                new_status = Subscription.Status.PAST_DUE
            else:
                new_status = Subscription.Status.INCOMPLETE

            current_period_end = data_object.get('current_period_end')
            if current_period_end:
                sub.current_period_end = timezone.make_aware(
                    datetime.datetime.utcfromtimestamp(current_period_end), timezone.utc
                )
            sub.status = new_status
            sub.save(update_fields=['status', 'current_period_end', 'updated_at'])
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
