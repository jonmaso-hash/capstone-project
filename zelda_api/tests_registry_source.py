"""
The contract for a first-party registry mirror. No parser, no provider yet.

Zelda is going to hold an official Florida corporate dataset locally instead of
asking a vendor. That is worth having for one reason above all: it can answer
WHICH OFFICIAL ARTIFACT produced an observation, what corpus that artifact
represented, how far daily files had advanced it, and therefore whether a MISS
means anything. Filed cannot answer the last question, which is why Delaware
had to be marked `coverage: partial` on the strength of two sample queries.

So 5A establishes the contract and nothing else. No fixed-width parsing, no
ingestion, no identity changes.

THE SHAPE, and the order matters:

    official artifact
        -> immutable ingestion provenance
        -> normalized observations
        -> the EXISTING Zelda identity authority
        -> findings

and never `artifact -> Florida resolver -> report`. A jurisdiction-specific
resolver would recreate the dual-identity-authority defect that PRs #102-#105
removed; a structural test below makes that hard to do by accident.

TWO THINGS THIS MODULE DELIBERATELY DOES NOT DECIDE.

The entity key. The document number is probably the right natural key, and
"probably" is how five Filed states became the whole truth. Sunbiz publishes
formal field definitions, and those are the authority for what the document
number means and whether it is stable. Until they have been read,
`ENTITY_KEY_FIELD` is None and a test holds it there.

Whether Florida's dataset statement is true. Sunbiz's download pages are behind
Cloudflare bot verification, which this project does not defeat -- the same
evidence-based line that stopped the Secretary of State scraper. The statement
is therefore recorded as an attributed, dated, UNVERIFIED quotation, and
`coverage` cannot reach 'broad' while it stays unverified. Florida consequently
remains 'unmeasured', which is where PR 4 left it.

COVERAGE AND FRESHNESS ARE DIFFERENT QUESTIONS. 'broad' is the breadth of the
documented snapshot corpus; `delta_through` is how current the mirror is. A
quarter-old snapshot is broad-and-stale, never partial -- conflating them would
turn an aging mirror into a reason to doubt its completeness.
"""
from datetime import date

from django.test import SimpleTestCase

from .registry_source import (
    ARTIFACT_DAILY_DELTA, ARTIFACT_QUARTERLY_SNAPSHOT, AUTHORITY_SOURCE,
    COVERAGE_BROAD, COVERAGE_PARTIAL, COVERAGE_UNMEASURED, DATASET_CORPORATE,
    ENTITY_KEY_FIELD, JURISDICTION, PARSER_SCHEMA_VERSION, SCOPED_ENTITY_FAMILIES,
    IngestionProvenance, absence_is_meaningful, assess_coverage,
    dataset_statement, ingestion_identity, is_replay_of,
)

HASH_A = 'a' * 64
HASH_B = 'b' * 64


def provenance(**overrides):
    """A complete, well-formed quarterly ingestion. Overridden per test."""
    fields = dict(
        jurisdiction=JURISDICTION,
        authority_source=AUTHORITY_SOURCE,
        dataset_family=DATASET_CORPORATE,
        artifact_type=ARTIFACT_QUARTERLY_SNAPSHOT,
        source_filename='cordata0.txt',
        source_artifact_sha256=HASH_A,
        downloaded_at=date(2026, 10, 2),
        snapshot_as_of=date(2026, 10, 1),
        delta_through=None,
        records_ingested=1200,
        shards_expected=('cordata0.txt',),
        shards_parsed=('cordata0.txt',),
        parser_schema_version=PARSER_SCHEMA_VERSION,
    )
    fields.update(overrides)
    return IngestionProvenance(**fields)


class TheDatasetScopeIsNarrowAndStatedTests(SimpleTestCase):

    def test_the_corporate_family_is_three_entity_types(self):
        self.assertEqual(SCOPED_ENTITY_FAMILIES[DATASET_CORPORATE],
                         ('corporation', 'limited_liability_company',
                          'limited_partnership'))

    def test_it_is_not_generalised_into_all_florida_businesses(self):
        """
        'Corporate data' is corporations, LLCs and limited partnerships. A
        sole proprietorship or a trademark is outside it, and inheriting
        corporate coverage would claim evidence about a corpus never ingested.
        """
        families = SCOPED_ENTITY_FAMILIES[DATASET_CORPORATE]
        for outside in ('trademark', 'sole_proprietorship', 'general_partnership',
                        'fictitious_name'):
            with self.subTest(family=outside):
                self.assertNotIn(outside, families)

    def test_the_dataset_statement_is_attributed_dated_and_unverified(self):
        """
        Sunbiz sits behind Cloudflare bot verification, which this project does
        not defeat. So the claim is recorded as a quotation with a source and a
        date, and marked unverified -- not asserted as fact.
        """
        statement = dataset_statement(DATASET_CORPORATE)
        self.assertIn('dos.fl.gov', statement['source_url'])
        self.assertTrue(statement['quoted_claim'])
        self.assertFalse(statement['verified'])
        self.assertTrue(statement['retrieved_at'] is None
                        or isinstance(statement['retrieved_at'], date))


class CoverageMustBeEarnedTests(SimpleTestCase):

    def test_a_complete_verified_snapshot_would_qualify_as_broad(self):
        """
        The positive control. Without it every rule below could be satisfied by
        a function that always refuses, and the contract would be untestable.
        """
        verdict, reason = assess_coverage([provenance()], statement_verified=True)
        self.assertEqual(verdict, COVERAGE_BROAD, reason)

    def test_an_unverified_dataset_statement_cannot_be_broad(self):
        """Today's real state: Florida stays unmeasured."""
        verdict, reason = assess_coverage([provenance()], statement_verified=False)
        self.assertEqual(verdict, COVERAGE_UNMEASURED)
        self.assertIn('statement', reason.lower())

    def test_no_ingestion_at_all_is_unmeasured_not_partial(self):
        verdict, reason = assess_coverage([], statement_verified=True)
        self.assertEqual(verdict, COVERAGE_UNMEASURED)

    def test_a_missing_shard_cannot_be_broad(self):
        verdict, reason = assess_coverage(
            [provenance(shards_expected=('cordata0.txt', 'cordata1.txt'),
                        shards_parsed=('cordata0.txt',))],
            statement_verified=True)
        self.assertNotEqual(verdict, COVERAGE_BROAD)
        self.assertIn('shard', reason.lower())

    def test_an_artifact_without_a_hash_cannot_be_broad(self):
        verdict, reason = assess_coverage([provenance(source_artifact_sha256='')],
                                          statement_verified=True)
        self.assertNotEqual(verdict, COVERAGE_BROAD)
        self.assertIn('hash', reason.lower())

    def test_row_count_alone_does_not_earn_broad(self):
        """
        'We ingested a lot of rows' is the claim this contract exists to
        refuse: a million rows from an incomplete set of shards is still
        incomplete.
        """
        verdict, _ = assess_coverage(
            [provenance(records_ingested=5_000_000,
                        shards_expected=('a.txt', 'b.txt'), shards_parsed=('a.txt',))],
            statement_verified=True)
        self.assertNotEqual(verdict, COVERAGE_BROAD)

    def test_only_a_snapshot_establishes_breadth_not_a_delta(self):
        """A day of new filings is not a corpus."""
        verdict, reason = assess_coverage(
            [provenance(artifact_type=ARTIFACT_DAILY_DELTA,
                        snapshot_as_of=None, delta_through=date(2026, 10, 2))],
            statement_verified=True)
        self.assertEqual(verdict, COVERAGE_UNMEASURED)
        self.assertIn('snapshot', reason.lower())


class BreadthIsNotFreshnessTests(SimpleTestCase):

    def test_a_stale_snapshot_is_broad_and_stale_never_partial(self):
        """
        Partial means the corpus was incomplete. Old means it was complete
        then. Conflating them turns an aging mirror into doubt about its
        completeness.
        """
        verdict, _ = assess_coverage(
            [provenance(snapshot_as_of=date(2025, 1, 1))], statement_verified=True)
        self.assertEqual(verdict, COVERAGE_BROAD)
        self.assertNotEqual(verdict, COVERAGE_PARTIAL)

    def test_a_delta_advances_freshness_without_changing_breadth(self):
        snapshot = provenance()
        delta = provenance(artifact_type=ARTIFACT_DAILY_DELTA,
                           source_filename='20261002c.txt',
                           source_artifact_sha256=HASH_B,
                           snapshot_as_of=None, delta_through=date(2026, 10, 2))
        verdict, _ = assess_coverage([snapshot, delta], statement_verified=True)
        self.assertEqual(verdict, COVERAGE_BROAD)


class AbsenceIsOnlyMeaningfulInsideTheContractTests(SimpleTestCase):

    def test_absence_means_nothing_while_coverage_is_unmeasured(self):
        self.assertFalse(absence_is_meaningful(
            COVERAGE_UNMEASURED, DATASET_CORPORATE, 'corporation'))

    def test_absence_means_nothing_for_a_family_outside_the_dataset(self):
        """
        A trademark missing from a corporate snapshot is not evidence: the
        snapshot never contained trademarks.
        """
        self.assertFalse(absence_is_meaningful(
            COVERAGE_BROAD, DATASET_CORPORATE, 'trademark'))
        self.assertFalse(absence_is_meaningful(
            COVERAGE_BROAD, DATASET_CORPORATE, 'sole_proprietorship'))

    def test_absence_can_be_meaningful_for_a_scoped_family_under_broad_coverage(self):
        """The one case where a local miss is allowed to mean something."""
        self.assertTrue(absence_is_meaningful(
            COVERAGE_BROAD, DATASET_CORPORATE, 'corporation'))

    def test_partial_coverage_never_makes_absence_meaningful(self):
        """The Delaware lesson, carried into the first-party mirror."""
        self.assertFalse(absence_is_meaningful(
            COVERAGE_PARTIAL, DATASET_CORPORATE, 'corporation'))


class IngestionIsIdempotentOnTheArtifactHashTests(SimpleTestCase):

    def test_the_hash_is_the_ingestion_identity(self):
        self.assertEqual(ingestion_identity(provenance()), HASH_A)

    def test_replaying_the_same_artifact_is_recognised_as_a_replay(self):
        self.assertTrue(is_replay_of(provenance(), provenance()))

    def test_the_same_bytes_under_a_different_filename_is_still_a_replay(self):
        """
        Sunbiz filenames carry dates; the bytes are what was ingested. A rename
        must not produce a second ingestion of the same corpus.
        """
        self.assertTrue(is_replay_of(provenance(),
                                     provenance(source_filename='renamed.txt')))

    def test_changed_bytes_are_a_different_ingestion(self):
        self.assertFalse(is_replay_of(provenance(), provenance(source_artifact_sha256=HASH_B)))

    def test_an_artifact_with_no_hash_is_never_treated_as_a_replay(self):
        """
        Otherwise two un-hashed artifacts would look identical and the second
        would be silently skipped.
        """
        blank = provenance(source_artifact_sha256='')
        self.assertFalse(is_replay_of(blank, blank))


class TheEntityKeyIsNotDecidedYetTests(SimpleTestCase):

    def test_no_natural_key_is_encoded_before_the_field_definitions_are_read(self):
        """
        The document number is probably correct. 'Probably' is how five Filed
        states became the whole truth, and Sunbiz's published field definitions
        are the authority for what the document number means and whether it is
        stable. This test fails the moment someone encodes a key without
        pinning that definition, which is the intended friction.
        """
        self.assertIsNone(ENTITY_KEY_FIELD)


class TheMirrorIsNotAnIdentityAuthorityTests(SimpleTestCase):
    """
    Structural, not behavioural. The mirror supplies evidence; the existing
    authority decides identity. PRs #102-#105 removed a dual-resolution defect,
    and a jurisdiction-specific resolver would recreate it -- so the guard reads
    the source rather than trusting that nobody will write one.
    """

    def test_the_module_defines_no_resolver(self):
        import io
        from pathlib import Path
        from django.conf import settings

        text = io.open(Path(settings.BASE_DIR) / 'zelda_api' / 'registry_source.py',
                       encoding='utf-8').read()
        self.assertGreater(len(text), 500, 'positive control: the file was read')
        for forbidden in ('class FloridaCompanyResolver', 'def resolve_company_identity',
                          'def resolve_identity', 'class RegistryResolver'):
            with self.subTest(symbol=forbidden):
                self.assertNotIn(forbidden, text)

    def test_the_module_exposes_no_identity_decision(self):
        from . import registry_source
        for name in dir(registry_source):
            if name.startswith('_'):
                continue
            with self.subTest(name=name):
                self.assertNotIn('resolve', name.lower())
