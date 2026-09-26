"""
Every surface that names Truth Delta's evidence sources must name the sources
that actually run.

Five surfaces describe them today, and they disagree:

    templates/zelda_api/ic_memo.html          "SEC EDGAR, Crunchbase, and
                                               recent news coverage"
    templates/truth_delta_dashboard.html (x2) "SEC EDGAR, Crunchbase and
                                               recent news"
    templates/truth_delta_paywall.html        "SEC EDGAR and, where configured,
                                               Crunchbase/news"
    templates/accounts/profile.html           "SEC EDGAR and, where configured,
                                               Crunchbase/news"

Two of the five already qualify it. Three assert it flatly. And the flat
assertion is false: `CrunchbaseIntegration.authenticate()` returns False
without CRUNCHBASE_API_KEY, so `DataSourceManager.get_all_active()` skips it
entirely. The key is deliberately unset -- Crunchbase charges, and paid
sources come last.

"Recent news" is a second, different overstatement. NewsIntegration is live
when NEWS_API_KEY is set, but every one of its extract_* methods returns None
and its own docstring says headlines are "not a claim source itself". News
supplies context to Claude; it never verifies a claim.

This is not the claim-strength axis that pages/tests_claim_strength.py guards.
Nothing here is an overclaim of certainty -- these are false statements of
MECHANISM and COVERAGE, and a vocabulary scanner cannot see them because
"Crunchbase" is only wrong when it isn't configured.

The fix follows zelda_api/disclaimers.py, whose docstring already states the
principle for this exact failure: "one string so the wording can't drift
between report types as they're edited independently." So the sources are
described in one place, derived from the same settings the fetch layer reads,
and the templates render that rather than each spelling it out.
"""
from django.test import SimpleTestCase, TestCase, override_settings

from .disclaimers import evidence_sources_sentence, verifying_source_names


class TheSourceListFollowsTheConfigurationTests(SimpleTestCase):

    @override_settings(CRUNCHBASE_API_KEY='', NEWS_API_KEY='')
    def test_an_unconfigured_source_is_not_named(self):
        """
        The live configuration. Naming Crunchbase here describes a lookup the
        fetch layer never performs, because get_all_active() skips an
        integration whose authenticate() returns False.
        """
        self.assertEqual(verifying_source_names(), ['SEC EDGAR'])
        sentence = evidence_sources_sentence()
        self.assertIn('SEC EDGAR', sentence)
        self.assertNotIn('Crunchbase', sentence)

    @override_settings(CRUNCHBASE_API_KEY='cb-key', NEWS_API_KEY='')
    def test_a_configured_source_is_named(self):
        """Control: the sentence must be able to say Crunchbase, or the test
        above would pass against a function that can only ever say one thing."""
        self.assertIn('Crunchbase', verifying_source_names())
        self.assertIn('Crunchbase', evidence_sources_sentence())

    @override_settings(CRUNCHBASE_API_KEY='', NEWS_API_KEY='news-key')
    def test_news_is_described_as_context_not_verification(self):
        """
        News is fetched when configured, so the sentence may mention it -- but
        it contributes no claims, so it must not be listed among the sources a
        claim is checked against.
        """
        self.assertNotIn('recent news', verifying_source_names())
        sentence = evidence_sources_sentence()
        self.assertIn('context', sentence.lower())

    @override_settings(CRUNCHBASE_API_KEY='', NEWS_API_KEY='')
    def test_news_is_not_mentioned_when_it_is_not_configured(self):
        self.assertNotIn('news', evidence_sources_sentence().lower())


class NoTemplateSpellsOutTheSourcesItselfTests(SimpleTestCase):
    """
    The structural half, modelled on billing/tests_pricing_source_of_truth.py's
    "no template hardcodes a monthly price". A template that names a source in
    its own words cannot follow the configuration, and that is precisely how
    three surfaces came to assert a source that never runs.
    """

    TEMPLATES = [
        'templates/zelda_api/ic_memo.html',
        'templates/truth_delta_dashboard.html',
        'templates/truth_delta_paywall.html',
        'templates/accounts/profile.html',
    ]

    def test_no_template_hardcodes_a_source_name(self):
        import io
        offenders = []
        for path in self.TEMPLATES:
            text = io.open(path, encoding='utf-8').read()
            for name in ('Crunchbase', 'SEC EDGAR'):
                if name in text:
                    offenders.append(f'{path}: "{name}"')
        self.assertEqual(
            offenders, [],
            'A template names an evidence source in its own words. It will not '
            'follow the configuration, and three surfaces already drifted this '
            'way. Render the shared sentence instead:\n  ' + '\n  '.join(offenders),
        )

    def test_the_scan_reads_real_files(self):
        """Positive control: a scan of missing files would pass the test above."""
        import io
        for path in self.TEMPLATES:
            with self.subTest(path=path):
                self.assertGreater(len(io.open(path, encoding='utf-8').read()), 500)


class TheDashboardUsesTheEnginesVocabularyTests(TestCase):
    """
    The dashboard's own explanation says claims are marked "supported,
    unverified, or contradicted" -- three states, over an engine that reports
    five. Two-and-three-state framings imply a claim Zelda could not
    corroborate was found wanting, when the ordinary outcomes are that no
    source reports the metric or that two figures are not comparable. The
    homepage was corrected in #95; this is the same sentence on the product
    page, where an investor actually reads it.
    """

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        from django.contrib.auth import get_user_model
        self.user = get_user_model().objects.create_user('sn_owner', password='x')
        self.client.force_login(self.user)

    def render_dashboard(self):
        from django.urls import reverse
        from .truth_delta_models import TruthDeltaReport
        from .vector_models import DocumentSource
        doc = DocumentSource.objects.create(
            filename='d.pdf', source_entity='Subject Co', uploaded_by=self.user,
            document_type='pitch_deck', status='analyzed')
        TruthDeltaReport.objects.create(
            document=doc, overall_truth_score=70.0, credibility_risk='low',
            summary='ok', details={'claims': [{'category': 'revenue'}]})
        return self.client.get(
            reverse('zelda_api:truth_delta_ui', args=[doc.id])).content.decode()

    def test_the_page_does_not_describe_three_states(self):
        html = self.render_dashboard()
        self.assertNotIn('supported, unverified, or contradicted', html)

    def test_the_page_names_the_states_the_engine_reports(self):
        html = self.render_dashboard()
        self.assertIn('not comparable', html)

    def test_the_page_does_not_name_an_unconfigured_source(self):
        """End to end: the rendered page, not just the template source."""
        with override_settings(CRUNCHBASE_API_KEY=''):
            html = self.render_dashboard()
        self.assertNotIn('Crunchbase', html)
