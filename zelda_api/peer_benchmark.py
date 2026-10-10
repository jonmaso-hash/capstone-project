import json
import logging
import re
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from matchmaking.models import (
    Application,
    PeerMarketBenchmark,
    SellerApplication,
    can_view_profile_field,
    restrict_queryset_for_field_filter,
)
from .anthropic_client import background_anthropic_client
from .peer_benchmark_evidence import (
    EVIDENCE_VERSION, METRICS as EXTERNAL_TARGETS, descriptive_summary,
    external_metrics, normalized_peers, source_set,
)

logger = logging.getLogger(__name__)

MIN_INTERLINK_PEERS = 5
INTERLINK_PRIVACY_VERSION = 2
INTERLINK_METRICS = {
    'founder': {'funding_raised': 'prior_amount_raised', 'current_raise': 'raising_amount',
                'employee_count': 'team_size', 'years_in_business': 'years_in_business'},
    'seller': {'annual_revenue': 'annual_revenue', 'ebitda': 'ebitda', 'asking_price': 'asking_price',
               'employee_count': 'team_size', 'years_in_business': 'years_in_business'},
}
EXTERNAL_METRICS = {
    'founder': {**INTERLINK_METRICS['founder'], 'latest_round_size': None},
    'seller': {**INTERLINK_METRICS['seller'], 'transaction_value': None,
               'asking_or_transaction_value': 'asking_price'},
}
ZERO_DEFAULT_FIELDS = {'prior_amount_raised', 'raising_amount', 'asking_price', 'years_in_business'}


def profile_number(profile, field):
    """A legacy zero default has no evidence of explicit disclosure."""
    return disclosed_number(getattr(profile, field), field)


def disclosed_number(value, field):
    value = as_number(value)
    return None if field in ZERO_DEFAULT_FIELDS and value == 0 else value


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
            'funding_raised': profile_number(profile, 'prior_amount_raised'),
            'current_raise': profile_number(profile, 'raising_amount'),
            'employee_count': profile.team_size,
            'years_in_business': profile_number(profile, 'years_in_business'),
            'revenue': as_number(profile.current_revenue),
        }
    return {
        'company_name': profile.company_name,
        'industry': profile.industry,
        'geography': profile.geography or '',
        'annual_revenue': as_number(profile.annual_revenue),
        'ebitda': as_number(profile.ebitda),
        'asking_price': profile_number(profile, 'asking_price'),
        'employee_count': profile.team_size,
        'years_in_business': profile_number(profile, 'years_in_business'),
    }


def cohort_groups(rows, geography):
    geo = geography_parts(geography)

    def same(row, level):
        if not can_view_profile_field(None, row, 'geography'):
            return False
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


def _visible_peer_value(viewer, peer, field):
    """Only include a peer's controlled field when Interlink's authority allows it."""
    if not can_view_profile_field(viewer, peer, field):
        return None
    return profile_number(peer, field)


def interlink_metric(value, peers):
    """Publish aggregates only with five publicly visible numeric contributors."""
    values = [x for x in peers if as_number(x) is not None]
    if len(values) < MIN_INTERLINK_PEERS:
        return {'value': as_number(value), 'median': None, 'percentile': None,
                'peer_values_available': 0}
    return metric(value, values)


def profile_metric(value, peers, field):
    visible = [(peer.pk, _visible_peer_value(None, peer, field)) for peer in peers]
    contributors = [(pk, number) for pk, number in visible if as_number(number) is not None]
    row = interlink_metric(value, [number for _, number in contributors])
    row['contributor_ids'] = [pk for pk, _ in contributors] if row['peer_values_available'] else []
    return row


def safe_interlink_snapshot(snapshot, role):
    """Fail closed on old snapshots: their aggregates had no privacy boundary.

    Used by both owner and public views, so existing share links are protected
    without regenerating reports or spending on external research.
    """
    output = {}
    model = Application if role == 'founder' else SellerApplication
    fields = INTERLINK_METRICS.get(role, {})
    for level in ('site', 'city', 'state', 'country'):
        cohort = snapshot.get(level, {}) if isinstance(snapshot, dict) else {}
        safe = {'peer_count': 0, 'metrics': {}}
        if (isinstance(cohort, dict)
                and cohort.get('privacy_version') == INTERLINK_PRIVACY_VERSION
                and isinstance(cohort.get('peer_count'), int)
                and cohort['peer_count'] >= MIN_INTERLINK_PEERS):
            ids = cohort.get('peer_ids')
            if (not isinstance(ids, list) or any(type(pk) is not int for pk in ids)
                    or len(set(ids)) != cohort['peer_count']):
                output[level] = safe
                continue
            peers = {peer.pk: peer for peer in model.objects.discoverable().filter(pk__in=ids)}
            cohort_fields = (('sector', 'stage') if role == 'founder' else ('industry',))
            if level != 'site':
                cohort_fields += ('geography',)
            if (len(peers) != len(ids) or any(
                    not can_view_profile_field(None, peer, field)
                    for peer in peers.values() for field in cohort_fields)):
                output[level] = safe
                continue
            safe['peer_count'] = cohort['peer_count']
            metrics = cohort.get('metrics', {})
            if isinstance(metrics, dict):
                for name, row in metrics.items():
                    if name not in fields or not isinstance(row, dict):
                        continue
                    count = row.get('peer_values_available')
                    contributors = row.get('contributor_ids')
                    if (isinstance(count, int) and count >= MIN_INTERLINK_PEERS
                            and isinstance(contributors, list)
                            and all(type(pk) is int for pk in contributors)
                            and len(set(contributors)) == count
                            and all(pk in peers and _visible_peer_value(None, peers[pk], fields[name]) is not None
                                    for pk in contributors)):
                        safe['metrics'][name] = {key: row.get(key) for key in (
                            'value', 'median', 'percentile', 'peer_values_available',
                        )}
                    else:
                        safe['metrics'][name] = interlink_metric(row.get('value'), [])
        output[level] = safe
    return output


def interlink_benchmark(profile, role):
    if role == 'founder':
        base = Application.objects.discoverable()
        # Cohort membership also discloses a field; authorize before filtering.
        for field in ('sector', 'stage'):
            base = restrict_queryset_for_field_filter(base, None, field)
        base = base.filter(
            sector__iexact=profile.sector,
            stage__iexact=profile.stage,
        ).exclude(pk=profile.pk)
    else:
        base = SellerApplication.objects.discoverable().filter(
            industry__iexact=profile.industry,
        ).exclude(pk=profile.pk)
    groups = cohort_groups(base, profile.geography)

    output = {}
    for level, peers in groups.items():
        if len(peers) < MIN_INTERLINK_PEERS:
            output[level] = {'peer_count': 0, 'metrics': {}, 'privacy_version': INTERLINK_PRIVACY_VERSION}
            continue
        metrics = {name: profile_metric(profile_number(profile, field), peers, field)
                   for name, field in INTERLINK_METRICS[role].items()}
        output[level] = {'peer_count': len(peers), 'metrics': metrics,
                         'peer_ids': [peer.pk for peer in peers],
                         'privacy_version': INTERLINK_PRIVACY_VERSION}
    return output


INTERLINK_LEVELS = ('site', 'city', 'state', 'country')


def interlink_snapshot_is_current(snapshot):
    return isinstance(snapshot, dict) and all(
        isinstance(snapshot.get(level), dict)
        and snapshot[level].get('privacy_version') == INTERLINK_PRIVACY_VERSION
        for level in INTERLINK_LEVELS
    )


def interlink_recalculated_at(snapshot):
    """When a stored Interlink half was rebuilt after its report was generated."""
    meta = snapshot.get('recalculated') if isinstance(snapshot, dict) else None
    return parse_datetime(meta.get('at') or '') if isinstance(meta, dict) else None


def refresh_interlink_snapshot(benchmark_id):
    """One-time rebuild of an Interlink half saved under older privacy rules.

    Only the Interlink half is recalculated, from current data under current
    public-viewer rules. External research is never called, and the external
    half, sources, narrative and the owner's 30-day refresh allowance are left
    exactly as saved. The rebuild date is stored so the page can say the two
    halves describe different dates. Returns True only when a row changed.
    """
    with transaction.atomic():
        benchmark = (
            PeerMarketBenchmark.objects.select_for_update()
            .filter(pk=benchmark_id).first()
        )
        # Both profile relations are nullable. Lock only the benchmark row;
        # PostgreSQL cannot apply FOR UPDATE to a nullable outer-join side.
        # A report may also have been deleted since the command listed it.
        if benchmark is None:
            return False
        old = benchmark.interlink_benchmark
        if benchmark.status != 'ready' or interlink_snapshot_is_current(old):
            return False
        profile = benchmark.founder if benchmark.role == 'founder' else benchmark.seller
        if profile is None or benchmark.role not in INTERLINK_METRICS:
            return False
        site = old.get('site') if isinstance(old, dict) else None
        snapshot = interlink_benchmark(profile, benchmark.role)
        snapshot['recalculated'] = {
            'at': timezone.now().isoformat(),
            'from_privacy_version': site.get('privacy_version') if isinstance(site, dict) else None,
        }
        benchmark.interlink_benchmark = snapshot
        benchmark.save(update_fields=['interlink_benchmark'])
        return True


def protect_public_subject(benchmark):
    """Apply current public permissions to a report instance, never its saved data.

    Mask derived percentiles as well as values. Free text was generated with
    owner data and cannot be reliably redacted, so withhold it when any supplied
    subject field is private. Missing subject profiles fail closed.
    """
    profile = benchmark.founder if benchmark.role == 'founder' else benchmark.seller
    fields = EXTERNAL_METRICS.get(benchmark.role, {})
    cohort_fields = ('sector', 'stage', 'geography') if benchmark.role == 'founder' else ('industry', 'geography')

    def public(field):
        return field is None or profile is not None and can_view_profile_field(None, profile, field)

    def mask(rows, mapping):
        output = {}
        for name, row in rows.items() if isinstance(rows, dict) else []:
            if name not in mapping or not isinstance(row, dict):
                continue
            output[name] = dict(row)
            output[name]['groups'] = [dict(group) for group in row.get('groups', [])]
            if not public(mapping[name]):
                output[name]['value'] = None
                output[name]['percentile'] = None
                for group in output[name]['groups']:
                    group['value'], group['percentile'] = None, None
                    group['comparison_note'] = 'Your figure is not publicly disclosed.'
        return output

    benchmark.external_benchmark = mask(benchmark.external_benchmark, fields)
    for level, cohort in benchmark.interlink_benchmark.items():
        if (not all(public(field) for field in cohort_fields if field != 'geography')
                or level != 'site' and not public('geography')):
            cohort['peer_count'], cohort['metrics'] = 0, {}
        else:
            cohort['metrics'] = mask(cohort['metrics'], INTERLINK_METRICS.get(benchmark.role, {}))
    supplied_fields = {field for field in fields.values() if field} | set(cohort_fields)
    if benchmark.role == 'founder':
        supplied_fields.add('current_revenue')
    if not all(public(field) for field in supplied_fields):
        benchmark.narrative = ''
        benchmark.cohort_label = ''
        benchmark.sources = [{key: source.get(key) for key in ('url', 'title')}
                             for source in benchmark.sources if isinstance(source, dict)]
        # The existing P-1 rule withholds citation excerpts when supplied
        # subject fields are private. New per-figure excerpts obey it too.
        # The source's own name for the company is quoted text too.
        for peer in benchmark.external_peers:
            for figure in peer.get('figures', []):
                figure['source_quote'] = figure['source_company_name'] = ''
            for fact in peer.get('facts', {}).values():
                fact['source_quote'] = fact['source_company_name'] = ''
        for row in benchmark.external_benchmark.values():
            for group in row.get('groups', []):
                for figure in group.get('figures', []):
                    figure['source_quote'] = figure['source_company_name'] = ''
    if not all(public(field) for field in cohort_fields):
        benchmark.external_benchmark = {}
        benchmark.external_peers = []
        benchmark.sources = []
    benchmark.subject_snapshot = {}


def safe_external_snapshot(snapshot, role):
    """A numeric snapshot alone cannot establish its source figures.

    Readers with full frozen evidence use prepare_external_report instead.
    This compatibility helper preserves subject values but never trusts old
    stored medians, percentiles or sample counts.
    """
    output = {}
    for name, row in snapshot.items() if isinstance(snapshot, dict) else []:
        field = EXTERNAL_METRICS.get(role, {}).get(name)
        if name not in EXTERNAL_METRICS.get(role, {}) or not isinstance(row, dict):
            continue
        output[name] = {'value': disclosed_number(row.get('value'), field) if field else None,
                        'median': None, 'percentile': None, 'peer_values_available': 0}
    return output


def prepare_external_report(benchmark):
    """Rebuild the displayed external half from frozen evidence, without I/O.

    No saved report is rewritten and no research/refresh allowance is used.
    Legacy model prose can repeat unsupported comparisons, so it is replaced
    by a deterministic description of the figures that survived admission.
    """
    snapshot = benchmark.external_benchmark
    current = isinstance(snapshot, dict) and bool(snapshot) and all(
        isinstance(row, dict) and row.get('evidence_version') == EVIDENCE_VERSION
        for row in snapshot.values())
    peers = normalized_peers(benchmark.external_peers, benchmark.sources, benchmark.role)
    subject = dict(benchmark.subject_snapshot) if current and isinstance(benchmark.subject_snapshot, dict) else {}
    if not current:
        benchmark.cohort_label = ''
        # Legacy latest-round comparisons used the current fundraising target.
        legacy = dict(snapshot) if isinstance(snapshot, dict) else {}
        if 'latest_round_size' in legacy:
            legacy.setdefault('current_raise', legacy.pop('latest_round_size'))
        if 'asking_or_transaction_value' in legacy:
            legacy.setdefault('asking_price', legacy.pop('asking_or_transaction_value'))
        subject = {name: row['value'] for name, row in safe_external_snapshot(legacy, benchmark.role).items()}
        for peer in peers:
            peer['facts'], peer['figures'] = {}, []
    benchmark.external_provenance_legacy = not current
    benchmark.external_peers = peers
    benchmark.sources = source_set(benchmark.sources)
    benchmark.external_benchmark = external_metrics(benchmark.role, subject, peers)
    benchmark.narrative = descriptive_summary(peers)


def extract_text_and_sources(response):
    text_parts = []
    sources = []
    for block in getattr(response, 'content', []) or []:
        if getattr(block, 'type', None) != 'text':
            continue
        text_parts.append(getattr(block, 'text', '') or '')
        for citation in getattr(block, 'citations', []) or []:
            url = getattr(citation, 'url', None)
            if not url:
                continue
            sources.append({
                'url': url,
                'title': getattr(citation, 'title', None) or url,
                'cited_text': getattr(citation, 'cited_text', '') or '',
            })
    return ''.join(text_parts).strip(), source_set(sources)


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
        instructions = (
            'Find 8-15 identifiable private-company peers. Prefer sourced facts for funding raised, '
            'latest round size, employee count, founding year, sector, stage, and location.'
        )
    else:
        cohort = str(subject.get('industry') or 'business')
        instructions = (
            'Find 8-15 identifiable comparable operating businesses or disclosed M&A/listing comparables. '
            'Prefer sourced annual revenue, annual EBITDA, employee count, years in business, '
            'asking price and completed transaction value. Keep asking prices separate from completed transactions.'
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
    "facts": {"METRIC_NAME": {
      "value": 1000000, "unit": "USD", "basis": "BASIS_NAME",
      "as_of": "2025-12-31", "period_kind": null, "period_end": null,
      "source_url": "https://...", "source_quote": "Exact source passage including company and figure"
    }}
  }],
  "summary": "2-4 neutral sentences describing the disclosed comparison and data gaps."
}
Only collect these metrics: METRIC_NAMES.
Allowed measurement bases: BASIS_NAMES.
Each fact needs its own real web-search citation, URL and exact cited passage.
The quote must name the peer and contain the figure, explicit currency/unit,
measurement basis and date. A bare $ symbol does not establish USD.
For annual reported revenue/EBITDA, use period_kind="annual" and the documented
period_end date; do not infer a calendar-year end from a year label. For other
metrics, as_of is the documented measurement or event date, not today's date.
Use null for missing metadata. Never estimate, annualise, convert currency or
borrow parent-company financials. ARR, TTM, adjusted EBITDA and LinkedIn profile
counts are not the requested reported annual revenue/EBITDA or employee count.
Current fundraising targets, completed equity rounds, asking prices, completed
transactions, enterprise value, equity value and asset-sale prices are separate.
'''
    prompt = prompt.replace('SUBJECT_NAME', subject['company_name'])
    prompt = prompt.replace('ROLE', role)
    prompt = prompt.replace('COHORT', cohort)
    prompt = prompt.replace('GEOGRAPHY', subject.get('geography') or 'not specified')
    prompt = prompt.replace('SUBJECT_JSON', json.dumps(subject, default=str))
    prompt = prompt.replace('INSTRUCTIONS', instructions)
    from .peer_benchmark_evidence import BASES
    prompt = prompt.replace('METRIC_NAMES', ', '.join(EXTERNAL_TARGETS[role]))
    prompt = prompt.replace('BASIS_NAMES', json.dumps({name: BASES[name] for name in EXTERNAL_TARGETS[role]}))

    client = background_anthropic_client()
    response = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=8000,
        messages=[{'role': 'user', 'content': prompt}],
        tools=[{'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': 8}],
    )
    text, sources = extract_text_and_sources(response)
    data = parse_json(text)
    peers = normalized_peers(data.get('peers'), sources, role)
    metrics = external_metrics(role, subject, peers)

    return {
        'cohort_label': cohort,
        'peers': peers,
        'metrics': metrics,
        'sources': sources,
        'summary': descriptive_summary(peers),
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
