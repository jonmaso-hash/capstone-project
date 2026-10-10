"""
What a Truth Delta report SAYS, derived from what it ESTABLISHED (R-003).

The rule: the model may explain Zelda's verdict; it may not create, alter or
contradict it.

Before this module the model wrote the report's words. It was handed the raw
comparison rows -- a 13.8% gap, `claim_period: null` -- WITHOUT the state the
grounding rules assign to them, and a prompt telling it that a claim
"significantly higher than observed data ... is a real red flag". Its prose was
stored and shown beside the canonical state, so Nike's report said
"materially overstated ... a significant red flag" next to 0 verified / 0
contradicted / revenue `period_unknown` (rerun ledger, R-003).

Now, for every report:

- The SUMMARY is composed here from `category_states()` and
  `grounding_reasons()`. The model's summary is not stored.
- The PER-CLAIM ROWS are the stored comparison rows, one per claim, so the model
  can neither add nor drop a claim. Their `observed` text is written from the
  stored evidence (value, source, period), never from the model.
- The model's one-sentence EXPLANATION of a row is kept only if it asserts no
  verdict the canonical state does not hold (`explanation_consistent`).
  Otherwise the row carries Zelda's own reason sentence, and the rejection is
  logged.

The state itself is never computed here. Everything reads the same
`TruthDeltaReport.category_states()` the icons, counts and memo read, so there
is still one implementation of the grounding rules.
"""
import logging
import re
from .financial_metrics import MONETARY_CATEGORIES, currency_code

logger = logging.getLogger(__name__)

MONEY_CATEGORIES = MONETARY_CATEGORIES
EXPLANATION_MAX_CHARS = 300

# Zelda's own sentence for each state / reason. Used when the model gave no
# explanation, or gave one the guard refused.
REASON_SENTENCES = {
    'currency_unknown': 'The monetary currency is not explicitly known on both sides, so this claim was not compared.',
    'currency_mismatch': 'The claim and external figure use different currencies, so this claim was not compared. No currency conversion was applied.',
    'period_unknown': ('An external figure was found, but its period could not be confirmed as '
                       'comparable, so this claim is not verified.'),
    'no_external_evidence': 'No external data was found for this claim.',
    'source_unavailable': 'The public source could not be reached, so this claim was not checked.',
    'corroboration_only': ('Only lower-authority (LinkedIn-derived) data was found. It is shown for '
                           'reference and does not verify or contradict this claim.'),
    'extraction_insufficient': ('The claim could not be tied to its source text precisely enough to '
                                'compare it.'),
    'no_comparable_claim': 'This kind of claim is not compared against external figures.',
    'ambiguous_pairing': 'More than one external figure could match this claim, so none was compared.',
}

# Verdict language. A sentence may use a family only when the canonical state
# holds that verdict. Negated uses ("could not be verified", "this does not
# establish that it is overstated") are removed before the check, because an
# honest no_data explanation has to be able to say what it could NOT conclude.
_CONTRADICTION = re.compile(
    r"\b(contradict\w*|overstat\w*|understat\w*|inflat\w*|exaggerat\w*|red[- ]flags?|mislead\w*|"
    r"misrepresent\w*|false|falsif\w*|inaccura\w*|incorrect|discrepan\w*|inconsisten\w*|"
    r"does not match|doesn't match|disagree\w*|unsupported|not supported)\b", re.I)
_VERIFICATION = re.compile(
    r"\b(verif\w*|confirm\w*|corroborat\w*|validat\w*|substantiat\w*|accurate|"
    r"consistent with|matches|in line with|supported by|backed by|checks out)\b", re.I)
_NEGATED = re.compile(
    r"\b(?:not|never|no|cannot|can't|could not|couldn't|unable to|without|nor)\b"
    r"(?:\s+\w+){0,3}?\s+"
    r"(?:verif\w*|confirm\w*|corroborat\w*|validat\w*|substantiat\w*|establish\w*|"
    r"contradict\w*|overstat\w*|understat\w*|inflat\w*|discrepan\w*|inconsisten\w*|red[- ]flags?)",
    re.I)


def explanation_consistent(text, state, reason=None):
    """
    True if `text` asserts no verdict other than `state`.

    - contradiction language is allowed only for `contradicted`;
    - verification language is allowed only for `verified` -- except that a
      corroboration_only row may say the lower-authority data is "consistent
      with" or "corroborates" the claim, which is what corroboration means,
      and never that anything "verified" or "confirmed" it.
    """
    if not isinstance(text, str) or not text.strip() or len(text) > EXPLANATION_MAX_CHARS:
        return False
    asserted = _NEGATED.sub(' ', text)
    if state != 'contradicted' and _CONTRADICTION.search(asserted):
        return False
    if state != 'verified':
        for match in _VERIFICATION.finditer(asserted):
            word = match.group(0).lower()
            if reason == 'corroboration_only' and (word.startswith('corroborat') or word == 'consistent with'):
                continue
            return False
    return True


def format_figure(value, category, currency=None):
    """A stored number as a reader would write it: $46.4 billion, 81,500."""
    if value is None:
        return None
    if category in MONEY_CATEGORIES:
        # None is the historical formatter contract; new rows pass even a
        # blank code explicitly, so they cannot acquire a dollar sign.
        code = currency_code(currency)
        prefix = '$' if currency is None else {'USD': '$', 'EUR': '€', 'GBP': '£', 'CAD': 'C$', 'AUD': 'A$'}.get(code, '')
        suffix = '' if currency is None else f' {code}' if code else ' (currency unknown)'
        magnitude = abs(value)
        for size, word in ((1e12, 'trillion'), (1e9, 'billion'), (1e6, 'million')):
            if magnitude >= size:
                return f"{prefix}{value / size:,.1f} {word}{suffix}"
        return f"{prefix}{value:,.0f}{suffix}"
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:,}"


def observed_text(row, reason=None):
    """The evidence a row was compared against, written from the stored row alone."""
    figure = format_figure(row.get('observed_value_numeric'), row.get('category'), row.get('observed_currency'))
    if figure is not None:
        detail = ', '.join(part for part in (row.get('observed_source'), row.get('observed_time_period')) if part)
        return f"{figure} ({detail})" if detail else figure
    if reason == 'corroboration_only' or row.get('corroboration'):
        return 'Lower-authority data only'
    if reason == 'source_unavailable':
        return 'Source could not be reached'
    return 'No external data found'


def state_sentence(row, state, reason):
    """Zelda's own explanation of a row, from the state alone."""
    figure = format_figure(row.get('observed_value_numeric'), row.get('category'), row.get('observed_currency'))
    where = ', '.join(part for part in (row.get('observed_source'), row.get('observed_time_period')) if part)
    if state == 'verified':
        return f"Matches the {where} figure of {figure}." if figure else 'Matches the external figure.'
    if state == 'contradicted':
        gap = row.get('discrepancy_pct')
        gap_text = f" by {abs(gap)}%" if gap is not None else ''
        return (f"Differs from the {where} figure of {figure}{gap_text}, for a comparable period."
                if figure else 'Differs from the external figure for a comparable period.')
    return REASON_SENTENCES.get(reason, 'Nothing could be established about this claim.')


def claim_rows(comparison, states, reasons, explanations=None):
    """
    One row per stored comparison row: the claim, the stored evidence, Zelda's
    state, and an explanation the guard accepted (else Zelda's own sentence).

    `explanations` is {category: text} from the model, or None. Rows are keyed
    by category on purpose: the state is per category, so is the explanation.
    """
    explanations = explanations or {}
    rows = []
    for row in comparison:
        category = row.get('category')
        state = row.get('zelda_state', states.get(category, 'no_data'))
        reason = row.get('zelda_reason', reasons.get(category)) if state == 'no_data' else None
        offered = explanations.get(category)
        if offered and explanation_consistent(offered, state, reason):
            assessment, source = offered.strip(), 'model'
        else:
            if offered:
                logger.info('Truth Delta explanation for %s refused: it does not agree with state %s/%s',
                            category, state, reason)
            assessment, source = state_sentence(row, state, reason), 'zelda'
        rows.append({
            'category': category,
            'claim_id': row.get('claim_id'),
            'claimed': row.get('claimed_value'),
            'observed': observed_text(row, reason),
            'assessment': assessment,
            'explanation_source': source,
        })
    return rows


def _label(category):
    return (category or 'claim').replace('_', ' ')


def summary(states, reasons, comparison, stats, headlines=()):
    """
    The report's summary, from the canonical state alone: the coverage line,
    then one sentence per category saying what was established and why.
    """
    from .ic_memo import coverage_sentence

    first = {}
    for row in comparison:
        category = row.get('category')
        if category not in first or row.get('zelda_state') == states.get(category):
            first[category] = row
    sentences = [coverage_sentence(stats)]
    for category, state in states.items():
        row = first.get(category, {})
        reason = reasons.get(category)
        figure = format_figure(row.get('observed_value_numeric'), category, row.get('observed_currency'))
        where = ', '.join(part for part in (row.get('observed_source'), row.get('observed_time_period')) if part)
        label = _label(category).capitalize()
        if state == 'verified':
            sentences.append(f"{label} matches {where} ({figure}).")
        elif state == 'contradicted':
            gap = row.get('discrepancy_pct')
            sentences.append(f"{label} differs from {where} ({figure})"
                             + (f" by {abs(gap)}%" if gap is not None else '') + ', for a comparable period.')
        elif reason == 'period_unknown' and figure:
            sentences.append(f"{label}: {where} reports {figure}, but the deck's figure has no stated period, "
                             f"so the two could not be compared and the claim is not verified.")
        else:
            sentences.append(f"{label}: " + REASON_SENTENCES.get(reason, 'nothing could be established.')[0].lower()
                             + REASON_SENTENCES.get(reason, 'nothing could be established.')[1:])
    if headlines:
        sentences.append('Recent news headlines were reviewed as context only; they verify nothing.')
    return ' '.join(sentences)
