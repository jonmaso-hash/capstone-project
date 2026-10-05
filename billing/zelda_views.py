"""One-time Checkout and owner-scoped report purchases for the Zelda hub."""
import json
import logging
import hashlib
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
from .models import ZeldaOrder
from .zelda_catalog import PRODUCTS, REPORTS, catalog, selected_reports

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
    name, amount, _ = PRODUCTS[product]
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
    return JsonResponse({'products': catalog(), 'reports': [{'key': key, 'name': value[0]} for key, value in REPORTS.items()]})


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
        if product not in PRODUCTS:
            raise ValueError()
        document_id = int(data['document_id'])
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'error': 'Select a product, evidence and the required reports.'}, status=400)
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
                                             reports=reports, amount=PRODUCTS[product][1])
    if order.checkout_url:
        return JsonResponse({'checkout_url': order.checkout_url})
    try:
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
        order.stripe_session_id, order.checkout_url = session['id'], session['url']
        order.save(update_fields=['stripe_session_id', 'checkout_url'])
    except ProductPaymentConfigurationError:
        logger.exception('Zelda product payment configuration unavailable for order %s', order.id)
        return JsonResponse({'error': 'Payments are not configured for this product yet. Please try again later. Nothing was charged.'}, status=503)
    except Exception:
        logger.exception('Could not create Zelda product checkout %s', order.id)
        return JsonResponse({'error': 'Checkout is currently unavailable. Nothing was charged. Please try again.'}, status=503)
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


def recover_order_payment(order):
    """Recover missed webhooks/queue delivery without creating another charge.

    Poll only the owner's stored session, at most once every 15 seconds. Cached
    checkout state is display information, never authorization to fulfill.
    """
    if order.status not in ('awaiting_payment', 'paid'):
        return {}
    account = hashlib.sha256(settings.STRIPE_SECRET_KEY.encode()).hexdigest()[:12]
    key = f'zelda_payment_check:{account}:{order.id}'
    details = cache.get(key + ':display') or {}
    if not cache.add(key, True, 15):
        return details
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
    cache.set(key + ':display', details, 15)
    return details


@login_required
def order_status(request, order_id):
    from .fulfillment import reconcile_order
    order = get_object_or_404(ZeldaOrder, pk=order_id, user=request.user)
    payment_details = recover_order_payment(order)
    reconcile_order(order)
    response = JsonResponse({'status': order.status, **payment_details, 'reports': [
        {'name': REPORTS[key][0], 'url': reverse('billing:zelda_report', args=[order.id, key])}
        for key in order.reports] if order.status == 'ready' else []})
    response['Cache-Control'] = 'no-store'
    return response


@login_required
def order_page(request, order_id):
    order = get_object_or_404(ZeldaOrder, pk=order_id, user=request.user)
    return render(request, 'billing/zelda_order.html', {'order': order, 'product_name': PRODUCTS[order.product][0]})


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
