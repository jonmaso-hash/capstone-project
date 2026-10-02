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

# What 'corporate data' covers, kept narrow on purpose. Sunbiz publishes other
# datasets (trademarks among them) that this one does not include, and a
# fictitious name or a sole proprietorship is not in it either. Inheriting
# corporate coverage for those would claim evidence about a corpus that was
# never ingested.
SCOPED_ENTITY_FAMILIES = {
    DATASET_CORPORATE: ('corporation', 'limited_liability_company',
                        'limited_partnership'),
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

# NOT DECIDED. See the module docstring: the field definitions decide this.
ENTITY_KEY_FIELD = None

# The dataset claim, as a quotation rather than as a fact. `verified` flips
# only when the statement has actually been retrieved from the source, and
# `retrieved_at` records when.
_DATASET_STATEMENTS = {
    DATASET_CORPORATE: {
        'source_url': 'https://dos.fl.gov/sunbiz/other-services/data-downloads/quarterly-data/',
        'quoted_claim': (
            'Reported as: quarterly files are generated in January, April, July '
            'and October and contain all data on record at the time the file is '
            'generated; corporate data covers corporations, limited liability '
            'companies and limited partnerships.'),
        'verified': False,
        'retrieved_at': None,
        'why_unverified': (
            'The Sunbiz download pages return a Cloudflare bot-verification '
            'interstitial to this project, and defeating bot detection is out '
            'of bounds here. The claim is second-hand until the page or the '
            'field definitions are supplied directly.'),
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
