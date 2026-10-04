"""
What Zelda is allowed to know when it writes (Phase 1 Task 5).

GroundedContext is the one boundary between Zelda's evidence system and a
generative product. The Intelligence Memo is its first consumer: the memo
generator receives a GroundedContext and nothing else -- no raw text, no
chunks, no free-floating insights, no profile row.

    document -> chunks -> insights -> claims -> verification -> GroundedContext -> memo

Every item carries where it came from (document, page, chunk) and what is
known about it:

    SELF_REPORTED  the company says so; nothing checked it (narrative, or a
                   category no source covers)
    VERIFIED       Truth Delta reconciled it against stored external evidence
    CONTRADICTED   Truth Delta found stored external evidence that diverges
    INSUFFICIENT   checked, but nothing could be concluded -- the reason says
                   why (period_unknown, source_unavailable, ...). The external
                   value, when one was fetched, travels with it.

The state is read from TruthDeltaReport.category_states() and
grounding_chain(), never re-derived here: there is one verdict, and the memo
receives it.

Profile values enter only when anyone could see them. The memo is read by
people the founder never connected with, so a CONNECTED or PRIVATE field
must not reach a prompt whose output they read. The rule is the existing
authority asked about an anonymous viewer.
"""
from dataclasses import dataclass, field
from typing import Optional, Tuple

from django.contrib.auth.models import AnonymousUser

from .authorization import authorize
from .principal import require_principal
from .retrieval import RetrievalRefused

SELF_REPORTED = 'SELF_REPORTED'
VERIFIED = 'VERIFIED'
CONTRADICTED = 'CONTRADICTED'
INSUFFICIENT = 'INSUFFICIENT'
STATES = (SELF_REPORTED, VERIFIED, CONTRADICTED, INSUFFICIENT)

_CANONICAL_TO_STATE = {'verified': VERIFIED, 'contradicted': CONTRADICTED, 'no_data': INSUFFICIENT}

MAX_STATEMENTS = 25
EXCERPT_CHARS = 300

# Profile fields a memo may reason over, when the founder has made them PUBLIC.
PROFILE_FIELDS = {
    'current_revenue': 'Current revenue (profile)',
    'raising_amount': 'Raising (profile)',
    'prior_amount_raised': 'Previously raised (profile)',
    'monthly_burn_rate': 'Monthly burn rate (profile)',
    'team_size': 'Team size (profile)',
    'stage': 'Stage (profile)',
    'sector': 'Sector (profile)',
    'geography': 'Geography (profile)',
}


@dataclass(frozen=True)
class SourceRef:
    """Where an item came from. Positional only -- never the source text."""
    document_id: Optional[int]
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None
    chunk_hash: str = ''
    profile_field: str = ''

    def __post_init__(self):
        if self.document_id is None and not self.profile_field:
            raise ValueError('A source needs a document or a profile field.')


ESTABLISHES = 'establishes'
CORROBORATES = 'corroborates'
CONTEXT = 'context'


@dataclass(frozen=True)
class External:
    """
    A stored external observation, exactly as Truth Delta recorded it, with
    what it is allowed to do. Only an 'establishes' value stands behind the
    item's status; 'corroborates' values agree or dissent without deciding
    anything; 'context' values are labelled background.
    """
    value: object
    source: str
    role: str = ESTABLISHES
    origin: str = ''
    period: str = ''
    registrant: str = ''
    discrepancy_pct: Optional[float] = None
    agrees: Optional[bool] = None
    independent: Optional[bool] = None


@dataclass(frozen=True)
class GroundedItem:
    """One thing the memo may state, with its provenance and its status."""
    ref: str                       # stable id the memo cites: C1, S1, P1
    kind: str                      # 'claim' | 'statement' | 'profile'
    category: str
    statement: str                 # bounded excerpt, never a whole chunk
    status: str
    sources: Tuple[SourceRef, ...]
    confidence: Optional[float] = None
    value: Optional[float] = None
    reason: str = ''               # why INSUFFICIENT, when it is
    external: Tuple[External, ...] = ()
    insight_id: Optional[int] = None
    claim_id: Optional[int] = None

    def __post_init__(self):
        if self.status not in STATES:
            raise ValueError(f'Unknown evidence status {self.status!r}.')
        if not self.sources:
            raise ValueError(f'{self.ref}: an item without provenance may not reach generation.')


@dataclass(frozen=True)
class GroundedContext:
    document_id: int
    company: str
    built_for: str                 # the principal's label, for the record
    items: Tuple[GroundedItem, ...]
    gaps: Tuple[str, ...]
    verification: str              # 'complete' | 'failed' | 'not_run'
    analysis_confidence: float
    insight_ids: Tuple[int, ...] = field(default=())

    @property
    def citations_count(self):
        return sum(len(item.sources) for item in self.items if item.kind == 'statement')

    def by_status(self, status):
        return [item for item in self.items if item.status == status]

    # -- construction -----------------------------------------------------------

    @classmethod
    def build(cls, principal, document):
        """
        The context for generating from `document`, for `principal`. Refuses
        without a principal, and refuses a principal who may not read the
        document's text -- generation is not a route around retrieval.
        """
        auth = authorize(require_principal(principal))
        if not auth.text_permitted(document):
            raise RetrievalRefused('This principal may not generate from this document.')

        from .confidence_breakdown import compute_overall_confidence
        from .truth_delta_models import ClaimedDatapoint, TruthDeltaReport
        from .vector_models import IntelligenceInsight

        insights = list(IntelligenceInsight.objects.filter(document=document).order_by('-confidence_score', 'id'))
        report = TruthDeltaReport.objects.filter(document=document).order_by('-created_at', '-id').first()
        claims = list(ClaimedDatapoint.objects.filter(document=document).order_by('id'))

        items = []
        items.extend(_claim_items(document, claims, report))
        items.extend(_statement_items(document, insights))
        items.extend(_profile_items(document))

        if report is not None:
            verification = 'complete'
        elif document.verification_failed_at:
            verification = 'failed'
        else:
            verification = 'not_run'

        return cls(
            document_id=document.id,
            company=document.source_entity or '',
            built_for=principal.label or principal.origin,
            items=tuple(items),
            gaps=tuple(_gaps(document, insights)),
            verification=verification,
            analysis_confidence=compute_overall_confidence(insights),
            insight_ids=tuple(i.id for i in insights[:MAX_STATEMENTS]),
        )

    # -- what the model receives ------------------------------------------------

    def to_prompt_payload(self):
        """A JSON-safe rendering: every item with its ref, status and provenance."""
        def source(ref):
            if ref.profile_field:
                return {'profile_field': ref.profile_field}
            return {k: v for k, v in (('document_id', ref.document_id), ('page', ref.page_number),
                                      ('chunk', ref.chunk_index)) if v is not None}

        return {
            'company': self.company,
            'verification': self.verification,
            'items': [
                {
                    'ref': item.ref,
                    'kind': item.kind,
                    'category': item.category,
                    'statement': item.statement,
                    'status': item.status,
                    **({'reason': item.reason} if item.reason else {}),
                    **({'confidence': round(item.confidence)} if item.confidence is not None else {}),
                    **({'external': [
                        {k: v for k, v in (('role', e.role), ('value', e.value), ('source', e.source),
                                           ('origin', e.origin), ('period', e.period),
                                           ('discrepancy_pct', e.discrepancy_pct), ('agrees', e.agrees),
                                           ('independent', e.independent)) if v not in (None, '')}
                        for e in item.external]} if item.external else {}),
                    'sources': [source(s) for s in item.sources],
                }
                for item in self.items
            ],
            'gaps': list(self.gaps),
        }


def _excerpt(text):
    text = ' '.join((text or '').split())
    return text if len(text) <= EXCERPT_CHARS else text[:EXCERPT_CHARS - 1] + '…'


def _claim_items(document, claims, report):
    states = report.category_states() if report is not None else {}
    reasons = report.grounding_reasons() if report is not None else {}
    chain = report.grounding_chain() if report is not None else {}
    items = []
    for n, claim in enumerate(claims, 1):
        canonical = states.get(claim.category)
        if report is None:
            status, reason = INSUFFICIENT, ('verification_failed' if document.verification_failed_at
                                            else 'verification_not_run')
        elif canonical is None:
            status, reason = SELF_REPORTED, 'not_checked'
        else:
            status = _CANONICAL_TO_STATE[canonical]
            reason = reasons.get(claim.category, '') if status == INSUFFICIENT else ''
        external = []
        for row in chain.get(claim.category, []):
            if row.get('observed_value') is not None:
                external.append(External(
                    value=row.get('observed_value_numeric', row.get('observed_value')),
                    source=row.get('observed_source') or '', role=ESTABLISHES,
                    origin=row.get('observed_origin') or '',
                    period=row.get('observed_time_period') or '',
                    registrant=row.get('observed_registrant') or '',
                    discrepancy_pct=row.get('discrepancy_pct'),
                ))
            for entry in row.get('corroboration') or []:
                external.append(External(
                    value=entry.get('value_numeric', entry.get('value')), source=entry.get('source') or '',
                    role=CORROBORATES, origin=entry.get('origin') or '', period=entry.get('period') or '',
                    discrepancy_pct=entry.get('discrepancy_pct'), agrees=entry.get('agrees'),
                    independent=entry.get('independent'),
                ))
            for entry in row.get('context') or []:
                external.append(External(
                    value=entry.get('value'), source=entry.get('source') or '', role=CONTEXT,
                    origin=entry.get('origin') or '', period=entry.get('period') or '',
                ))
        external = tuple(external)
        items.append(GroundedItem(
            ref=f'C{n}', kind='claim', category=claim.category,
            statement=_excerpt(claim.claimed_value), status=status, reason=reason,
            sources=(SourceRef(document_id=document.id, page_number=claim.page_number,
                               chunk_hash=claim.chunk_hash or ''),),
            confidence=claim.confidence_in_extraction, value=claim.claimed_value_numeric,
            external=external, claim_id=claim.id,
        ))
    return items


def _statement_items(document, insights):
    items = []
    for n, insight in enumerate(insights[:MAX_STATEMENTS], 1):
        # Positional metadata only: the chunk boundary forbids reading text here.
        locations = list(insight.source_chunks.values_list('page_number', 'chunk_index'))
        sources = tuple(SourceRef(document_id=document.id, page_number=page, chunk_index=index)
                        for page, index in locations) or (SourceRef(document_id=document.id),)
        items.append(GroundedItem(
            ref=f'S{n}', kind='statement', category=insight.category,
            statement=_excerpt(insight.insight_text), status=SELF_REPORTED,
            sources=sources, confidence=insight.confidence_score, insight_id=insight.id,
        ))
    return items


def _profile_items(document):
    from matchmaking.models import Application, _normalize_company_string, can_view_profile_field

    app = Application.objects.filter(user=document.uploaded_by).first()
    if app is None:
        return []
    doc_company = _normalize_company_string(document.source_entity)
    app_company = _normalize_company_string(app.company_name)
    if not (doc_company and app_company and (doc_company in app_company or app_company in doc_company)):
        return []
    audience = AnonymousUser()
    items = []
    for field_name, label in PROFILE_FIELDS.items():
        value = getattr(app, field_name, None)
        if value in (None, '') or not can_view_profile_field(audience, app, field_name):
            continue
        items.append(GroundedItem(
            ref=f'P{len(items) + 1}', kind='profile', category=label, statement=_excerpt(f'{label}: {value}'),
            status=SELF_REPORTED, sources=(SourceRef(document_id=None, profile_field=field_name),),
        ))
    return items


def _gaps(document, insights):
    """What the extracted statements do not cover -- absent from extraction, not proven absent."""
    covered = {i.category for i in insights}
    expected = ('Problem', 'Market', 'Revenue', 'Team', 'Product', 'Traction', 'Funding', 'Risk')
    return [f'No {category.lower()} statement was extracted from the document.'
            for category in expected if category not in covered]
