"""Source-linked peer figures, with deterministic admission and comparison.

A citation is traceability, not independent verification. We require an actual
provider citation excerpt containing the figure, rather than accepting a URL
or a model-authored quote. Unit, meaning and measurement dates must be known
before a figure contributes to a comparison. Nothing converts currencies,
annualises figures or fills in missing dates.
"""
import math
import re
from collections import defaultdict
from datetime import date
from urllib.parse import urlsplit

EVIDENCE_VERSION = 1
MIN_EXTERNAL_PEERS = 3
METRICS = {
    'founder': ('funding_raised', 'current_raise', 'latest_round_size', 'employee_count', 'years_in_business'),
    'seller': ('annual_revenue', 'ebitda', 'asking_price', 'transaction_value', 'employee_count', 'years_in_business'),
}
LABELS = {
    'funding_raised': 'Cumulative funding raised', 'current_raise': 'Current fundraising target',
    'latest_round_size': 'Latest completed round', 'annual_revenue': 'Annual reported revenue',
    'ebitda': 'Annual reported EBITDA', 'asking_price': 'Asking price',
    'transaction_value': 'Completed transaction value', 'employee_count': 'Employee count',
    'years_in_business': 'Years in business',
}
BASES = {
    'funding_raised': ('total_equity_funding', 'total_funding'),
    'current_raise': ('fundraising_target',), 'latest_round_size': ('completed_equity_round',),
    'annual_revenue': ('reported_revenue',), 'ebitda': ('reported_ebitda',),
    'asking_price': ('enterprise_value', 'equity_value', 'asset_sale_price'),
    'transaction_value': ('enterprise_value', 'equity_value', 'asset_sale_price'),
    'employee_count': ('employees',), 'years_in_business': ('operating_years',),
}
COUNT_UNITS = {'employee_count': 'employees', 'years_in_business': 'years'}
CURRENCY_WORDS = {
    'USD': ('USD', 'US$', 'U.S. dollars', 'US dollars'),
    'CAD': ('CAD', 'C$', 'Canadian dollars'), 'AUD': ('AUD', 'A$', 'Australian dollars'),
    'NZD': ('NZD', 'NZ$', 'New Zealand dollars'), 'EUR': ('EUR', '€', 'euros'),
    'GBP': ('GBP', '£', 'pounds sterling'), 'JPY': ('JPY', 'Japanese yen'),
    'CNY': ('CNY', 'Chinese yuan'), 'INR': ('INR', 'Indian rupees'),
    'CHF': ('CHF', 'Swiss francs'), 'SGD': ('SGD', 'Singapore dollars'),
    'HKD': ('HKD', 'Hong Kong dollars'), 'MXN': ('MXN', 'Mexican pesos'),
    'BRL': ('BRL', 'Brazilian reais'), 'ZAR': ('ZAR', 'South African rand'),
}


def finite_number(value):
    if isinstance(value, bool) or value in (None, ''):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def public_url(value):
    if not isinstance(value, str) or any(c.isspace() for c in value):
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme in ('http', 'https') and parts.hostname and not parts.username and not parts.password:
            return value
    except ValueError:
        pass
    return None


def _text(value):
    return ' '.join(value.split()) if isinstance(value, str) else ''


def company_key(value):
    value = re.sub(r'[^a-z0-9 ]', ' ', _text(value).lower())
    value = re.sub(r'\b(inc|incorporated|corp|corporation|llc|limited|ltd)\b', '', value)
    return _text(value)


_LEGAL_SUFFIXES = {'inc', 'incorporated', 'corp', 'corporation', 'llc', 'limited', 'ltd', 'co', 'company', 'plc'}
_NAME_WORD = r"[A-Z][\w&-]*"


def longer_source_name(name, quote):
    """The fuller company name a quote uses around the peer's name, or None.

    Matching stays tolerant: "Acme Brands" still supports a figure for the
    peer "Acme", because genuine name variants look the same ("Notion" and
    "Notion Labs"). This only reports the longer name so a reader can check
    the attribution. Capitalised words directly before or after the peer's
    name are treated as part of a longer name; legal suffixes are not, and a
    word that merely starts the sentence is ignored, accepting a missed
    notice over a misleading one.
    """
    words = company_key(name).split()
    if not words:
        return None
    pattern = r'(?<!\w)' + r'\W+'.join(re.escape(w) for w in words) + r'(?!\w)'
    for match in re.finditer(pattern, quote, re.I):
        before = re.search(r'((?:' + _NAME_WORD + r'\s+)+)$', quote[:match.start()])
        prefix = before[1].split() if before else []
        start = before.start(1) if before else match.start()
        if prefix and (start == 0 or re.search(r'[.!?]\s*$', quote[:start])):
            prefix = prefix[1:]  # sentence-initial capital, not evidence of a name
        after = re.match(r'((?:\s+' + _NAME_WORD + r')+)', quote[match.end():])
        suffix = after[1].split() if after else []
        while suffix and suffix[-1].lower().strip('.') in _LEGAL_SUFFIXES:
            suffix.pop()
        if prefix or suffix:
            return ' '.join(prefix + [match[0]] + suffix)
    return None


def source_set(sources):
    """Retain every distinct excerpt for a URL, not just its first citation."""
    output = {}
    for source in sources if isinstance(sources, list) else []:
        if not isinstance(source, dict) or not public_url(source.get('url')):
            continue
        url = source['url']
        row = output.setdefault(url, {'url': url, 'title': _text(source.get('title')) or url, 'excerpts': []})
        excerpts = source.get('excerpts')
        excerpts = excerpts if isinstance(excerpts, list) else [source.get('cited_text')]
        for excerpt in excerpts:
            excerpt = _text(excerpt)
            if excerpt and excerpt not in row['excerpts']:
                row['excerpts'].append(excerpt)
        row['cited_text'] = '\n'.join(row['excerpts'])
    return list(output.values())


def _quoted_number(value, quote, metric):
    # Require a unit-bound figure, not a matching date or company-name digit.
    # Passages containing different amounts are ambiguous and stay out.
    amount = r'(-?\d[\d,]*(?:\.\d+)?)\s*(billion|million|thousand|bn|[bmk])?\b'
    currency = r'(?:' + '|'.join(re.escape(w) for words in CURRENCY_WORDS.values() for w in words) + r'|\$)'
    if metric in COUNT_UNITS:
        unit = r'(?:employees|employee headcount)' if metric == 'employee_count' else r'(?:years in business|years of operation|operating years)'
        patterns = (amount + r'\s*' + unit, unit + r'\s*(?:of|:)?\s*' + amount)
    else:
        patterns = (currency + r'\s*' + amount, amount + r'\s*' + currency)
    values = set()
    for pattern in patterns:
        for match in re.finditer(pattern, quote, re.I):
            number = float(match[1].replace(',', ''))
            scale = (match[2] or '').lower()
            number *= {'billion': 1e9, 'bn': 1e9, 'b': 1e9, 'million': 1e6, 'm': 1e6,
                       'thousand': 1e3, 'k': 1e3}.get(scale, 1)
            values.add(number)
    return values == {value}


def _source_date(value, quote):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    if parsed > date.today():
        return None
    variants = (value, parsed.strftime('%B %d, %Y'), parsed.strftime('%b %d, %Y'),
                f'{parsed:%B} {parsed.day}, {parsed.year}', f'{parsed:%b} {parsed.day}, {parsed.year}')
    return value if any(v.lower() in quote.lower() for v in variants) else None


def _currency_in_quote(unit, quote):
    amount = r'-?\d[\d,]*(?:\.\d+)?\s*(?:billion|million|thousand|bn|[bmk])?\b'
    for word in CURRENCY_WORDS.get(unit, ()):
        end = r'(?!\w)' if word[-1].isalnum() else ''
        prefix = r'(?<!\w)' + re.escape(word) + r'\s*' + amount
        suffix = amount + r'\s*' + re.escape(word) + end
        if re.search(prefix, quote, re.I) or re.search(suffix, quote, re.I):
            return True
    return False


def _basis_in_quote(metric, basis, quote):
    text = quote.lower()
    if metric == 'funding_raised':
        return bool(re.search(r'\b(total|cumulative)\b', text) and 'funding' in text
                    and not re.search(r'\b(seeking|target|raising|planned|projected)\b', text)
                    and (basis != 'total_equity_funding' or 'equity' in text))
    if metric == 'current_raise':
        return bool(re.search(r'\b(seeking|raising|target)\b', text))
    if metric == 'latest_round_size':
        return bool(re.search(r'\b(raised|closed|completed)\b', text) and 'round' in text
                    and re.search(r'\b(equity|series)\b', text))
    if metric in ('asking_price', 'transaction_value'):
        kind = (bool(re.search(r'\b(asking|listed|listing)\b', text)) if metric == 'asking_price'
                else bool(re.search(r'\b(completed|closed|acquired|sold)\b', text)
                          and not re.search(r'\b(pending|proposed|expected|anticipated)\b', text)))
        return kind and basis.replace('_', ' ') in text
    if metric == 'annual_revenue':
        return 'revenue' in text and not re.search(r'\b(arr|ttm|run.rate|recurring|forecast|projected|estimated|guidance|target|expected)\b', text)
    if metric == 'ebitda':
        return 'ebitda' in text and not re.search(r'\b(adjusted|forecast|projected|estimated|guidance|target|expected)\b', text)
    if metric == 'employee_count':
        return bool(re.search(r'\b(employees|employee headcount)\b', text)) and 'linkedin' not in text
    return bool(re.search(r'\b(years in business|years of operation|operating years)\b', text))


# A sentence ends at . ! or ? followed by whitespace and a capital letter, so
# decimals ("12.5 million") and most lowercase-continued abbreviations do not
# split a sentence. Excerpts are whitespace-collapsed by _text.
_SENTENCE_BREAK = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')


def quote_contexts(quote, excerpts):
    """Every source sentence span that contains the quote, in each excerpt.

    The model chooses where a quote starts and ends, so a qualifier just
    outside it ("Analysts estimated that ...") would otherwise go unseen. The
    span runs from the start of the sentence holding the quote's first word to
    the end of the sentence holding its last, and no further: another
    company's projection elsewhere in the excerpt must not disqualify this one.
    """
    contexts = []
    for excerpt in excerpts:
        start = excerpt.find(quote)
        while start >= 0:
            end = start + len(quote)
            breaks = [m.end() for m in _SENTENCE_BREAK.finditer(excerpt)]
            left = max((b for b in breaks if b <= start), default=0)
            right = min((m.start() for m in _SENTENCE_BREAK.finditer(excerpt, end)), default=len(excerpt))
            contexts.append(excerpt[left:right])
            start = excerpt.find(quote, start + 1)
    return contexts


def normalized_peers(peers, sources, role):
    by_url = {s['url']: s for s in source_set(sources)}
    output = []
    for peer in peers[:15] if isinstance(peers, list) else []:
        if not isinstance(peer, dict) or not company_key(peer.get('company_name')):
            continue
        name = _text(peer['company_name'])[:255]
        facts = peer.get('facts') if isinstance(peer.get('facts'), dict) else {}
        row = {key: _text(peer.get(key))[:255] for key in (
            'company_name', 'location', 'sector_or_industry', 'stage_or_type')}
        row['facts'], row['figures'] = {}, []
        for metric in METRICS.get(role, ()):
            fact = facts.get(metric)
            if not isinstance(fact, dict):
                continue
            value = finite_number(fact.get('value'))
            source_url = fact.get('source_url')
            source = by_url.get(source_url) if isinstance(source_url, str) else None
            quote = _text(fact.get('source_quote'))
            if (value is None or source is None or not quote
                    or not any(quote in excerpt for excerpt in source['excerpts'])
                    or not _quoted_number(value, quote, metric)
                    or f' {company_key(name)} ' not in f' {company_key(quote)} '):
                continue
            if metric != 'ebitda' and value < 0:
                continue
            if metric in COUNT_UNITS and not value.is_integer():
                continue
            unit = fact.get('unit')
            unit = unit if isinstance(unit, str) else None
            if metric in COUNT_UNITS:
                unit = unit if unit == COUNT_UNITS[metric] else None
            else:
                unit = unit if _currency_in_quote(unit, quote) else None
            basis = fact.get('basis') if fact.get('basis') in BASES[metric] else None
            # The basis must be stated in the quote, and no qualifier may
            # appear in any source sentence the quote was cut from.
            if basis and not (_basis_in_quote(metric, basis, quote) and all(
                    _basis_in_quote(metric, basis, context)
                    for context in quote_contexts(quote, source['excerpts']))):
                basis = None
            as_of = _source_date(fact.get('as_of'), quote)
            period_end = _source_date(fact.get('period_end'), quote)
            annual = metric in ('annual_revenue', 'ebitda')
            annual_quote = bool(re.search(r'\b(annual|year ended|fiscal year)\b', quote, re.I))
            period_kind = 'annual' if annual and fact.get('period_kind') == 'annual' and annual_quote else None
            reasons = []
            if not unit:
                reasons.append('Unit or currency not established')
            if not basis:
                reasons.append('Measurement basis not established')
            if annual and not (period_kind and period_end):
                reasons.append('Annual reporting period not established')
            if not annual and not as_of:
                reasons.append('Measurement date not established')
            longer = longer_source_name(name, quote)
            clean = dict(value=value, unit=unit, basis=basis, as_of=as_of,
                         period_kind=period_kind, period_end=period_end,
                         source_url=source['url'], source_title=source['title'], source_quote=quote,
                         eligible=not reasons, exclusion_reason='; '.join(reasons),
                         name_differs=bool(longer), source_company_name=longer or '')
            row['facts'][metric] = clean
            row['figures'].append(dict(clean, metric=metric, label=LABELS[metric], company_name=name))
        output.append(row)
    return output


def _group_key(fact):
    return (fact['unit'], fact['basis'], fact['period_kind'] or '', fact['period_end'] or '',
            fact['as_of'] if not fact['period_kind'] else '')


def external_metrics(role, subject, peers):
    """One company contributes at most once per metric, across all cohorts.

    Different observations for the same company/metric are excluded rather
    than selecting a convenient figure. Equal duplicate observations count
    once. Each unit/basis/date cohort has its own visible sample count.
    """
    output = {}
    subject = subject if isinstance(subject, dict) else {}
    declared = subject.get('metric_bases')
    declared = declared if isinstance(declared, dict) else {}
    for metric in METRICS.get(role, ()):
        observations = defaultdict(list)
        for peer in peers:
            fact = peer['facts'].get(metric)
            if fact and fact['eligible']:
                observations[company_key(peer['company_name'])].append((peer, fact))
        groups = defaultdict(list)
        for rows in observations.values():
            signatures = {(_group_key(f), f['value']) for _, f in rows}
            if len(signatures) != 1:
                continue
            peer, fact = rows[0]
            groups[_group_key(fact)].append(dict(fact, company_name=peer['company_name']))
        value = finite_number(subject.get(metric))
        rendered = []
        for key, figures in sorted(groups.items()):
            unit, basis, period_kind, period_end, as_of = key
            values = sorted(f['value'] for f in figures)
            mid = len(values) // 2
            enough = len(values) >= MIN_EXTERNAL_PEERS
            med = (values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2) if enough else None
            own_basis = declared.get(metric)
            same_basis = isinstance(own_basis, dict) and all(own_basis.get(k) == v for k, v in zip(
                ('unit', 'basis', 'period_kind', 'period_end', 'as_of'), key))
            pct = round(100 * sum(v <= value for v in values) / len(values)) if enough and same_basis and value is not None else None
            note = '' if pct is not None else 'Your figure has no matching recorded unit, basis and measurement date.'
            if metric in ('latest_round_size', 'transaction_value'):
                value, pct = None, None
                note = 'No completed round or transaction figure is recorded on your profile.'
            if not enough:
                note = f'At least {MIN_EXTERNAL_PEERS} distinct peers with comparable cited figures are required.'
            rendered.append(dict(value=value if same_basis else None, median=med, percentile=pct, peer_values_available=len(figures),
                                 unit=unit, basis=basis.replace('_', ' '), period_kind=period_kind,
                                 period_end=period_end, as_of=as_of, figures=figures, comparison_note=note))
        primary = max(rendered, key=lambda r: r['peer_values_available']) if rendered else {}
        output[metric] = dict(value=value, median=primary.get('median'), percentile=primary.get('percentile'),
                              peer_values_available=primary.get('peer_values_available', 0),
                              label=LABELS[metric], groups=rendered, evidence_version=EVIDENCE_VERSION)
    return output


def descriptive_summary(peers):
    figures = [f for p in peers for f in p['figures']]
    eligible = sum(f['eligible'] for f in figures)
    return (f'{len(peers)} selected external peers; {len(figures)} source-linked figures, '
            f'of which {eligible} have a recorded unit, basis and measurement period. '
            'Each comparison uses only figures with the same unit, basis and dates. '
            'Source-linked extraction is not independent verification.')
