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

    def test_the_scope_comes_from_the_filing_types_not_the_prose(self):
        """
        The source's prose summarises corporate data as "corporations, limited
        liability companies and limited partnerships". Its own published type
        list is wider: non-profit variants, trusts and registered agents are in
        the same file. The codes are what the file contains, so the codes are
        the scope -- an earlier version of this module encoded the prose and
        under-claimed by three families.
        """
        self.assertEqual(SCOPED_ENTITY_FAMILIES[DATASET_CORPORATE],
                         ('corporation', 'nonprofit_corporation',
                          'limited_partnership', 'limited_liability_company',
                          'trust', 'registered_agent'))

    def test_every_published_filing_type_maps_to_a_scoped_family(self):
        """
        An unmapped filing type would be parsed into a family nobody declared,
        and would then inherit coverage it was never measured for.
        """
        from .registry_source import CORPORATE_FILING_TYPES, FILING_TYPE_FAMILIES
        self.assertEqual(set(FILING_TYPE_FAMILIES), set(CORPORATE_FILING_TYPES))
        for code, family in FILING_TYPE_FAMILIES.items():
            with self.subTest(code=code):
                self.assertIn(family, SCOPED_ENTITY_FAMILIES[DATASET_CORPORATE])

    def test_trusts_and_agents_are_inside_the_dataset(self):
        """
        Counter-intuitive and measured: they share the corporate file, so a
        trust missing from the snapshot IS informative where a trademark is
        not.
        """
        from .registry_source import COVERAGE_BROAD
        for family in ('trust', 'registered_agent', 'nonprofit_corporation'):
            with self.subTest(family=family):
                self.assertTrue(absence_is_meaningful(
                    COVERAGE_BROAD, DATASET_CORPORATE, family))

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

    def test_the_dataset_statement_is_attributed_dated_and_now_verified(self):
        """
        The statement has been retrieved from the source, so it is no longer
        second-hand -- but HOW it was retrieved is part of the record. Sunbiz
        returns a Cloudflare bot-verification interstitial to this project and
        defeating bot detection is out of bounds, so a human read the pages.
        That is weaker provenance than a programmatic fetch and a re-check
        needs a human again, which is worth stating rather than losing.
        """
        statement = dataset_statement(DATASET_CORPORATE)
        self.assertIn('dos.fl.gov', statement['source_url'])
        self.assertIn('data-definitions', statement['definitions_url'])
        self.assertTrue(statement['quoted_claim'])
        self.assertTrue(statement['verified'])
        self.assertIsInstance(statement['retrieved_at'], date)
        self.assertTrue(statement['verified_by'])

    def test_verifying_the_statement_does_not_by_itself_grant_coverage(self):
        """
        The two gates are independent, and conflating them would be the whole
        error this contract exists to prevent. Knowing what a corpus is MEANT
        to contain says nothing about whether it was ingested. Florida's
        statement is verified and Florida has no ingestion, so coverage stays
        unmeasured.
        """
        verdict, reason = assess_coverage([])
        self.assertEqual(verdict, COVERAGE_UNMEASURED)
        self.assertIn('no ingestion', reason.lower())


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


class TheEntityKeyCameFromTheFieldDefinitionsTests(SimpleTestCase):
    """
    It was None until the published definitions were read -- "probably the
    document number" is how five Filed sources became the whole truth. Now it
    is encoded, with the layout it was read from.
    """

    def test_the_key_is_the_document_number_at_its_published_position(self):
        from .registry_source import ENTITY_KEY_LAYOUT
        self.assertEqual(ENTITY_KEY_FIELD, 'document_number')
        self.assertEqual(ENTITY_KEY_LAYOUT, {'start': 1, 'length': 12})

    def test_the_same_position_in_both_files_is_what_makes_it_a_join_key(self):
        from .registry_source import ENTITY_KEY_LAYOUT, EVENT_KEY_FIELDS
        self.assertEqual(ENTITY_KEY_LAYOUT['start'], 1)
        self.assertEqual(EVENT_KEY_FIELDS, ('document_number', 'sequence_number'))

    def test_the_key_value_may_be_six_or_twelve_characters(self):
        """
        The field is 12 wide; the value is not always. A parser assuming 12
        would mangle every short document number.
        """
        from .registry_source import ENTITY_KEY_VALUE_LENGTHS
        self.assertEqual(ENTITY_KEY_VALUE_LENGTHS, (6, 12))

    def test_many_rows_may_share_one_key(self):
        """
        The correction that matters most here. An earlier draft recorded
        uniqueness as unestablished and told the parser to "assert it and fail
        loudly" -- which would have rejected valid Sunbiz files, because the
        usage guide says duplicate document numbers legitimately occur.

        Deduplicating on the document number alone is the opposite error: it
        would discard rows the source deliberately included. Both are wrong,
        and the open question is how several rows combine, not whether they
        exist.
        """
        from .registry_source import OPEN_UNKNOWNS, ROWS_PER_KEY
        self.assertEqual(ROWS_PER_KEY, 'many')
        self.assertNotIn('key_uniqueness', OPEN_UNKNOWNS)
        self.assertIn('delta_merge_semantics', OPEN_UNKNOWNS)

    def test_the_module_never_calls_the_key_a_unique_identifier(self):
        """
        A documentation guard, in the same spirit as the one holding Filed's
        registration row off the words 'founder' and 'verified'.

        An earlier revision described the document number as the "cross-file
        unique identifier" in a comment sitting directly above the block
        stating that duplicate document numbers legitimately occur. The code
        was right and the prose set a trap: a future reader meets 'unique',
        reasonably infers one row per number, and writes the deduplication that
        throws away rows the source deliberately included.
        """
        import io
        from pathlib import Path
        from django.conf import settings

        text = io.open(Path(settings.BASE_DIR) / 'zelda_api' / 'registry_source.py',
                       encoding='utf-8').read()
        self.assertGreater(len(text), 500, 'positive control: the file was read')
        # Reported as a count, not with assertNotIn: the haystack is the whole
        # module, and a failing assertNotIn prints all of it, burying the one
        # line that matters under 20KB of source.
        self.assertEqual(
            text.lower().count('unique identifier'), 0,
            "registry_source.py calls the document number a 'unique "
            "identifier'. It is not row-unique -- duplicate document numbers "
            'legitimately occur -- and that phrase is what invites a future '
            'uniqueness assertion that would reject valid Sunbiz files.')
        # The disambiguation that replaced it must still be there.
        self.assertIn('never ROW identity', text)

    def test_the_docstring_does_not_contradict_the_constants(self):
        """
        The guard above was too narrow and let a bigger version of the same
        trap survive: after the field definitions were read, the module
        DOCSTRING still announced "`ENTITY_KEY_FIELD` is None" and "The Florida
        dataset statement is UNVERIFIED" while the code said otherwise.

        A reader trusts the docstring over a constant 200 lines down, so the
        two claims that have actually flipped are checked against the values
        they describe.
        """
        import io
        from pathlib import Path
        from django.conf import settings
        from . import registry_source

        doc = (registry_source.__doc__ or '')
        self.assertGreater(len(doc), 500, 'positive control: the docstring was read')
        if registry_source.ENTITY_KEY_FIELD is not None:
            self.assertNotIn('`ENTITY_KEY_FIELD` is None', doc)
        if dataset_statement(DATASET_CORPORATE)['verified']:
            self.assertNotIn('statement is UNVERIFIED', doc)
            self.assertNotIn("`verified: False`", doc)

    def test_the_duplicate_row_caveat_is_recorded_as_the_sources_own(self):
        from .registry_source import SOURCE_CAVEATS
        joined = ' '.join(SOURCE_CAVEATS).lower()
        self.assertIn('duplicate document numbers', joined)
        self.assertIn('must not be', joined)


class TheRecordGeometryReconcilesTests(SimpleTestCase):
    """
    Cheap transcription check: each record length must equal the last field's
    start plus its length minus one. Getting a fixed-width layout one byte
    wrong shifts every later field and produces plausible nonsense rather than
    an error.
    """

    def test_the_published_lengths_are_pinned(self):
        from .registry_source import FIELD_COUNTS, RECORD_LENGTHS
        self.assertEqual(RECORD_LENGTHS, {'data': 1440, 'event': 662})
        self.assertEqual(FIELD_COUNTS, {'data': 79, 'event': 25})

    def test_the_data_record_length_reconciles_with_its_last_field(self):
        from .registry_source import RECORD_LENGTHS
        self.assertEqual(1437 + 4 - 1, RECORD_LENGTHS['data'])

    def test_the_event_record_length_reconciles_with_its_last_field(self):
        from .registry_source import RECORD_LENGTHS
        self.assertEqual(653 + 10 - 1, RECORD_LENGTHS['event'])


class WhatTheSourceWarnsAboutItsOwnDataTests(SimpleTestCase):
    """
    Bounds on what a finding may claim, from the source itself. Florida is the
    strongest officer source in the suite and still cannot support "these are
    the officers".
    """

    def test_officer_evidence_is_capped_at_six_with_an_overflow_flag(self):
        from .registry_source import MAX_OFFICERS_IN_RECORD, MORE_OFFICERS_FLAG_POSITION
        self.assertEqual(MAX_OFFICERS_IN_RECORD, 6)
        self.assertEqual(MORE_OFFICERS_FLAG_POSITION, 495)

    def test_the_sources_own_caveats_are_recorded(self):
        from .registry_source import SOURCE_CAVEATS
        joined = ' '.join(SOURCE_CAVEATS).lower()
        self.assertIn('officers may be truncated', joined)
        self.assertIn('may not be current', joined)
        self.assertIn('expected gap', joined)
        self.assertIn('malformed rows', joined)

    def test_the_open_unknowns_are_enumerated_for_the_parser(self):
        """
        Each would fail silently if assumed: a misread date format yields
        plausible wrong dates, unknown shard names make a partial release look
        complete, and the two design gaps let stale or incomplete state read as
        current.
        """
        from .registry_source import OPEN_UNKNOWNS
        self.assertEqual(
            set(OPEN_UNKNOWNS),
            {'date_format', 'shard_names', 'delta_merge_semantics',
             'corpus_generation', 'delta_continuity'})
        for name, why in OPEN_UNKNOWNS.items():
            with self.subTest(unknown=name):
                self.assertGreater(len(why), 40)

    def test_the_two_design_gaps_are_recorded_rather_than_discovered_later(self):
        """
        Both are latent in this module's own functions today, and both are
        harmless only because nothing has been ingested yet.

        `assess_coverage` judges every snapshot it is handed, so one old
        incomplete release would hold coverage down forever after a complete
        one superseded it. `freshness` takes the maximum delta_through, so a
        missing middle day reads as fully current. Writing them down is what
        stops them becoming surprises during production ingestion.
        """
        from .registry_source import OPEN_UNKNOWNS
        self.assertIn('governing', OPEN_UNKNOWNS['corpus_generation'].lower())
        self.assertIn('contiguous', OPEN_UNKNOWNS['delta_continuity'].lower())


class TheDailyFilenameDateIsNotABusinessDateTests(SimpleTestCase):
    """
    `20261002c.txt` does not mean "these filings happened on 2 October". The
    source defines the filename date as the date the information was ENTERED
    INTO THE DATABASE -- so a parser using it as a filing or effective date
    would date every record in the file wrongly, and plausibly enough that
    nobody would notice.

    This is also what `delta_through` means, which is why it belongs in the
    contract rather than in the parser.
    """

    def test_the_filename_date_means_database_entry(self):
        from .registry_source import DAILY_FILENAME_DATE_MEANS
        self.assertEqual(DAILY_FILENAME_DATE_MEANS, 'entered_into_database')

    def test_it_is_explicitly_not_a_filing_or_effective_or_event_date(self):
        from .registry_source import (DAILY_FILENAME_DATE_IS_NOT,
                                      DAILY_FILENAME_DATE_MEANS)
        self.assertEqual(DAILY_FILENAME_DATE_IS_NOT,
                         ('filing_date', 'effective_date', 'event_date'))
        self.assertNotIn(DAILY_FILENAME_DATE_MEANS, DAILY_FILENAME_DATE_IS_NOT)

    def test_a_malformed_row_must_be_rejected_not_shifted(self):
        """
        The source says malformed rows occur, from special characters or line
        breaks embedded in the data. In a fixed-width layout a short row shifts
        every later field, so silent tolerance is worse than failure.
        """
        from .registry_source import MALFORMED_ROW_POLICY
        self.assertEqual(MALFORMED_ROW_POLICY, 'reject_explicitly')

    def test_the_quarterly_shard_names_are_still_unresolved(self):
        """
        The page names `cordata.zip` and `corevent.zip` and says the data is
        split into ten files by the final digit of the record number -- without
        naming them, and without stating that the number is the document
        number. Encoding guessed names would let a partial release look
        complete to assess_coverage.
        """
        from .registry_source import OPEN_UNKNOWNS
        self.assertIn('shard_names', OPEN_UNKNOWNS)
        self.assertIn('does not name them', OPEN_UNKNOWNS['shard_names'])


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
