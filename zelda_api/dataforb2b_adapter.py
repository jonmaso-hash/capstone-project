"""
DataForB2B -> Truth Delta observations (Task 8).

The adapter turns a CompanyRecord's facts into ObservedDatapoint rows that
carry the role and origin source_capabilities declares -- and nothing else.
It writes straight to the Task 6 boundary rather than joining
DataSourceManager.INTEGRATIONS, whose writing path predates roles: what a
DataForB2B value may do is decided once, in the registry, and the engine's
_build_comparison is the only place a row ever affects a claim. So:

    funding_raised   corroborates: agrees or dissents with a claim, never decides it
    employees        context: LinkedIn-associated profiles, never compared
    revenue/customers  never requested, never written

A deck claim is not establishing evidence. With DataForB2B as the only
source, a claim stays INSUFFICIENT ('corroboration_only') with the provider
value attached; it is verified only when an establishing source agrees.

Cost control: the provider is asked only when the document has a claim in a
category it may speak to, and only with a deterministic identifier (the
profile's company website, or a LinkedIn /company/ URL). Anything else is
not asked at all. Every outcome is returned for the report; none of them is a
statement about the company.
"""
import logging
from .financial_metrics import currency_code

from .dataforb2b import (
    SOURCE_TYPE, SUCCESS, UNCONFIGURED, UNRESOLVABLE, DataForB2BClient, normalize_domain, supports,
)
from .source_capabilities import CAN_ESTABLISH, OBSERVABLE_CATEGORIES, may_store

logger = logging.getLogger(__name__)

NOT_NEEDED = 'not_needed'
SOURCE_NAME = 'DataForB2B (LinkedIn-derived)'
# What the provider may speak to among the categories Truth Delta can store.
RELEVANT_CATEGORIES = tuple(c for c in OBSERVABLE_CATEGORIES if supports(c))
# Credibility for ordering among corroborating rows only. It can never make a
# row establishing: role, not credibility, decides that (_build_comparison).
CORROBORATION_CREDIBILITY = 0.5


def identifiers_for(document):
    """Deterministic identifiers from the document's business profile, or {}."""
    from .entity_verification import subject_for_document

    subject = subject_for_document(document)
    if subject is None:
        return {}
    found = {}
    domain = normalize_domain(getattr(subject, 'company_website', '') or '')
    if domain:
        found['domain'] = domain
    linkedin = getattr(subject, 'linkedin_url', '') or ''
    # Only a company page: on a founder profile this field is usually the
    # founder's own /in/ URL, which identifies a person, not the company.
    if '/company/' in linkedin.lower():
        found['linkedin'] = linkedin
    return found


def observe(document, claims, client=None):
    """
    Write DataForB2B observations for `document` and return the provider
    outcome for the report. Replaces this provider's previous rows only on
    success, so a failed refresh never deletes what an earlier run found.
    """
    from .truth_delta_models import ExternalDataSource, ObservedDatapoint

    wanted = sorted({claim.category for claim in claims} & set(RELEVANT_CATEGORIES))
    if not wanted:
        return NOT_NEEDED
    client = client or DataForB2BClient()
    if not client.configured:
        return UNCONFIGURED
    identifiers = identifiers_for(document)
    if not identifiers:
        return UNRESOLVABLE

    result = client.company_facts(categories=wanted, **identifiers)
    if result.outcome != SUCCESS:
        logger.info(f'[DataForB2B] document {document.id}: {result.outcome}')
        return result.outcome

    record = result.record
    source, _ = ExternalDataSource.objects.get_or_create(
        source_type=SOURCE_TYPE, defaults={'source_name': SOURCE_NAME, 'is_active': True})
    ObservedDatapoint.objects.filter(document=document, source__source_type=SOURCE_TYPE).delete()

    retrieved = record.retrieved_at.date().isoformat()
    for fact in record.facts:
        # Defence in depth: the client already reads roles from the registry.
        if fact.role == CAN_ESTABLISH or not may_store(SOURCE_TYPE, fact.category):
            logger.error(f'[DataForB2B] refused to write {fact.category} with role {fact.role}')
            continue
        ObservedDatapoint.objects.create(
            document=document, category=fact.category,
            observed_value=_display(fact), observed_value_numeric=fact.value, unit=fact.unit,
            currency=currency_code(fact.unit),
            time_period=f'as of {retrieved}', source=source, registrant=record.provider_id,
            source_url=record.linkedin_url[:200] if record.linkedin_url.startswith('https://') else '',
            source_date=record.retrieved_at.date(), source_credibility=CORROBORATION_CREDIBILITY,
            extraction_method='api', role=fact.role, evidence_origin=fact.origin,
            provenance={
                'provider': record.provider, 'provider_id': record.provider_id,
                'provider_field': fact.field, 'lookup_method': record.lookup_method,
                'lookup_identifier': record.lookup_identifier,
                'retrieved_at': record.retrieved_at.isoformat(), 'note': fact.note,
            },
        )
    return SUCCESS


def _display(fact):
    if fact.unit == 'USD':
        return f'${fact.value:,.0f}'
    if fact.unit == 'linkedin_associated_profiles':
        return f'{fact.value:,.0f} LinkedIn-associated profiles'
    return f'{fact.value:,.0f}'
