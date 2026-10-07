import json
import logging
import re
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count
from django.utils import timezone

from matchmaking.models import (
    AcquisitionInterestEvent,
    Application,
    InvestorInterestEvent,
    PeerMarketBenchmark,
    SellerApplication,
)
from .anthropic_client import background_anthropic_client

logger = logging.getLogger(__name__)


def as_number(value):
    if value in (None, ''):
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def median(values):
    vals = sorted(v for v in (as_number(x) for x in values) if v is not None)
    if not vals:
        return None
    mid = len(vals) // 2
    if len(vals) % 2:
        return vals[mid]
    return round((vals[mid - 1] + vals[mid]) / 2, 2)


def percentile(subject, values):
    subject = as_number(subject)
    vals = [v for v in (as_number(x) for x in values) if v is not None]
    if subject is None or not vals:
        return None
    return round(100 * sum(1 for value in vals if value <= subject) / len(vals))


def geography_parts(value):
    parts = [part.strip() for part in (value or '').split(',') if part.strip()]
    return {
        'city': parts[0] if parts else '',
        'state': parts[-2] if len(parts) >= 2 else '',
        'country': parts[-1] if len(parts) >= 2 else '',
    }


def subject_snapshot(profile, role):
    if role == 'founder':
        return {
            'company_name': profile.company_name,
            'sector': profile.sector,
            'stage': profile.stage,
            'geography': profile.geography or '',
            'funding_raised': as_number(profile.prior_amount_raised),
            'current_raise': as_number(profile.raising_amount),
            'employee_count': profile.team_size,
            'years_in_business': profile.years_in_business,
            'revenue': as_number(profile.current_revenue),
        }
    return {
        'company_name': profile.company_name,
        'industry': profile.industry,
        'geography': profile.geography or '',
        'annual_revenue': as_number(profile.annual_revenue),
        'ebitda': as_number(profile.ebitda),
        'asking_price': as_number(profile.asking_price),
        'employee_count': profile.team_size,
        'years_in_business': profile.years_in_business,
    }


def cohort_groups(rows, geography):
    geo = geography_parts(geography)

    def same(row, level):
        expected = geo.get(level) or ''
        actual = geography_parts(getattr(row, 'geography', '')).get(level) or ''
        return bool(expected) and expected.lower() == actual.lower()

    rows = list(rows)
    return {
        'site': rows,
        'city': [row for row in rows if same(row, 'city')],
        'state': [row for row in rows if same(row, 'state')],
        'country': [row for row in rows if same(row, 'country')],
    }


def metric(value, peers):
    return {
        'value': as_number(value),
        'median': median(peers),
        'percentile': percentile(value, peers),
        'peer_values_available': len([x for x in peers if as_number(x) is not None]),
    }


def interlink_benchmark(profile, role):
    if role == 'founder':
        base = Application.objects.discoverable().filter(
            sector__iexact=profile.sector,
            stage__iexact=profile.stage,
        ).exclude(pk=profile.pk)
        event_model = InvestorInterestEvent
        owner_field = 'founder_id'
        subject_events = event_model.objects.filter(founder=profile)
    else:
        base = SellerApplication.objects.discoverable().filter(
            industry__iexact=profile.industry,
        ).exclude(pk=profile.pk)
        event_model = AcquisitionInterestEvent
        owner_field = 'seller_id'
        subject_events = event_model.objects.filter(seller=profile)

    interest_types = ('thumbs_up', 'intro_request', 'message_sent', 'analyze', 'memo_view', 'truth_delta_view')
    subject_interest = subject_events.filter(event_type__in=interest_types).count()
    groups = cohort_groups(base, profile.geography)

    output = {}
    for level, peers in groups.items():
        if not peers:
            output[level] = {'peer_count': 0, 'metrics': {}}
            continue
        ids = [peer.id for peer in peers]
        counts = dict(
            event_model.objects.filter(
                **{owner_field + '__in': ids},
                event_type__in=interest_types,
            ).values(owner_field).annotate(n=Count('id')).values_list(owner_field, 'n')
        )
        if role == 'founder':
            metrics = {
                'investor_interest_events': metric(subject_interest, [counts.get(peer.id, 0) for peer in peers]),
                'funding_raised': metric(profile.prior_amount_raised, [peer.prior_amount_raised for peer in peers]),
                'current_raise': metric(profile.raising_amount, [peer.raising_amount for peer in peers]),
                'employee_count': metric(profile.team_size, [peer.team_size for peer in peers]),
                'years_in_business': metric(profile.years_in_business, [peer.years_in_business for peer in peers]),
            }
        else:
            metrics = {
                'buyer_interest_events': metric(subject_interest, [counts.get(peer.id, 0) for peer in peers]),
                'annual_revenue': metric(profile.annual_revenue, [peer.annual_revenue for peer in peers]),
                'ebitda': metric(profile.ebitda, [peer.ebitda for peer in peers]),
                'asking_price': metric(profile.asking_price, [peer.asking_price for peer in peers]),
                'employee_count': metric(profile.team_size, [peer.team_size for peer in peers]),
                'years_in_business': metric(profile.years_in_business, [peer.years_in_business for peer in peers]),
            }
        output[level] = {'peer_count': len(peers), 'metrics': metrics}
    return output


def extract_text_and_sources(response):
    text_parts = []
    sources = []
    seen = set()
    for block in getattr(response, 'content', []) or []:
        if getattr(block, 'type', None) != 'text':
            continue
        text_parts.append(getattr(block, 'text', '') or '')
        for citation in getattr(block, 'citations', []) or []:
            url = getattr(citation, 'url', None)
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append({
                'url': url,
                'title': getattr(citation, 'title', None) or url,
                'cited_text': getattr(citation, 'cited_text', '') or '',
            })
    return ''.join(text_parts).strip(), sources


def parse_json(text):
    cleaned = text.strip()
    cleaned = re.sub(r'^`(?:json)?\s*', '', cleaned, flags=re.I)
    cleaned = re.sub(r'\s*`$','', cleaned)
    start = cleaned.find('{')
    end = cleaned.rfind('}')
    if start < 0 or end < start:
        raise ValueError('External benchmark research did not return JSON.')
    return json.loads(cleaned[start:end + 1])


def external_research(role, subject):
    if role == 'founder':
        cohort = (str(subject.get('stage') or '') + ' ' + str(subject.get('sector') or '')).strip()
        target_metrics = ('funding_raised', 'latest_round_size', 'employee_count', 'years_in_business')
        instructions = (
            'Find 8-15 identifiable private-company peers. Prefer sourced facts for funding raised, '
            'latest round size, employee count, founding year, sector, stage, and location.'
        )
    else:
        cohort = str(subject.get('industry') or 'business')
        target_metrics = ('annual_revenue', 'ebitda', 'asking_or_transaction_value', 'employee_count', 'years_in_business')
        instructions = (
            'Find 8-15 identifiable comparable operating businesses or disclosed M&A/listing comparables. '
            'Prefer sourced revenue, EBITDA, employee count, founding year, asking price or disclosed transaction value.'
        )

    prompt = '''
Build a factual Peer Market Benchmark for SUBJECT_NAME.
Role: ROLE
Target cohort: COHORT
Target geography: GEOGRAPHY
Subject data supplied by the owner: SUBJECT_JSON

INSTRUCTIONS
Search the web for current, citable public sources. Do not rank business quality, recommend an investment,
or predict transaction success. Only collect descriptive peer facts. Use null where a figure is not publicly
established. Do not estimate hidden figures.

Return exactly one JSON object:
{
  "cohort_label": "...",
  "peers": [{
    "company_name": "...",
    "location": "...",
    "sector_or_industry": "...",
    "stage_or_type": "...",
    "funding_raised": null,
    "latest_round_size": null,
    "annual_revenue": null,
    "ebitda": null,
    "asking_or_transaction_value": null,
    "employee_count": null,
    "years_in_business": null
  }],
  "summary": "2-4 neutral sentences describing the disclosed comparison and data gaps."
}
'''
    prompt = prompt.replace('SUBJECT_NAME', subject['company_name'])
    prompt = prompt.replace('ROLE', role)
    prompt = prompt.replace('COHORT', cohort)
    prompt = prompt.replace('GEOGRAPHY', subject.get('geography') or 'not specified')
    prompt = prompt.replace('SUBJECT_JSON', json.dumps(subject, default=str))
    prompt = prompt.replace('INSTRUCTIONS', instructions)

    client = background_anthropic_client()
    response = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=5000,
        messages=[{'role': 'user', 'content': prompt}],
        tools=[{'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': 8}],
    )
    text, sources = extract_text_and_sources(response)
    data = parse_json(text)
    peers = data.get('peers') or []

    subject_map = {
        'funding_raised': subject.get('funding_raised'),
        'latest_round_size': subject.get('current_raise'),
        'annual_revenue': subject.get('annual_revenue'),
        'ebitda': subject.get('ebitda'),
        'asking_or_transaction_value': subject.get('asking_price'),
        'employee_count': subject.get('employee_count'),
        'years_in_business': subject.get('years_in_business'),
    }
    metrics = {}
    for name in target_metrics:
        values = [peer.get(name) for peer in peers if isinstance(peer, dict)]
        metrics[name] = metric(subject_map.get(name), values)

    return {
        'cohort_label': data.get('cohort_label') or cohort,
        'peers': peers,
        'metrics': metrics,
        'sources': sources,
        'summary': data.get('summary') or '',
    }


def generate_benchmark(benchmark_id):
    benchmark = PeerMarketBenchmark.objects.select_related('founder', 'seller', 'user').get(pk=benchmark_id)
    benchmark.status = 'running'
    benchmark.error_message = ''
    benchmark.save(update_fields=['status', 'error_message'])
    try:
        profile = benchmark.founder if benchmark.role == 'founder' else benchmark.seller
        subject = subject_snapshot(profile, benchmark.role)
        internal = interlink_benchmark(profile, benchmark.role)
        external = external_research(benchmark.role, subject)
        now = timezone.now()

        benchmark.subject_snapshot = subject
        benchmark.interlink_benchmark = internal
        benchmark.external_peers = external['peers']
        benchmark.external_benchmark = external['metrics']
        benchmark.sources = external['sources']
        benchmark.cohort_label = external['cohort_label']
        benchmark.narrative = external['summary']
        benchmark.status = 'ready'
        benchmark.generated_at = now
        benchmark.refresh_eligible_at = now + timedelta(days=30)
        benchmark.save(update_fields=[
            'subject_snapshot', 'interlink_benchmark', 'external_peers', 'external_benchmark',
            'sources', 'cohort_label', 'narrative', 'status', 'generated_at', 'refresh_eligible_at',
        ])
        return benchmark
    except Exception as exc:
        logger.exception('Peer Market Benchmark generation failed for %s', benchmark_id)
        benchmark.status = 'failed'
        benchmark.error_message = str(exc)[:1000]
        benchmark.save(update_fields=['status', 'error_message'])
        raise


def create_monthly_benchmark(user, role):
    founder = getattr(user, 'match_founder_profile', None) if role == 'founder' else None
    seller = getattr(user, 'match_seller_profile', None) if role == 'seller' else None
    profile = founder or seller

    if role not in ('founder', 'seller') or not profile or not getattr(profile, 'is_premium', False):
        raise PermissionError('Peer Market Benchmark requires Founder or Seller Premium.')

    latest = PeerMarketBenchmark.objects.filter(user=user, role=role).first()
    if latest and latest.status in ('pending', 'running'):
        return latest, False
    if latest and latest.refresh_eligible_at and timezone.now() < latest.refresh_eligible_at:
        return latest, False
    if latest and latest.status == 'failed' and latest.created_at > timezone.now() - timedelta(hours=1):
        # A temporary provider/search failure must not turn page refreshes
        # into repeated paid web-search attempts.
        return latest, False

    benchmark = PeerMarketBenchmark.objects.create(
        user=user,
        role=role,
        subject_name=profile.company_name,
        founder=founder if role == 'founder' else None,
        seller=seller if role == 'seller' else None,
    )
    return benchmark, True
