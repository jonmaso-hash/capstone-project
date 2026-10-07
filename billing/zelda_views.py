"""One-time Checkout and owner-scoped report purchases for the Zelda hub."""
import json
import logging
import hashlib
import uuid
import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.cache import cache
from django.db import transaction, DatabaseError
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import ZeldaOrder, TruthDeltaCreditPurchase, TruthDeltaCreditWallet, TruthDeltaCreditRedemption
from .zelda_catalog import PRODUCTS, REPORTS, ALL_STRIPE_PRODUCTS, DILIGENCE_PRODUCTS, role_catalog, selected_reports

logger = logging.getLogger(__name__)


class ProductPaymentConfigurationError(ValueError):
    pass


class CompanySearchLimitError(Exception):
    pass


def search_limit_response(scope, identifier):
    from accounts import rate_limits
    minutes = rate_limits.minutes_until_allowed(scope, identifier)
    wait = f'in {minutes} minute{"s" if minutes != 1 else ""}' if minutes is not None else 'in a few minutes'
    if scope == 'zelda_company_search_user':
        limit, _ = rate_limits.LIMITS[scope]
        message = f'You have reached {limit} company searches per hour. Try again {wait}. You can still upload a pitch deck.'
    else:
        message = f'Public-record lookups are temporarily busy. Try again {wait}, or upload a pitch deck.'
    response = JsonResponse({'error': message, 'retry_after_seconds': minutes * 60 if minutes is not None else None}, status=429)
    if minutes is not None:
        response['Retry-After'] = str(minutes * 60)
    return response


def plain(value):
    return value.to_dict() if isinstance(value, stripe.StripeObject) else value


def stripe_price(product):
    """Use an existing active catalog Price; never create a replacement product."""
    name, amount, _ = ALL_STRIPE_PRODUCTS[product]
    api_key = settings.STRIPE_SECRET_KEY.strip()
    if not api_key:
        raise ProductPaymentConfigurationError('STRIPE_SECRET_KEY is missing on the web service')
    account = hashlib.sha256(settings.STRIPE_SECRET_KEY.encode()).hexdigest()[:12]
    key = f'zelda_price:{account}:{product}'
    price_id = cache.get(key)
    if not price_id:
        products = stripe.Product.list(active=True, limit=100, api_key=api_key)
        matches = [plain(p) for p in products.auto_paging_iter() if plain(p).get('name', '').casefold() == name.casefold()]
        if len(matches) != 1:
            raise ProductPaymentConfigurationError('The product must have one matching active Stripe catalog entry.')
        prices = plain(stripe.Price.list(product=matches[0]['id'], active=True, limit=100, api_key=api_key)).get('data', [])
        matches = [plain(p) for p in prices if plain(p).get('currency') == 'usd'
                   and plain(p).get('unit_amount') == amount and plain(p).get('type') == 'one_time']
        if len(matches) != 1:
            raise ProductPaymentConfigurationError('The product must have one matching active USD one-time price.')
        price_id = matches[0]['id']
        cache.set(key, price_id, 3600)
    price = plain(stripe.Price.retrieve(price_id, api_key=api_key))
    if not price.get('active') or price.get('currency') != 'usd' or price.get('unit_amount') != amount or price.get('type') != 'one_time':
        cache.delete(key)
        raise ProductPaymentConfigurationError('The configured catalog price does not match the product.')
    return price_id


@login_required
def product_catalog(request):
    wallet_balance = 0
    if getattr(request.user, 'match_investor_profile', None) or getattr(request.user, 'match_buyer_profile', None):
        wallet_balance = TruthDeltaCreditWallet.objects.filter(user=request.user).values_list('balance', flat=True).first() or 0
    return JsonResponse({
        'products': role_catalog(request.user),
        'reports': [{'key': key, 'name': value[0]} for key, value in REPORTS.items()],
        'truth_delta_credit_balance': wallet_balance,
    })


@login_required
@require_POST
def external_search(request):
    from zelda_api.sec_company_identity import resolve_company_identity, search_listed_companies, FOUND
    from zelda_api.sec_identity import SecUnavailable
    name = request.POST.get('q', '').strip()[:255]
    if len(name) < 1:
        return JsonResponse({'error': 'Enter a company name or stock ticker.'}, status=400)
    from accounts import rate_limits
    user_key = str(request.user.pk)
    if rate_limits.reserve('zelda_company_search_user', user_key) is None:
        return search_limit_response('zelda_company_search_user', user_key)
    source_reserved = False

    def reserve_source():
        nonlocal source_reserved
        if source_reserved:
            return
        if rate_limits.reserve('identity_check_global', rate_limits.GLOBAL_KEY) is None:
            raise CompanySearchLimitError()
        source_reserved = True
    try:
        index_unavailable = False
        try:
            choices = search_listed_companies(name, before_fetch=reserve_source)
        except SecUnavailable:
            choices, index_unavailable = [], True
        if choices:
            for choice in choices:
                choice['token'] = signing.dumps({'name': choice['name'], 'cik': choice['cik']}, salt='zelda-company-selection')
                choice['source_url'] = f'https://www.sec.gov/edgar/browse/?CIK={choice["cik"]}'
            return JsonResponse({'results': choices})
        reserve_source()
        identity = resolve_company_identity(name)
        if identity.status != FOUND and index_unavailable:
            raise SecUnavailable('Company index unavailable')
    except CompanySearchLimitError:
        return search_limit_response('identity_check_global', rate_limits.GLOBAL_KEY)
    except SecUnavailable:
        return JsonResponse({'error': 'Public company records are temporarily unavailable. Please try again.'}, status=503)
    if identity.status != FOUND:
        return JsonResponse({'results': [], 'message': (
            'More than one SEC registrant matches. Use a more specific legal company name.' if identity.status == 'ambiguous'
            else 'No matching SEC registrant was found. A brand may not file separately from its parent, and SEC records do not cover every private company. You can still upload its document and enter its company name.'
        )})
    token = signing.dumps({'name': identity.name, 'cik': identity.cik}, salt='zelda-company-selection')
    return JsonResponse({'results': [{'name': identity.name, 'cik': identity.cik, 'token': token,
                                     'source_url': f'https://www.sec.gov/edgar/browse/?CIK={identity.cik}'}]})


@login_required
@require_POST
def product_intake(request):
    from zelda_api.vector_models import DocumentSource
    from zelda_api.utils import extract_text_from_file, has_usable_text, ExtractionError, strip_page_markers
    from shared_utils.upload_limits import PITCH_ANALYSIS_MAX_MB, MB
    from zelda_api.sec_identity import company_record, SecUnavailable
    name = request.POST.get('company', '').strip()[:255]
    cik = ''
    token = request.POST.get('subject_token', '')
    try:
        if token:
            subject = signing.loads(token, salt='zelda-company-selection', max_age=3600)
            name, cik = subject['name'], subject['cik']
    except (signing.BadSignature, KeyError):
        return JsonResponse({'error': 'Company selection expired. Please search and select it again.'}, status=400)
    if not name:
        return JsonResponse({'error': 'Name the company this evidence describes.'}, status=400)
    from accounts import rate_limits
    _tokens, refused = rate_limits.reserve_all([('zelda_product_intake_user', str(request.user.pk))])
    if refused:
        return JsonResponse({'error': 'You have reached today’s document intake limit. Please try again later.'}, status=429)
    file = request.FILES.get('file')
    if file:
        if file.size > PITCH_ANALYSIS_MAX_MB * MB or file.name.rsplit('.', 1)[-1].lower() not in ('pdf', 'pptx', 'txt'):
            return JsonResponse({'error': f'Use a PDF, PPTX or TXT document up to {PITCH_ANALYSIS_MAX_MB} MB.'}, status=400)
        try:
            raw, pages = extract_text_from_file(file)
        except ExtractionError:
            return JsonResponse({'error': 'This document could not be read. Please provide a text-readable PDF, PPTX or TXT.'}, status=422)
        filename = file.name[:255]
        evidence_label = 'Your uploaded document'
    elif cik:
        try:
            record = company_record(cik)
        except SecUnavailable:
            return JsonResponse({'error': 'The selected public record could not be retrieved. Please try again.'}, status=503)
        # Registration facts are explicitly bounded evidence, not a pitch deck
        # or parent financials silently attributed to this selected company.
        raw = (f"SEC registration snapshot for {name}. CIK {cik}. "
               f"Registered name: {record.get('name', name)}. "
               f"Incorporation jurisdiction: {record.get('stateOfIncorporation', 'not disclosed')}. "
               f"Source: https://www.sec.gov/edgar/browse/?CIK={cik}. "
               "This snapshot establishes registry context only; it does not disclose current revenue, customers, employees or valuation. Upload company documents for substantive financial and claim analysis.")
        pages, filename, evidence_label = 1, 'SEC registration snapshot.txt', 'SEC registration snapshot only'
    else:
        return JsonResponse({'error': 'Upload a document or select a company from external search.'}, status=400)
    if not has_usable_text(raw):
        return JsonResponse({'error': 'The document contains insufficient readable text. Please upload another file.'}, status=422)
    try:
        doc = DocumentSource.objects.create(
            uploaded_by=request.user, source_entity=name, filename=filename, document_type='research_report',
            raw_text_full=raw, raw_text_preview=strip_page_markers(raw)[:1000], total_pages=pages,
            is_external_subject=True, is_product_input=True, external_cik=cik,
        )
    except DatabaseError:
        logger.exception('Could not save Zelda product evidence for user %s', request.user.pk)
        return JsonResponse({'error': 'The server could not save your document. Please try again shortly. Nothing was purchased.'}, status=503)
    return JsonResponse({'document_id': doc.id, 'company': name, 'evidence': evidence_label}, status=201)


@login_required
@require_POST
def product_checkout(request):
    from zelda_api.vector_models import DocumentSource
    try:
        data = json.loads(request.body)
        product = data['product']
        reports = selected_reports(product, data.get('reports', []))
        if product not in ALL_STRIPE_PRODUCTS or product == 'truth_delta_credit_pack':
            raise ValueError()
        is_diligence_user = bool(
            getattr(request.user, 'match_investor_profile', None)
            or getattr(request.user, 'match_buyer_profile', None)
        )
        if product == 'truth_delta_diligence' and not is_diligence_user:
            raise ValueError()
        if product in PRODUCTS and is_diligence_user:
            raise ValueError()
        document_id = int(data['document_id'])
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'error': 'Select a product, evidence and the required reports.'}, status=400)
    try:
        # Lock the evidence while selecting/creating an order. Concurrent retries
        # then share the same order and Stripe idempotency key.
        for attempt in range(2):
            with transaction.atomic():
                doc = get_object_or_404(DocumentSource.objects.select_for_update(), pk=document_id,
                                        uploaded_by=request.user, is_product_input=True)
                order = ZeldaOrder.objects.filter(user=request.user, source_document=doc, product=product,
                                                  status__in=['awaiting_payment', 'paid', 'processing', 'ready', 'failed']).first()
                if order and order.reports != reports:
                    return JsonResponse({'error': 'This evidence already has a different pack selection. Upload a fresh evidence set for a different pack.'}, status=409)
                if order and order.status != 'awaiting_payment':
                    return JsonResponse({'order_url': reverse('billing:zelda_order', args=[order.id])})
                if not order:
                    order = ZeldaOrder.objects.create(user=request.user, source_document=doc, product=product,
                                                     reports=reports, amount=ALL_STRIPE_PRODUCTS[product][1])
            if not order.stripe_session_id:
                break
            # A saved URL can outlive its Checkout session. Ask Stripe before
            # redirecting or replacing it; never start a second payment for a
            # complete session, including an asynchronously pending payment.
            session = plain(stripe.checkout.Session.retrieve(
                order.stripe_session_id, api_key=settings.STRIPE_SECRET_KEY.strip()))
            if session.get('id') != order.stripe_session_id:
                raise ValueError('Retrieved product session mismatch')
            checkout_state = session.get('status')
            if checkout_state not in ('open', 'complete', 'expired'):
                raise ValueError('Unknown Checkout session state')
            if session.get('payment_status') == 'paid' and checkout_state != 'complete':
                raise ValueError('Paid Checkout session is not complete')
            handle_product_event('checkout.session.expired' if checkout_state == 'expired'
                                 else 'checkout.session.completed', session)
            if checkout_state == 'expired':
                continue
            if checkout_state == 'complete':
                return JsonResponse({'order_url': reverse('billing:zelda_order', args=[order.id])})
            if not session.get('url'):
                raise ProductPaymentConfigurationError('Open Checkout session has no hosted URL')
            return JsonResponse({'checkout_url': session['url']})
        else:
            raise ProductPaymentConfigurationError('Checkout sessions expired during retry')
        price_id = stripe_price(product)
        order_url = request.build_absolute_uri(reverse('billing:zelda_order', args=[order.id]))
        session = plain(stripe.checkout.Session.create(
            mode='payment', line_items=[{'price': price_id, 'quantity': 1}],
            client_reference_id=str(request.user.id), customer_email=request.user.email or None,
            success_url=order_url, cancel_url=order_url,
            metadata={'purpose': 'zelda_product', 'order_id': str(order.id), 'user_id': str(request.user.id)},
            idempotency_key=f'zelda-order-{order.id}',
            api_key=settings.STRIPE_SECRET_KEY.strip(),
        ))
        if not session.get('id') or not session.get('url'):
            raise ProductPaymentConfigurationError('Stripe did not return a hosted Checkout session')
        order.stripe_session_id, order.checkout_url = session['id'], session['url']
        order.save(update_fields=['stripe_session_id', 'checkout_url'])
    except Http404:
        raise
    except ProductPaymentConfigurationError:
        logger.exception('Zelda product payment configuration unavailable for order %s', order.id)
        return JsonResponse({'error': 'Payments are not configured for this product yet. Please try again later. Nothing was charged.'}, status=503)
    except Exception:
        reference = uuid.uuid4().hex[:12]
        logger.exception('Could not open Zelda product checkout reference=%s user=%s', reference, request.user.pk)
        return JsonResponse({'error': 'Checkout is currently unavailable. If you already submitted payment, do not pay again. Please try again shortly.',
                             'reference': reference}, status=503)
    return JsonResponse({'checkout_url': order.checkout_url})



def handle_product_event(event_type, session):
    """Accept only a signed webhook or a session retrieved directly from Stripe."""
    from .tasks import fulfill_zelda_order
    with transaction.atomic():
        order = ZeldaOrder.objects.select_for_update().filter(stripe_session_id=session.get('id')).first()
        if not order or session.get('metadata', {}).get('order_id') != str(order.pk):
            raise ValueError('Unknown product order/session')
        if (session.get('mode') != 'payment'
                or session.get('metadata', {}).get('purpose') != 'zelda_product'
                or str(order.user_id) != session.get('metadata', {}).get('user_id')
                or session.get('currency') != order.currency or session.get('amount_total') != order.amount):
            raise ValueError('Product order payment mismatch')
        if event_type in ('checkout.session.completed', 'checkout.session.async_payment_succeeded'):
            if session.get('payment_status') == 'paid' and order.status in ('awaiting_payment', 'paid'):
                if order.status == 'awaiting_payment':
                    order.status, order.paid_at = 'paid', timezone.now()
                    order.save(update_fields=['status', 'paid_at'])
                transaction.on_commit(lambda: fulfill_zelda_order.delay(str(order.pk)))
        elif event_type in ('checkout.session.expired', 'checkout.session.async_payment_failed'):
            if order.status == 'awaiting_payment':
                order.status = 'canceled'
                order.save(update_fields=['status'])



def _is_diligence_user(user):
    return bool(
        getattr(user, 'match_investor_profile', None)
        or getattr(user, 'match_buyer_profile', None)
    )


@login_required
@require_POST
def truth_delta_credit_pack_checkout(request):
    if not _is_diligence_user(request.user):
        return JsonResponse({'error': 'Truth Delta credit packs are available to investors and buyers.'}, status=403)

    amount = DILIGENCE_PRODUCTS['truth_delta_credit_pack'][1]
    purchase = TruthDeltaCreditPurchase.objects.filter(
        user=request.user,
        status='awaiting_payment',
    ).order_by('-created_at').first()
    if not purchase:
        purchase = TruthDeltaCreditPurchase.objects.create(user=request.user, amount=amount)

    try:
        if purchase.stripe_session_id:
            session = plain(stripe.checkout.Session.retrieve(
                purchase.stripe_session_id,
                api_key=settings.STRIPE_SECRET_KEY.strip(),
            ))
            if session.get('payment_status') == 'paid' and session.get('status') == 'complete':
                handle_truth_delta_credit_event('checkout.session.completed', session)
                return JsonResponse({'credit_balance': TruthDeltaCreditWallet.objects.filter(
                    user=request.user
                ).values_list('balance', flat=True).first() or 0})
            if session.get('status') == 'open' and session.get('url'):
                return JsonResponse({'checkout_url': session['url']})
            if session.get('status') == 'expired':
                purchase.status = 'canceled'
                purchase.save(update_fields=['status'])
                purchase = TruthDeltaCreditPurchase.objects.create(user=request.user, amount=amount)

        price_id = stripe_price('truth_delta_credit_pack')
        return_url = request.build_absolute_uri(
            reverse('accounts:profile', args=[request.user.username])
        ) + '?zelda=truth-delta-credits'
        session = plain(stripe.checkout.Session.create(
            mode='payment',
            line_items=[{'price': price_id, 'quantity': 1}],
            client_reference_id=str(request.user.id),
            customer_email=request.user.email or None,
            success_url=return_url,
            cancel_url=return_url,
            metadata={
                'purpose': 'truth_delta_credit_pack',
                'credit_purchase_id': str(purchase.id),
                'user_id': str(request.user.id),
            },
            idempotency_key=f'truth-delta-credit-pack-{purchase.id}',
            api_key=settings.STRIPE_SECRET_KEY.strip(),
        ))
        if not session.get('id') or not session.get('url'):
            raise ProductPaymentConfigurationError('Stripe did not return a hosted Checkout session')
        purchase.stripe_session_id = session['id']
        purchase.checkout_url = session['url']
        purchase.save(update_fields=['stripe_session_id', 'checkout_url'])
        return JsonResponse({'checkout_url': purchase.checkout_url})
    except Exception:
        reference = uuid.uuid4().hex[:12]
        logger.exception('Could not open Truth Delta credit checkout reference=%s user=%s', reference, request.user.pk)
        return JsonResponse({
            'error': 'Checkout is currently unavailable. If you already submitted payment, do not pay again.',
            'reference': reference,
        }, status=503)


def handle_truth_delta_credit_event(event_type, session):
    metadata = session.get('metadata') or {}
    with transaction.atomic():
        purchase = TruthDeltaCreditPurchase.objects.select_for_update().filter(
            stripe_session_id=session.get('id')
        ).first()
        if (
            not purchase
            or metadata.get('credit_purchase_id') != str(purchase.pk)
            or metadata.get('purpose') != 'truth_delta_credit_pack'
            or metadata.get('user_id') != str(purchase.user_id)
            or session.get('mode') != 'payment'
            or session.get('currency') != purchase.currency
            or session.get('amount_total') != purchase.amount
        ):
            raise ValueError('Truth Delta credit purchase payment mismatch')

        if event_type in ('checkout.session.completed', 'checkout.session.async_payment_succeeded'):
            if session.get('payment_status') != 'paid':
                return
            if purchase.status == 'awaiting_payment':
                wallet, _ = TruthDeltaCreditWallet.objects.select_for_update().get_or_create(
                    user=purchase.user
                )
                wallet.balance += purchase.credits
                wallet.save(update_fields=['balance', 'updated_at'])
                purchase.status = 'paid'
                purchase.paid_at = timezone.now()
                purchase.save(update_fields=['status', 'paid_at'])
        elif event_type in ('checkout.session.expired', 'checkout.session.async_payment_failed'):
            if purchase.status == 'awaiting_payment':
                purchase.status = 'canceled'
                purchase.save(update_fields=['status'])


@login_required
@require_POST
def redeem_truth_delta_credit(request):
    if not _is_diligence_user(request.user):
        return JsonResponse({'error': 'Truth Delta credits are available to investors and buyers.'}, status=403)
    try:
        data = json.loads(request.body)
        document_id = int(data['document_id'])
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'error': 'Select company evidence before using a Truth Delta credit.'}, status=400)

    from zelda_api.vector_models import DocumentSource
    from .tasks import fulfill_zelda_order

    with transaction.atomic():
        doc = get_object_or_404(
            DocumentSource.objects.select_for_update(),
            pk=document_id,
            uploaded_by=request.user,
            is_product_input=True,
        )
        wallet = TruthDeltaCreditWallet.objects.select_for_update().filter(user=request.user).first()
        if not wallet or wallet.balance < 1:
            return JsonResponse({'error': 'You do not have a Truth Delta credit available.'}, status=409)

        existing = ZeldaOrder.objects.filter(
            user=request.user,
            source_document=doc,
            product='truth_delta_diligence',
            status__in=['paid', 'processing', 'ready'],
        ).first()
        if existing:
            return JsonResponse({'order_url': reverse('billing:zelda_order', args=[existing.id])})

        order = ZeldaOrder.objects.create(
            user=request.user,
            source_document=doc,
            product='truth_delta_diligence',
            reports=['truth_delta'],
            amount=0,
            status='paid',
            paid_at=timezone.now(),
        )
        wallet.balance -= 1
        wallet.save(update_fields=['balance', 'updated_at'])
        TruthDeltaCreditRedemption.objects.create(wallet=wallet, order=order, credits_used=1)
        transaction.on_commit(lambda: fulfill_zelda_order.delay(str(order.id)))

    return JsonResponse({
        'order_url': reverse('billing:zelda_order', args=[order.id]),
        'credit_balance': wallet.balance,
    })

def recover_order_payment(order):
    """Recover missed webhooks/queue delivery without creating another charge.

    Poll only the owner's stored session, at most once every 15 seconds. Cached
    checkout state is display information, never authorization to fulfill.
    """
    if order.status not in ('awaiting_payment', 'paid'):
        return {}
    account = hashlib.sha256(settings.STRIPE_SECRET_KEY.encode()).hexdigest()[:12]
    key = f'zelda_payment_check:{account}:{order.id}'
    try:
        details = cache.get(key + ':display') or {}
        if not cache.add(key, True, 15):
            return details
    except Exception:
        # An unavailable cache must not take down the saved order status, or
        # cause unthrottled Stripe calls on every browser poll.
        logger.exception('Zelda payment check cache unavailable for order %s', order.pk)
        return {'payment_check_unavailable': True}
    try:
        if order.status == 'paid' and order.paid_at:
            # A paid order can still be waiting for broker delivery. The worker
            # locks the order and ignores duplicate deliveries once processing.
            from .tasks import fulfill_zelda_order
            transaction.on_commit(lambda: fulfill_zelda_order.delay(str(order.pk)))
            return {}
        api_key = settings.STRIPE_SECRET_KEY.strip()
        if not api_key or not order.stripe_session_id:
            raise ProductPaymentConfigurationError('Payment verification is not configured')
        session = plain(stripe.checkout.Session.retrieve(order.stripe_session_id, api_key=api_key))
        # Do not let an unexpected response confirm a different stored order.
        if session.get('id') != order.stripe_session_id:
            raise ValueError('Retrieved product session mismatch')
        status = session.get('status')
        if status not in ('open', 'complete', 'expired'):
            raise ValueError('Unknown Checkout session state')
        if session.get('payment_status') == 'paid' and status != 'complete':
            raise ValueError('Paid Checkout session is not complete')
        event = 'checkout.session.expired' if status == 'expired' else 'checkout.session.completed'
        # Validate metadata, amount and currency even for unpaid/expired sessions.
        handle_product_event(event, session)
        details = {'checkout_state': status}
    except Exception:
        logger.exception('Could not reconcile Zelda payment for order %s', order.pk)
        details = {'payment_check_unavailable': True}
    finally:
        # on_commit delivery errors may occur after payment is safely recorded.
        order.refresh_from_db()
    try:
        cache.set(key + ':display', details, 15)
    except Exception:
        logger.exception('Could not cache Zelda payment check for order %s', order.pk)
    return details


@login_required
def order_status(request, order_id):
    from .fulfillment import reconcile_order
    try:
        order = get_object_or_404(ZeldaOrder, pk=order_id, user=request.user)
        payment_details = recover_order_payment(order)
        reconcile_order(order)
    except Http404:
        raise
    except Exception:
        reference = uuid.uuid4().hex[:12]
        logger.exception('Zelda order status failed reference=%s order=%s user=%s', reference, order_id, request.user.pk)
        response = JsonResponse({'error': 'The server could not check this order right now. If you already paid, do not pay again.',
                                 'reference': reference}, status=503)
        response['Cache-Control'] = 'no-store'
        response['Retry-After'] = '5'
        return response
    response = JsonResponse({'status': order.status, **payment_details, 'reports': [
        {'name': REPORTS[key][0], 'url': reverse('billing:zelda_report', args=[order.id, key])}
        for key in order.reports] if order.status == 'ready' else []})
    response['Cache-Control'] = 'no-store'
    return response


@login_required
def order_page(request, order_id):
    order = get_object_or_404(ZeldaOrder, pk=order_id, user=request.user)
    return render(request, 'billing/zelda_order.html', {'order': order, 'product_name': ALL_STRIPE_PRODUCTS[order.product][0]})


@login_required
@require_POST
def retry_order(request, order_id):
    from .tasks import fulfill_zelda_order
    with transaction.atomic():
        order = get_object_or_404(ZeldaOrder.objects.select_for_update(), pk=order_id, user=request.user)
        if order.status != 'failed' or not order.paid_at:
            return JsonResponse({'error': 'This report is not available for retry.'}, status=409)
        order.status = 'paid'
        order.save(update_fields=['status'])
        transaction.on_commit(lambda: fulfill_zelda_order.delay(str(order.id)))
    return JsonResponse({'status': 'paid'})


@login_required
def purchased_report(request, order_id, report_key):
    from .fulfillment import report_sections
    order = get_object_or_404(ZeldaOrder, pk=order_id, user=request.user, status='ready', paid_at__isnull=False)
    if report_key not in order.reports:
        raise Http404()
    from zelda_api.principal import Principal
    return render(request, 'billing/zelda_report.html', {
        'order': order, 'report_name': REPORTS[report_key][0],
        'sections': report_sections(order, report_key, Principal.from_request(request, 'purchased Zelda report')),
    })
