# zelda_api/truth_delta_tasks.py
"""
Celery async tasks for Truth Delta verification.
Runs in background to fetch external data and calculate credibility scores.
"""
import hashlib
import logging
from celery import shared_task
from django.utils import timezone
from .vector_models import DocumentSource
from .truth_delta_engine import TruthDeltaEngine
from .financial_metrics import (
    MONEY_CATEGORIES, claim_is_admissible, currency_value, usage_unit,
)
from .truth_delta_models import ClaimedDatapoint

logger = logging.getLogger(__name__)

# ClaimedDatapoint.text_excerpt holds the claim's own sentence, bounded. It
# used to hold the whole source chunk: document text copied outside the
# chunk boundary, where a serializer could expose it without anyone asking
# whether the reader may see the document's text. chunk_hash and
# page_number keep the provenance.
EXCERPT_CHARS = 300


def bounded_excerpt(text):
    text = ' '.join((text or '').split())
    return text if len(text) <= EXCERPT_CHARS else text[:EXCERPT_CHARS - 1] + '…'


def verification_finished(document_id):
    """
    Verification for this document has reached a terminal state -- verified,
    contradicted, nothing to check, or failed. Write the memo now, from a
    GroundedContext that carries that outcome. Called at every terminal path,
    including a re-run from the Run Verification button, so the memo never
    lags the evidence. Valuation documents have no Intelligence Memo.
    """
    try:
        document_type = (DocumentSource.objects.filter(id=document_id)
                         .values_list('document_type', flat=True).first())
        if document_type is None or document_type == 'business_valuation':
            return
        from .tasks import generate_intelligence_memo
        generate_intelligence_memo.delay(document_id)
    except Exception:
        logger.exception(f"[Truth Delta] Could not queue the memo for document {document_id}")


@shared_task
def extract_claims_from_insights(document_id: int):
    """
    Extract claimed datapoints from intelligence insights.
    Called after IntelligenceInsight objects are created.

    Maps insights to claims that can be verified. The category names here
    must match IntelligenceInsight.category exactly as produced by
    ZeldaIntelligencePipelineV2._analyze_document's analysis_categories
    dict (Problem/Market/Revenue/Team/Product/Traction/Funding/Risk) —
    Problem/Product/Risk are deliberately excluded since they're narrative,
    not numeric, and have nothing for Truth Delta to verify.

    This previously did a fuzzy substring scan against keys ('Customer',
    'Growth', 'Users') that don't match any category _analyze_document
    ever actually generates ('Traction', 'Market' are the real names) —
    so Traction and Market insights, however well-extracted, could never
    become a ClaimedDatapoint and reach Truth Delta at all. A direct
    lookup against the real category names is both a fix and a
    simplification.
    """
    try:
        from .vector_models import IntelligenceInsight

        logger.info(f"[Truth Delta] Extracting claims from insights for document {document_id}")

        document = DocumentSource.objects.get(id=document_id)
        insights = IntelligenceInsight.objects.filter(document=document)

        claims_created = 0

        # Map insight categories to claim categories
        category_mapping = {
            'Revenue': 'revenue',
            'Traction': 'customers',
            'Team': 'employees',
            'Funding': 'funding_raised',
            'Market': 'market_size',
        }

        for insight in insights:
            matched_category = category_mapping.get(insight.category)

            if not matched_category:
                continue

            # A category mapping is not evidence. The analyzer's category says
            # which BUCKET a sentence was filed under; it does not establish
            # that the sentence supports a claim of that kind. Without this
            # check the JoyToys deck produced: a $250K raise as 250,000
            # customers, 75% bank-line utilization as $75 raised, an amount
            # SOUGHT as capital raised, and annualized burn as revenue -- four
            # of six claims materially wrong. Truth Delta reported them
            # honestly as unverified, but for an SEC filer it would have
            # compared burn against real revenue and announced a contradiction
            # about a company that did nothing wrong.
            text = insight.insight_text or ''
            # A Traction figure that counts bots or messages is a usage figure,
            # not a customer count. Its own noun decides, and is kept as the
            # unit so two usage claims never read as the same quantity.
            unit = insight.metric_unit or ''
            if matched_category == 'customers':
                counted = usage_unit(text)
                if counted:
                    matched_category, unit = 'usage', counted
            if not claim_is_admissible(matched_category, text):
                logger.debug(
                    "[Truth Delta] %s insight is not admissible evidence for %s: %r",
                    insight.category, matched_category, text[:80])
                continue

            # Money categories read MONEY. The general extractor matches
            # percentages first, which is how "Bank line: 75% utilized" became
            # $75 raised while the $20K actually raised sat unread in the same
            # sentence.
            if matched_category in MONEY_CATEGORIES:
                numeric_value = currency_value(text)
            else:
                numeric_value = _extract_numeric_value(text)

            if numeric_value is None:
                logger.debug(f"Could not extract numeric value from insight: {insight.insight_text}")
                continue
            
            # Create claimed datapoint, with full provenance back to the source chunk
            source_chunk_obj = insight.source_chunks.first()
            claim = ClaimedDatapoint.objects.create(
                document=document,
                category=matched_category,
                claimed_value=insight.insight_text[:255],  # Truncate if needed
                claimed_value_numeric=numeric_value,
                unit=unit,
                source_chunk=f"Insight: {insight.category}",
                confidence_in_extraction=insight.confidence_score,
                page_number=source_chunk_obj.page_number if source_chunk_obj else None,
                text_excerpt=bounded_excerpt(insight.insight_text),
                chunk_hash=hashlib.sha256(source_chunk_obj.raw_text.encode()).hexdigest() if source_chunk_obj else '',
            )
            
            claims_created += 1
            logger.debug(f"Created claim: {claim}")
        
        logger.info(f"[Truth Delta] Created {claims_created} claims from insights")
        
        # Queue verification
        verify_document_truth_delta.delay(document_id)
        
        return {'status': 'success', 'claims_created': claims_created}
    
    except Exception as exc:
        # This path never queued verification, so the run simply never
        # happened and the page said "hasn't been run yet" -- true, and
        # useless. Record it for the same reason the verify task does.
        logger.exception(f"Error extracting claims for document {document_id}")
        _record_verification_failure(document_id, exc)
        verification_finished(document_id)
        return {'status': 'error', 'error': str(exc)}


# Helper functions

def _is_bare_year(match) -> bool:
    """A four-digit calendar year with no currency mark, multiplier or separator."""
    currency, digits, suffix = match.group(1), match.group(2), match.group(3)
    if currency or suffix or not digits.isdigit():
        return False
    return len(digits) == 4 and 1900 <= int(digits) <= 2099


def _extract_numeric_value(text: str) -> float:
    """
    Extract first numeric value from text.
    Handles formats like: "$1M", "$416 billion", "500 customers", "200% growth", etc.

    The multiplier is read only from a token immediately adjacent to the
    matched digits — never from anywhere else in the sentence. Scanning
    the whole string (an earlier version of this function) meant a
    sentence merely containing the letter "M" (e.g. "...Marketing spend
    of $500...") would spuriously multiply an unrelated number by
    1,000,000.

    Recognizes both the abbreviated form (K/M/B, e.g. "$1M") and the
    spelled-out word (thousand/million/billion, e.g. "$416 billion") —
    real prose (SEC filings, investor updates) overwhelmingly uses the
    spelled-out form, which a K/M/B-only check silently drops: "$416
    billion" would parse as bare "416" with no multiplier, since the
    letter right after "billion" always defeats the old single-letter
    adjacency check. That's not a missing claim (which recall would
    catch) — it's a claim that looks successful but is off by a factor
    of a billion, which is worse.
    """
    import re

    if not text:
        return None

    # Percentages first, so "200%" never also picks up a stray multiplier
    # from elsewhere in the sentence.
    percent_match = re.search(r'([\d,]*\.?\d+)\s*%', text)
    if percent_match:
        try:
            return float(percent_match.group(1).replace(',', ''))
        except ValueError:
            pass

    # Currency/count, with an optional multiplier directly after the
    # digits — either the single-letter form or the spelled-out word.
    # The trailing negative lookahead rejects ambiguous adjacent-letter
    # cases (e.g. "1Mbps", "$50 billionaire") rather than guessing.
    #
    # The first alternative is a SPACED thousands separator ("140 000+ bots",
    # also with a no-break or narrow no-break space): it read as 140 before.
    # Its groups must be exactly three digits, and it may not start inside a
    # longer number, so "In 2016 500 customers" stays 500 and "12 50" stays 12.
    # A trailing "+" needs nothing: it is not a letter, so it ends the figure.
    for match in re.finditer(
        r'(\$)?((?<![\d.,])\d{1,3}(?:[   ]\d{3})+(?![\d.,])|[\d,]*\.?\d+)'
        r'\s*(thousand\b|million\b|billion\b|[kmb])?(?![a-zA-Z])',
        text, re.IGNORECASE,
    ):
        if _is_bare_year(match):
            # "returned capital to shareholders continuously since 2012"
            # became funding_raised = $2012, which Truth Delta then scored.
            # A calendar year carries no currency mark, no multiplier and no
            # thousands separator; $2,015 and "2,015 customers" both do.
            continue
        break
    else:
        return None

    try:
        numeric_value = float(re.sub(r'[,\s]', '', match.group(2)))
    except ValueError:
        return None

    suffix = (match.group(3) or '').lower()
    if suffix in ('k', 'thousand'):
        numeric_value *= 1_000
    elif suffix in ('m', 'million'):
        numeric_value *= 1_000_000
    elif suffix in ('b', 'billion'):
        numeric_value *= 1_000_000_000

    return numeric_value


def _record_verification_failure(document_id, exc):
    """
    Persist that verification could not complete, so the absence of a report
    stops being the only evidence that something went wrong.

    The technical cause is kept for staff and the logs; the surfaces show an
    end user that it failed and what they can do. Deliberately best-effort:
    if recording the failure ALSO fails there is nothing useful left to do,
    and raising here would replace the real exception with a worse one.
    """
    try:
        # A failure supersedes an earlier "nothing to check": the newest
        # outcome is the one a reader is told.
        DocumentSource.objects.filter(id=document_id).update(
            verification_failed_at=timezone.now(),
            verification_error=str(exc)[:2000],
            verification_no_claims_at=None,
        )
    except Exception:
        logger.exception(f"[Truth Delta] Could not record the failure for {document_id}")

    try:
        from ops.models import log_failed_task
        log_failed_task('zelda_api.tasks.verify_document_truth_delta', [document_id], str(exc))
    except Exception:
        logger.exception(f"[Truth Delta] Could not log the failed task for {document_id}")


@shared_task
def verify_document_truth_delta(document_id):
    engine = TruthDeltaEngine()
    try:
        result = engine.verify_document(document_id)
    except Exception as exc:
        # Previously unhandled. A raise left Celery reporting a failed task and
        # NOTHING a reader could see -- the page said "hasn't been run yet",
        # which is indistinguishable from "still running".
        logger.exception(f"[Truth Delta] Verification failed for document {document_id}")
        _record_verification_failure(document_id, exc)
        # A failed verification is still a terminal state: the memo is written
        # from what is known, with the failure on record.
        verification_finished(document_id)
        # Re-raised on purpose: recording it for the user must not swallow it
        # for us, or the task reports success and the failure leaves no trace
        # in Celery or in ops.
        raise

    # A run that completed clears any earlier failure. Without this the state
    # is permanent once tripped: a document that failed yesterday and verified
    # fine today would still be shown as broken.
    #
    # No claims to verify is an ordinary outcome, not a breakage -- but it is
    # an outcome, and it is recorded as one. Writing nothing left it looking
    # exactly like a run that never started. Written before the memo is
    # queued, because the memo reads it.
    DocumentSource.objects.filter(id=document_id).update(
        verification_failed_at=None, verification_error='',
        verification_no_claims_at=timezone.now() if result is None else None)
    # Verified, contradicted or nothing to check: all terminal, all get a memo.
    verification_finished(document_id)

    # Return JSON-serializable dict, not a Django model object
    if result is None:
        return {'status': 'no_claims', 'document_id': document_id}

    return {
        'status': 'success',
        'document_id': document_id,
        'report_id': result.id if hasattr(result, 'id') else None,
    }