"""
The public promise matches what Zelda does (copy PR after R-003/R-003b).

Retired because each was untrue or overstated once the evidence rules were
hardened:

- "each disclosed claim": Truth Delta checks the claims Zelda EXTRACTS, and on
  the Nike deck that was 2 of about 25.
- "real external filings": most private companies have none; the honest form
  is "public sources where they report the figure".
- "diligence at scale" / "AI-backed diligence" / "diligence package": Zelda is
  first-pass investment intelligence, not diligence.
- "no external data was found to verify or contradict these claims": false
  since R-003b whenever data existed but could not be compared -- Nike had an
  SEC figure. "No claim could be verified or contradicted" is true in every
  unscored case.
- "Credibility Score", "Truth Delta Score", "credibility scores": one score,
  one name, Evidence Credibility, because it rates the evidence for the claims
  Zelda evaluated, not the company.
- "request evidence from investors": backwards. Investors request; the
  founder answers.

Pinned the other way: the private-company sentence on the homepage, kept for
launch on purpose, so a missing public source never reads as a verdict on the
company.
"""
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from pages.tests_claim_strength import _template_files

RETIRED = {
    'each disclosed claim': re.compile(r'each disclosed claim', re.I),
    'real external filings': re.compile(r'real external filings', re.I),
    'diligence at scale': re.compile(r'diligence at scale', re.I),
    'AI-backed diligence': re.compile(r'AI-backed diligence', re.I),
    'diligence package': re.compile(r'diligence package', re.I),
    'no external data ... these claims': re.compile(r'no external data was found to verify or contradict these claims', re.I),
    'Credibility Score (alias)': re.compile(r'(?<!Evidence )Credibility Score'),
    'credibility score(s) (alias)': re.compile(r'\bcredibility scores?\b'),
    'Truth Delta Score (alias)': re.compile(r'Truth Delta Score'),
    'request evidence from investors': re.compile(r'request evidence from investors', re.I),
}

PRIVATE_COMPANY_SENTENCE = ('For most private companies, public sources report little, so many claims will read '
                            '&lsquo;not established&rsquo;; that is a statement about the evidence, not about the company.')


def retired_phrases(text):
    return [name for name, pattern in RETIRED.items() if pattern.search(text)]


def _surfaces():
    """Every template, plus the IC memo's markdown export, which is written in Python."""
    files = list(_template_files())
    files.append(Path(settings.BASE_DIR) / 'zelda_api' / 'ic_memo.py')
    return files


class TheScanWorksTests(SimpleTestCase):
    """Positive controls: the patterns fire, and the canonical name is not mistaken for an alias."""

    def test_each_retired_phrase_is_detected(self):
        samples = {
            'each disclosed claim': 'Truth Delta reports each disclosed claim as verified.',
            'real external filings': 'verification against real external filings',
            'diligence at scale': 'run AI diligence at scale',
            'AI-backed diligence': 'raise with AI-backed diligence',
            'diligence package': 'one shareable diligence package',
            'no external data ... these claims': 'no external data was found to verify or contradict these claims',
            'Credibility Score (alias)': '<strong>Credibility Score:</strong>',
            'credibility score(s) (alias)': 'Upgrade to see credibility scores',
            'Truth Delta Score (alias)': "label: 'Truth Delta Score'",
            'request evidence from investors': 'the ability to request evidence from investors',
        }
        for name, sample in samples.items():
            with self.subTest(name=name):
                self.assertIn(name, retired_phrases(sample))

    def test_the_canonical_name_and_the_per_claim_sentence_are_not_retired(self):
        for fine in ('Evidence Credibility:', 'You get an Evidence Credibility score, claim-by-claim',
                     'No external data was found for this claim.'):
            with self.subTest(text=fine):
                self.assertEqual(retired_phrases(fine), [])

    def test_the_scan_reaches_the_surfaces(self):
        names = {path.name for path in _surfaces()}
        for required in ('home.html', 'billing.html', 'truth_delta_dashboard.html', 'ic_memo.html',
                         'memo_detail.html', 'profile.html', 'ic_memo.py'):
            with self.subTest(file=required):
                self.assertIn(required, names)


class NoRetiredPromiseRemainsTests(SimpleTestCase):

    def test_no_surface_uses_retired_wording(self):
        offenders = []
        for path in _surfaces():
            found = retired_phrases(path.read_text(encoding='utf8', errors='ignore'))
            if found:
                offenders.append(f'{path.relative_to(settings.BASE_DIR)}: {found}')
        self.assertEqual(offenders, [], 'Retired public wording is back:\n' + '\n'.join(offenders))


class TheApprovedPromiseIsServedTests(TestCase):

    def test_the_home_page_keeps_the_private_company_sentence(self):
        content = self.client.get(reverse('pages:home')).content.decode('utf8')
        self.assertIn(PRIVATE_COMPANY_SENTENCE, content)
        self.assertIn('Zelda adds source-linked business analysis.', content)

    def test_the_pricing_page_makes_no_absolute_screening_claim(self):
        # The template, not one rendered role: each plan card shows to its own role only.
        content = (Path(settings.BASE_DIR) / 'templates' / 'billing' / 'billing.html').read_text(encoding='utf8')
        self.assertIn('screen decks with first-pass investment intelligence', content)
        self.assertIn('screen listings with first-pass acquisition intelligence', content)
        self.assertNotIn('every deck', content)
        self.assertNotIn('every listing', content)
