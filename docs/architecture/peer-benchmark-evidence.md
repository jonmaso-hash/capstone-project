# External peer figure provenance (P-2)

External discovery remains available, but a bare model-returned number and a
report-wide source list cannot establish a numeric comparison. Each displayed
figure now carries its exact citation passage, source URL/title, unit,
measurement basis and measurement date or annual period end. The passage must
come from an actual citation returned by the web-search provider, name the
company and contain one unambiguous unit-bound amount/count matching the
extracted value. Every excerpt for a source URL is retained.

This is **source-linked extraction, not independent verification**. It does not
prove that the source is accurate, independently resolve every external legal
entity, or eliminate all semantic extraction errors. The source passage is
visible so readers can inspect the attribution. Ambiguous passages, unsafe
URLs, absent citations, fabricated quotes and non-finite numbers are rejected.

Only figures with a supported unit/basis and a date documented in that passage
enter calculations. Unknown metadata is never inferred from the retrieval date
or a year label. A bare dollar sign does not establish USD. Supported currencies
are declared in `peer_benchmark_evidence.CURRENCY_WORDS`; unsupported currencies
remain excluded, without FX conversion. Monetary amounts are in major currency
units. Counts must be integers; negative reported EBITDA and explicit zeros are
valid observations.

Comparisons are separate for each exact unit, measurement basis, measurement
date or annual reporting-period end. Every group is shown, with its own sample
count. A median needs at least three distinct companies. This is a descriptive
sample-size rule, not the Interlink five-contributor privacy rule or a claim of
market representativeness. Duplicate company names/normalised legal suffixes
count once; conflicting complete observations exclude that company for the
metric rather than silently picking one. Aliases that cannot be recognised by
this conservative name normalisation are a remaining identity limitation.

The metric definitions are explicit:

- Cumulative total equity funding and cumulative total funding are separate
  bases. Current fundraising targets and completed equity rounds are separate
  metrics; the owner's current target is never its completed round.
- Asking prices and completed transaction values are separate metrics.
  Enterprise value, equity value and asset-sale price are separate bases.
- Annual reported revenue does not admit ARR, TTM or recurring run-rates.
  Annual reported EBITDA does not admit adjusted EBITDA.
- Employee counts do not admit LinkedIn-associated profiles. Years in business
  require a sourced count and measurement date; no founding-date arithmetic is
  silently substituted.

An owner percentile additionally needs an explicitly recorded compatible unit,
basis and dates. Current profiles have no currency fields and do not capture
all these bases, so their unqualified figures do not acquire a currency or
period merely by being displayed. Their recorded values remain visible to the
owner, and only under current public permissions on share pages. A future
profile-data change can populate `subject_snapshot.metric_bases`; this PR does
not add those form/model fields or treat missing metadata as known.

Generation freezes the admitted peer facts and source excerpts in existing JSON
fields. Rendering rebuilds calculations from those frozen inputs instead of
trusting stored aggregate numbers. Model-generated comparison prose is replaced
with a deterministic count/gap summary. Legacy external calculations and model
prose are withheld on both pages; identifiable peer discovery and safe source
links remain available. Legacy own targets/prices retain their actual meaning.
Nothing rewrites an old report, reruns paid research or changes the refresh
allowance. The Interlink refresh command and internal privacy rules are intact.

Public rendering applies the existing P-1 subject/cohort rules to every new
group and figure. Revocation masks owner values and percentiles throughout.
When supplied subject fields are private, per-figure citation excerpts are
withheld alongside the report-wide excerpts. Private cohort fields hide the
external peer set and sources entirely.

The regression module is included in blocking CI. It covers admission failure,
valid controls, unit/basis/date separation, duplicate/conflicting companies,
source preservation, semantic metric separation, deterministic narrative,
legacy safety, frozen evidence recalculation and both views' privacy behavior.
