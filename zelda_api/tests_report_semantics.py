"""
A report must say which rules produced it.

#97 and #98 changed what a Truth Delta report MEANS, not just how it is
built. Before #97 the SEC resolver took the first CIK of a prefix match
returning up to ten filers, so a report can contain financial evidence about
a different company. Before #98 a source that never answered was reported as
`no_external_evidence` -- "we looked and nothing was there" -- when the truth
was that the attempt failed.

Reports of both kinds are in the database now, and nothing distinguishes them
from reports produced under the current rules. An investor opening an old one
reads superseded semantics with no marker.

The fix is a semantics stamp, and two shortcuts must be impossible:

BACKFILLING
    Giving historical rows the current version would erase the very
    distinction the field exists to preserve.

INFERRING FROM created_at
    `created_at` records when a report was WRITTEN. What governed it was
    whatever code was DEPLOYED at that moment, and nothing records deploys.
    Merge time is not deploy time. A date-partitioned guess would be exactly
    what this architecture refuses: manufactured provenance presented as
    fact.

So `unknown` is not a fallback. It is the accurate value, and it has to stay
accurate.

The last two tests matter as much as the field. If an `unknown` report
renders identically to a current one, the database holds the distinction
while every surface erases it -- the same shape as the #93 defect, where both
ends were right and the path between them did not exist. A provenance field
nobody surfaces does not exist to the person making the decision.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .truth_delta_models import (
    TRUTH_DELTA_SEMANTICS, UNKNOWN_SEMANTICS, TruthDeltaReport,
)
from .vector_models import DocumentSource

User = get_user_model()


class AReportRecordsTheRulesThatProducedItTests(TestCase):

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('sem_owner', password='x')
        self.client.force_login(self.user)
        self.document = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Subject Co', uploaded_by=self.user,
            document_type='pitch_deck', status='analyzed',
        )

    def report(self, **kwargs):
        return TruthDeltaReport.objects.create(
            document=self.document, overall_truth_score=70.0,
            credibility_risk='low', summary='ok',
            details={'claims': [{'category': 'revenue'}]}, **kwargs)

    # 1. new reports carry the current semantics
    def test_a_report_the_engine_writes_carries_the_current_semantics(self):
        from .truth_delta_engine import TruthDeltaEngine
        self.assertEqual(TruthDeltaEngine().semantics_version, TRUTH_DELTA_SEMANTICS)

    # 2. a row written without a stamp is unknown, never the current version
    def test_an_unstamped_row_is_unknown_not_the_current_version(self):
        """
        The migration's behaviour, expressed through the field default: every
        row that predates stamping reads `unknown`. If the default were the
        current version, every historical report would silently claim rules
        it was never produced under.
        """
        report = self.report()
        self.assertEqual(report.engine_version, UNKNOWN_SEMANTICS)
        self.assertNotEqual(report.engine_version, TRUTH_DELTA_SEMANTICS)

    # 3. unknown is distinguishable from any known version
    def test_unknown_is_distinguishable_from_a_known_version(self):
        self.assertFalse(self.report().semantics_known)
        self.assertTrue(self.report(engine_version=TRUTH_DELTA_SEMANTICS).semantics_known)

    # 4. and it cannot be inferred from when the row was written
    def test_a_recent_row_with_no_stamp_is_still_unknown(self):
        """
        Kills the tempting shortcut: "rows created after the fix must have the
        new semantics". created_at records when the report was WRITTEN, not
        which code was DEPLOYED. A row created one second ago with no stamp is
        still of unknown provenance, and saying otherwise invents the fact.
        """
        report = self.report()  # created_at is now
        self.assertFalse(
            report.semantics_known,
            'semantics were inferred from how recently the row was written',
        )

    # 5. an unknown report still renders
    def test_an_unknown_report_still_renders(self):
        """
        Missing provenance is our gap, not the reader's. The page must not
        punish them for it by refusing to show the report.
        """
        report = self.report()
        response = self.client.get(
            reverse('zelda_api:truth_delta_ui', args=[report.document_id]))
        self.assertEqual(response.status_code, 200)

    # 6. and is not presented as current
    def test_an_unknown_report_is_not_presented_as_current(self):
        """
        The consequence the field exists for. Rendering it identically to a
        current-semantics report preserves the data and destroys the meaning.
        """
        self.report()
        html = self.client.get(
            reverse('zelda_api:truth_delta_ui', args=[self.document.id])).content.decode()
        self.assertIn('predates', html.lower())

    def test_a_current_report_carries_no_such_notice(self):
        """Control: the notice must be a statement about THIS report, not
        boilerplate that renders on every page regardless."""
        TruthDeltaReport.objects.all().delete()
        self.report(engine_version=TRUTH_DELTA_SEMANTICS)
        html = self.client.get(
            reverse('zelda_api:truth_delta_ui', args=[self.document.id])).content.decode()
        self.assertNotIn('predates', html.lower())
