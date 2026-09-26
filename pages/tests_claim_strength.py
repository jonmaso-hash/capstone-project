"""
A standing guard on CLAIM STRENGTH, the axis the advisory guard doesn't cover.

`zelda_api/tests_no_investment_advice.py` already stops Zelda telling anyone
what to do ("should invest", "good investment", "Recommendation:"). That is
the advisory axis, and it has been enforced repo-wide since 2026-09-18.

This is the other axis: vocabulary that implies a DETERMINATION or an
ASSURANCE with no concrete basis. The standard it enforces is the one the
homepage rewrite was built on:

    A claim is acceptable when its referent is an actual product state,
    mechanism, or documented output -- not because the wording sounds
    cautious.

"True fit" is an empirical claim about whether semantic similarity predicts a
real transaction, and there is no marketplace data for it. "Bank-grade" names
a standard nobody defined. "Fully secure" is an assurance no system can make.
None of these are advice, so the advisory guard lets every one of them past.

Three deliberate decisions about scope, each of which cost something to learn:

TEMPLATES ONLY, NOT PYTHON
    The advisory guard scans .py as well, and should: its tokens are enum
    values and prompt text that genuinely live in code. Claim-strength
    vocabulary does not. Every current .py match for "guarantee" is an
    engineering use in a comment -- "on duplicates to guarantee execution
    safety", "the static half of the guarantee", "a stronger guarantee than".
    Scanning source comments for product-claim vocabulary produces noise that
    would get the guard deleted. Product claims live in templates.

NEGATED FORMS ARE ALLOWED, AND ARE THE POINT
    Both real uses of "guarantee" in the templates are disclaimers:
    "We do not guarantee that any introduction... will result in a
    transaction", and "a diligence accelerator, not a background check or a
    guarantee." That is exactly the copy that SHOULD exist. A guard that
    banned the word outright would delete the disclaimers and leave the
    overclaims, which is precisely backwards.

"VERIFIED" IS NOT BANNED
    It is accurate wherever its referent is a state the product establishes:
    Verified Funded / Verified Sold name a bilateral state the connection
    state machine enforces, and a unilateral FUNDED_PENDING renders no badge.
    Truth Delta's own `verified` is one of five evidence states. What is
    banned is the compound that asserts a conclusion Zelda does not reach --
    "fully verified", "verified evidence", "Zelda verifies".

Not covered here, deliberately: "Instant Valuation Reports" on the homepage is
an unmeasured latency claim, but its wording is entangled with the open
packaging decisions (D3), so it is recorded rather than pinned. Adding it here
would decide a packaging question by way of a test.
"""
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


# Each pattern is a claim whose referent is an outcome nobody measured, or an
# assurance nobody can make. Matched case-insensitively against whitespace-
# normalised template text.
FORBIDDEN_PATTERNS = (
    # Assurance: absolutes about security, privacy or accuracy.
    (r'\b(?:bank|military|enterprise|institutional|government)[-\s]grade\b',
     'names a security standard that has no definition behind it'),
    (r'\b(?:100%|fully|completely|totally|entirely)\s+'
     r'(?:secure|private|confidential|accurate|verified|encrypted)\b',
     'claims an absolute no system can support'),
    (r'\b(?:unhackable|foolproof|impenetrable|bulletproof)\b',
     'claims an absolute no system can support'),
    (r'\bguarantee[sd]?\b',
     'promises an outcome the platform does not control'),

    # Unmeasured outcomes: claims about what matching or analysis achieves.
    (r'\btrue[-\s]fit\b',
     'asserts that semantic similarity predicts a real transaction'),
    (r'\bscored by fit\b',
     'asserts that semantic similarity predicts a real transaction'),
    (r'\bperfect\s+(?:match|fit)\b',
     'asserts an outcome the match score does not measure'),
    (r'\bdue[-\s]diligence[-\s]ready\b',
     'names a diligence standard nobody defined'),
    (r'\b(?:investment|audit)[-\s]ready\b',
     'names a standard nobody defined'),

    # Verification overclaims: a conclusion Zelda does not reach.
    (r'\bverified\s+(?:evidence|truth|facts?)\b',
     'says Zelda established that evidence is true'),
    (r'\bzelda\s+verifies\b',
     'says Zelda establishes truth rather than reporting evidence states'),
)

# A negator immediately before a match makes it a disclaimer, not a claim.
# "We do not guarantee", "not a background check or a guarantee".
NEGATORS = (
    r'\bno\b', r'\bnot\b', r'\bnever\b', r'\bcannot\b', r"\bcan't\b",
    r'\bwithout\b', r'\bdoes not\b', r'\bdo not\b', r"\bdoesn't\b",
    r"\bdon't\b", r'\bnor\b', r'\bisn\'t\b', r'\bis not\b',
)
_NEGATOR_WINDOW = 40  # characters before the match to search


def squeeze(text):
    """
    Lowercased, with every run of whitespace collapsed to one space.

    Template copy wraps across source lines, so a pattern written with single
    spaces will not match the raw file even when the phrase is plainly there.
    A scan without this is silently unfalsifiable -- the homepage guard shipped
    a phrase assertion that passed while the phrase sat on the page, because
    "like a deal team" happened to wrap.
    """
    return ' '.join(text.lower().split())


def _is_negated(haystack, start):
    window = haystack[max(0, start - _NEGATOR_WINDOW):start]
    return any(re.search(negator, window) for negator in NEGATORS)


def claim_strength_offences(text):
    """
    Every forbidden claim in `text`, as (matched phrase, why).

    Negated occurrences are not offences: a disclaimer saying the platform
    does NOT guarantee something is the opposite of an overclaim.
    """
    haystack = squeeze(text)
    found = []
    for pattern, reason in FORBIDDEN_PATTERNS:
        for match in re.finditer(pattern, haystack):
            if _is_negated(haystack, match.start()):
                continue
            found.append((match.group(0), reason))
    return found


def _template_files():
    root = Path(settings.BASE_DIR) / 'templates'
    return [p for p in root.rglob('*.html')
            if 'node_modules' not in p.parts and 'venv' not in p.parts]


class TheScannerActuallyWorksTests(SimpleTestCase):
    """
    Positive controls. A scan that cannot detect anything passes every clean
    tree forever and protects nothing; these prove the detector fires before
    the next class asserts that it doesn't.
    """

    def test_it_detects_an_assurance_claim(self):
        offences = claim_strength_offences('Your files are protected with bank-grade encryption.')
        self.assertEqual([phrase for phrase, _ in offences], ['bank-grade'])

    def test_it_detects_an_unmeasured_outcome_claim(self):
        offences = claim_strength_offences('We surface true-fit counterparties.')
        self.assertEqual([phrase for phrase, _ in offences], ['true-fit'])

    def test_it_detects_a_verification_overclaim(self):
        offences = claim_strength_offences('Zelda separates claims from verified evidence.')
        self.assertEqual([phrase for phrase, _ in offences], ['verified evidence'])

    def test_it_detects_a_phrase_that_wraps_across_lines(self):
        """
        The failure mode that made the homepage's first phrase scan vacuous.
        Written as the template would wrap it, with a newline mid-phrase.
        """
        wrapped = 'Your data is\n            fully    secure\n            at all times.'
        self.assertEqual([phrase for phrase, _ in claim_strength_offences(wrapped)],
                         ['fully secure'])

    def test_a_negated_claim_is_not_an_offence(self):
        """The disclaimers that must survive -- both are real template text."""
        for disclaimer in (
            'We do not guarantee that any introduction, match, connection or '
            'conversation will result in a transaction.',
            'a diligence accelerator, not a background check or a guarantee.',
        ):
            with self.subTest(disclaimer=disclaimer[:40]):
                self.assertEqual(claim_strength_offences(disclaimer), [])

    def test_a_negator_further_away_than_the_window_still_counts_as_a_claim(self):
        """
        The negation allowance is deliberately narrow. A "not" thirty words
        earlier does not make a later sentence a disclaimer, and treating it
        as one would be a hole big enough to drive any claim through.
        """
        text = ('We do not share your data with third parties. ' + 'Filler sentence. ' * 4
                + 'Our platform is fully secure.')
        self.assertEqual([phrase for phrase, _ in claim_strength_offences(text)],
                         ['fully secure'])

    def test_legitimate_verified_states_are_not_offences(self):
        """
        "Verified" is accurate where its referent is a state the product
        establishes. Banning the word would delete the strongest true claim
        on the site.
        """
        for legitimate in (
            'Verified Funded and Verified Sold outcomes become part of the track record.',
            '[VERIFIED] Deal confirmed by both parties. FUNDED',
            'evidence-grounded intelligence, semantic matching, and verified deal outcomes',
            'reports each disclosed claim as verified, unsupported, unavailable, or not comparable',
            '4. Build a Verified Track Record',
        ):
            with self.subTest(text=legitimate[:40]):
                self.assertEqual(claim_strength_offences(legitimate), [])


class NoUnsupportedClaimVocabularyInTemplatesTests(SimpleTestCase):
    """
    The guard itself. Every template, every release.
    """

    def test_the_scan_reaches_the_templates(self):
        """
        Second positive control, on the corpus rather than the detector: a
        scan that walked an empty directory would pass the test below while
        checking nothing at all.
        """
        files = _template_files()
        self.assertGreater(len(files), 50, 'the template scan found almost nothing to read')
        self.assertTrue(
            any(p.name == 'home.html' for p in files),
            'the scan did not reach the homepage, the surface this guard exists for',
        )

    def test_no_template_makes_an_unsupported_claim(self):
        offenders = []
        for path in _template_files():
            text = path.read_text(encoding='utf-8', errors='ignore')
            for phrase, reason in claim_strength_offences(text):
                offenders.append(
                    f'{path.relative_to(Path(settings.BASE_DIR))}: "{phrase}" — {reason}'
                )
        self.assertEqual(
            offenders, [],
            'Claim-strength vocabulary found in templates. Each of these asserts a '
            'determination or an assurance with nothing behind it. Say what the '
            'product establishes instead, or state the limit:\n  '
            + '\n  '.join(offenders),
        )
