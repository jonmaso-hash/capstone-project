"""
The contract for a first-party registry mirror. Contract only -- no parser.

Zelda will hold an official Florida corporate dataset locally rather than
asking a vendor for it. The reason is not cost: it is that a local official
artifact can answer a question no vendor call can. It can say WHICH artifact
produced an observation, what corpus that artifact represented, how far daily
files had advanced it, and therefore whether a MISS means anything. Filed
cannot answer the last one, which is why Delaware had to be recorded as
`coverage: partial` on the strength of two sample queries.

    official artifact
        -> immutable ingestion provenance
        -> normalized observations
        -> the EXISTING Zelda identity authority
        -> findings

Never `artifact -> Florida resolver -> report`. A jurisdiction-specific
resolver would recreate the dual-identity-authority defect PRs #102-#105
removed, so this module exposes no resolution at all and a structural test
keeps it that way.

TWO DELIBERATE REFUSALS.

`ENTITY_KEY_FIELD` is None. The document number is probably the right natural
key, and "probably" is exactly how five Filed sources became the whole truth.
Sunbiz publishes formal fixed-width field definitions; those are the authority
for what the document number means and whether it is stable enough to key a
business record. The key gets encoded after they are read, not before.

The Florida dataset statement is UNVERIFIED. The Sunbiz download pages sit
behind Cloudflare bot verification, which this project does not defeat -- the
same evidence-based line that stopped the Secretary of State scraper. So the
claim is carried as an attributed, dated quotation with `verified: False`, and
`assess_coverage` refuses 'broad' while it stays that way. Florida therefore
remains 'unmeasured', exactly where PR 4 left it, and a test holds it there
rather than relying on anyone's restraint.

COVERAGE AND FRESHNESS ARE DIFFERENT QUESTIONS, and the vocabulary is shared
with `filed_authority` on purpose: 'broad' is the breadth of the documented
corpus, `delta_through` is how current the mirror is. A quarter-old snapshot is
broad-and-stale, never partial. Calling it partial would turn an aging mirror
into doubt about its completeness, which is a different and false claim.
"""
import dataclasses
import datetime
from typing import Optional, Tuple

# --- the jurisdiction and its authority ----------------------------------
JURISDICTION = 'FL'
AUTHORITY_SOURCE = 'Florida Division of Corporations (Sunbiz)'

# --- dataset families ----------------------------------------------------
DATASET_CORPORATE = 'corporate'

# The filing types actually present in the corporate data file.
#
# THE SOURCE'S PROSE UNDERSTATES ITS OWN DATASET. The download page summarises
# corporate data as "corporations, limited liability companies and limited
# partnerships", while the type list it publishes also carries non-profit
# variants, trusts and registered agents. The codes are what is in the file, so
# the codes are the scope; the prose is recorded as the source's summary of it.
CORPORATE_FILING_TYPES = (
    'DOMP',     # domestic profit corporation
    'DOMNP',    # domestic non-profit corporation
    'FORP',     # foreign profit corporation
    'FORNP',    # foreign non-profit corporation
    'DOMLP',    # domestic limited partnership
    'FORLP',    # foreign limited partnership
    'FLAL',     # Florida limited liability company
    'FORL',     # foreign limited liability company
    'NPREG',    # non-profit registration
    'TRUST',    # trust
    'AGENT',    # registered agent
)

# What 'corporate data' covers, derived from the filing types above rather than
# from the prose. Still narrow: trademarks are a separate Sunbiz dataset, and a
# fictitious name or sole proprietorship is not here either. Inheriting
# corporate coverage for those would claim evidence about a corpus never
# ingested.
SCOPED_ENTITY_FAMILIES = {
    DATASET_CORPORATE: ('corporation', 'nonprofit_corporation',
                        'limited_partnership', 'limited_liability_company',
                        'trust', 'registered_agent'),
}

FILING_TYPE_FAMILIES = {
    'DOMP': 'corporation', 'FORP': 'corporation',
    'DOMNP': 'nonprofit_corporation', 'FORNP': 'nonprofit_corporation',
    'NPREG': 'nonprofit_corporation',
    'DOMLP': 'limited_partnership', 'FORLP': 'limited_partnership',
    'FLAL': 'limited_liability_company', 'FORL': 'limited_liability_company',
    'TRUST': 'trust', 'AGENT': 'registered_agent',
}

# --- artifact types ------------------------------------------------------
# A quarterly snapshot establishes a corpus. A daily file is the filings added
# on one working day, which advances freshness and establishes nothing about
# breadth.
ARTIFACT_QUARTERLY_SNAPSHOT = 'quarterly_snapshot'
ARTIFACT_DAILY_DELTA = 'daily_delta'

# --- coverage vocabulary, shared with filed_authority --------------------
COVERAGE_BROAD = 'broad'
COVERAGE_PARTIAL = 'partial'
COVERAGE_UNMEASURED = 'unmeasured'

# Bumped when the parser's interpretation of the fixed-width layout changes, so
# a re-ingestion under new parsing rules is distinguishable from a replay of
# the same bytes under the old ones.
PARSER_SCHEMA_VERSION = 1

# DECIDED, now that the published field definitions have been read. Field 1 of
# the data file is the Corporation Number at start 1, length 12, described as
# the corporate document number, and it sits at the same position and width in
# the event file -- which is what makes it the join key between filings and
# events. The usage guide calls it the cross-file unique identifier.
ENTITY_KEY_FIELD = 'document_number'
ENTITY_KEY_LAYOUT = {'start': 1, 'length': 12}

# The FIELD is 12 wide; the VALUE may be 6 or 12 characters. A parser that
# assumed 12 would mangle every short number, and one that stripped padding
# without recording the original width could not round-trip a record.
ENTITY_KEY_VALUE_LENGTHS = (6, 12)

# A ROW IS NOT AN ENTITY. The usage guide states that duplicate document
# numbers can legitimately occur -- a file may carry several rows about the same
# entity -- so the key identifies a business while rows about it are many.
#
# An earlier draft of this module had it backwards: it recorded uniqueness as
# unestablished and told 5B's parser to "assert it and fail loudly". That would
# have rejected valid Sunbiz files as corrupt. Deduplicating on the document
# number alone is equally wrong in the other direction: it would silently throw
# away rows the source deliberately included. How several rows for one entity
# combine is `delta_merge_semantics`, still open.
ROWS_PER_KEY = 'many'

# Events are keyed by the pair, not by the document number alone.
EVENT_KEY_FIELDS = ('document_number', 'sequence_number')
EVENT_SEQUENCE_LAYOUT = {'start': 13, 'length': 5}

# Fixed-width record geometry, stated to apply to both daily and quarterly
# files. Both lengths reconcile against their last field, which is a cheap
# check that the layout was transcribed correctly: 1437 + 4 - 1 = 1440 and
# 653 + 10 - 1 = 662.
RECORD_LENGTHS = {'data': 1440, 'event': 662}
FIELD_COUNTS = {'data': 79, 'event': 25}

# The data record carries at most six officers, with a flag at position 495
# when there are more. So officer evidence from this dataset is CAPPED, and the
# source separately warns that addresses and officers may be truncated or not
# current. Florida is the strongest officer source in the whole suite and it
# still cannot support "these are the officers" -- only "these are officers the
# register listed, as of this snapshot".
MAX_OFFICERS_IN_RECORD = 6
MORE_OFFICERS_FLAG_POSITION = 495

# Caveats the source states about its own data. Recorded because they bound
# what a finding may claim, and because a future reader should not have to
# re-derive them from a page behind a bot check.
SOURCE_CAVEATS = (
    'Addresses and officers may be truncated or may not be current.',
    'At most six officers appear in a record; a flag marks that more exist.',
    'Annual reports and address changes do not appear as events.',
    'No daily file is produced on a work day with no filings, so a missing '
    'date is an expected gap rather than a failed retrieval.',
    'Duplicate document numbers can legitimately occur, so rows must not be '
    'deduplicated on the document number alone.',
    'Malformed rows can occur, caused by special characters or line breaks '
    'embedded in the data.',
)

# What the date in a daily filename means, which is NOT what it looks like.
# It is the date the information was entered into the Sunbiz database -- not
# the filing date, not the effective date, not the date anything happened to
# the business. A parser treating `20261002c.txt` as "these filings occurred on
# 2 October" would date every record in it wrongly, and plausibly.
DAILY_FILENAME_DATE_MEANS = 'entered_into_database'
DAILY_FILENAME_DATE_IS_NOT = ('filing_date', 'effective_date', 'event_date')

# Row length is the parser's first and cheapest integrity check, and the one
# thing that must never degrade quietly: the source says malformed rows occur,
# and in a fixed-width layout a row one byte short shifts every later field and
# yields plausible nonsense instead of an error.
MALFORMED_ROW_POLICY = 'reject_explicitly'

# What is still NOT established, kept explicit so 5B resolves rather than
# assumes. Each is settled by one real artifact.
OPEN_UNKNOWNS = {
    'date_format': (
        'Date fields are 8 characters, but the definitions do not say whether '
        'they are MMDDYYYY or YYYYMMDD. Parsing the wrong one silently '
        'produces plausible, wrong dates rather than an error.'),
    'shard_names': (
        'The corporate quarterly data is split into 10 files by the trailing '
        'digit of the record number, but the page does not name them, and it '
        'says "ending in the number" without stating that the number is the '
        'document number. assess_coverage needs the real names to tell a '
        'complete release from a partial one.'),
    'delta_merge_semantics': (
        'Whether an amended entity reappears in a daily filings file as a full '
        'record is not stated, so how several rows for one document number '
        'combine into one business record is unverified. This is the open '
        'question that replaced the mistaken "assert uniqueness" rule.'),
    'corpus_generation': (
        'assess_coverage evaluates every snapshot it is given. Once historical '
        'snapshots accumulate, one old incomplete snapshot would hold coverage '
        'down forever even after a later complete release superseded it. '
        'Coverage has to be assessed against a GOVERNING generation -- the '
        'latest applicable snapshot plus its own deltas -- before production '
        'ingestion. Harmless today because nothing has been ingested.'),
    'delta_continuity': (
        'freshness() takes the maximum delta_through, which overstates '
        'freshness across a gap: with 1 and 3 October present and 2 October '
        'missing it would report the 3rd. Freshness should advance only '
        'through the latest CONTIGUOUS verified delta sequence after the '
        'governing snapshot. Shard completeness already gets this treatment '
        'for snapshots; deltas need the same.'),
}

# The dataset claim, as a quotation with its provenance. `verified` means the
# statement was actually retrieved from the source -- not that Zelda has
# confirmed the corpus is complete, which is what assess_coverage decides
# separately from an actual ingestion.
_DATASET_STATEMENTS = {
    DATASET_CORPORATE: {
        'source_url': 'https://dos.fl.gov/sunbiz/other-services/data-downloads/quarterly-data/',
        'definitions_url': 'https://dos.sunbiz.org/data-definitions/cor.html',
        'daily_url': 'https://dos.fl.gov/sunbiz/other-services/data-downloads/daily-data/',
        'quoted_claim': (
            'Quarterly files are generated in January, April, July and October '
            'and contain all data on record at the time the file is generated, '
            'so each release is a full snapshot rather than a delta. Corporate '
            'data covers corporations, limited liability companies and limited '
            'partnerships, and excludes trademarks. Daily files are generated '
            'on work days and contain filings added to the record that day; '
            'the filename date is the date the information was entered into '
            'the database.'),
        'verified': True,
        'retrieved_at': datetime.date(2026, 10, 2),
        # Recorded, because how a fact was obtained is part of the fact. The
        # Sunbiz pages return a Cloudflare bot-verification interstitial to this
        # project and defeating bot detection is out of bounds here, so the
        # operator read the pages directly. That is a weaker provenance than a
        # programmatic fetch and a re-check needs a human again.
        'verified_by': 'operator read the source pages directly',
    },
}


def dataset_statement(dataset_family):
    """The source's own claim about a dataset, with its provenance."""
    return dict(_DATASET_STATEMENTS[dataset_family])


@dataclasses.dataclass(frozen=True)
class IngestionProvenance:
    """
    One ingestion of one official artifact. Immutable by construction: a
    provenance record that could be edited after the fact would not be a chain
    of custody.
    """
    jurisdiction: str
    authority_source: str
    dataset_family: str
    artifact_type: str
    source_filename: str
    source_artifact_sha256: str
    downloaded_at: datetime.date
    records_ingested: int
    shards_expected: Tuple[str, ...]
    shards_parsed: Tuple[str, ...]
    parser_schema_version: int
    snapshot_as_of: Optional[datetime.date] = None
    delta_through: Optional[datetime.date] = None

    @property
    def shards_missing(self):
        return tuple(s for s in self.shards_expected if s not in self.shards_parsed)


def ingestion_identity(provenance):
    """
    What makes two ingestions the same one: the bytes.

    Not the filename -- Sunbiz filenames carry dates, and a rename must not
    produce a second ingestion of the same corpus.
    """
    return provenance.source_artifact_sha256 or None


def is_replay_of(existing, candidate):
    """
    Whether `candidate` re-ingests the artifact `existing` already covered.

    An artifact with no hash is never a replay. Treating two un-hashed
    artifacts as identical would silently skip the second, which is the
    opposite of idempotent.
    """
    left, right = ingestion_identity(existing), ingestion_identity(candidate)
    return bool(left) and bool(right) and left == right


def assess_coverage(ingestions, statement_verified=None):
    """
    (verdict, reason) for a jurisdiction's local dataset.

    'broad' has to be EARNED, and a row count does not earn it: a million rows
    from an incomplete set of shards is still incomplete. Every condition below
    is a way the corpus could be short without the ingestion having failed
    loudly.

    `statement_verified` is a parameter rather than a lookup so a caller can
    assess a hypothetical, and so the test suite can exercise the qualifying
    path that today's unverified Florida statement makes unreachable.
    """
    ingestions = list(ingestions or [])
    if not ingestions:
        return COVERAGE_UNMEASURED, 'No ingestion has been recorded.'

    snapshots = [i for i in ingestions if i.artifact_type == ARTIFACT_QUARTERLY_SNAPSHOT]
    if not snapshots:
        return COVERAGE_UNMEASURED, (
            'No quarterly snapshot has been ingested. A daily file is the '
            'filings added on one working day and establishes nothing about '
            'the breadth of the corpus.')

    for snapshot in snapshots:
        if not snapshot.source_artifact_sha256:
            return COVERAGE_UNMEASURED, (
                'A snapshot was ingested without recording its artifact hash, '
                'so the ingestion cannot be identified or replayed.')
        if snapshot.shards_missing:
            return COVERAGE_PARTIAL, (
                'Expected shard(s) %s were not parsed, so the corpus is '
                'incomplete.' % ', '.join(snapshot.shards_missing))
        if not snapshot.shards_expected:
            return COVERAGE_UNMEASURED, (
                'The snapshot recorded no expected shards, so completeness '
                'cannot be checked -- an empty expectation is trivially met.')

    if statement_verified is None:
        statement_verified = dataset_statement(
            snapshots[0].dataset_family).get('verified', False)
    if not statement_verified:
        return COVERAGE_UNMEASURED, (
            "The source's dataset statement is unverified, so what the corpus "
            'is meant to contain has not been established and breadth cannot '
            'be claimed against it.')

    return COVERAGE_BROAD, (
        'An official quarterly snapshot was ingested with every expected shard '
        'parsed, its artifact hash recorded, and the dataset statement '
        'verified.')


def freshness(ingestions):
    """
    (snapshot_as_of, delta_through) -- how current the mirror is.

    Separate from coverage by design. A quarter-old snapshot is broad and
    stale; reporting it as partial would claim its corpus was incomplete.

    KNOWN LIMITATION, recorded as OPEN_UNKNOWNS['delta_continuity']: this takes
    the maximum delta_through and so overstates freshness across a gap. With 1
    and 3 October ingested and 2 October missing it reports the 3rd, although
    the mirror is missing a day. Correct behaviour is to advance only through
    the latest contiguous verified sequence, which needs the delta lineage that
    5B/5C will establish. Harmless while nothing is ingested, and stated here
    rather than discovered later.
    """
    ingestions = list(ingestions or [])
    snapshot_dates = [i.snapshot_as_of for i in ingestions if i.snapshot_as_of]
    delta_dates = [i.delta_through for i in ingestions if i.delta_through]
    return (max(snapshot_dates) if snapshot_dates else None,
            max(delta_dates) if delta_dates else None)


def absence_is_meaningful(coverage, dataset_family, entity_family):
    """
    Whether "this business is not in the register" is a statement worth making.

    The governing rule, carried over from the Filed work: presence can be
    evidence where absence is not. Two conditions, both required -- the local
    corpus must be established as broad, and the thing being looked for must
    lie inside that corpus. A trademark missing from a corporate snapshot is
    not evidence; the snapshot never held trademarks.
    """
    if coverage != COVERAGE_BROAD:
        return False
    return entity_family in SCOPED_ENTITY_FAMILIES.get(dataset_family, ())
