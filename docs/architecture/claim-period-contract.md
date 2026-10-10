# Claim period and comparison contract (td.5)

Frozen before implementation on main `b0fac5e`, 2026-10-10, in commit
`8b031fc`. Expectations live in `zelda_api/data/claim_periods/expectations.json`,
with two recorded EDGAR company-facts subsets beside them. This is the period
part of claim-extraction PR 2, after attribution (#265) and currency (#266).

## Why this is an admission gate

Before td.5 no claim carried a period, so every disagreement ended as
`period_unknown` and `contradicted` was unreachable. A period on the claim is
what lets a gap become a contradiction, so the comparison rule was defined and
its failure edges frozen before any period reached a claim.

## The claim side

`zelda_api/claim_periods.py` reads the claim's **own sentence only**. A slide
heading on another line ("Traction by Apr-16") never attaches; joining lines is
what would expose a platform's user counts to the claim layer.

Kinds: `annual`, `quarterly`, `monthly`, `ttm`, `run_rate`, `cumulative`.
A fiscal-year label ("FY2024", "fiscal 2025") gives a fiscal year and **never**
an end date. An explicit "year ended May 31, 2026" gives an end date. A bare
year ("a 2015 Series A deck", "founded in 1978") is not a period. Two
conflicting bases in one sentence leave the period unknown. "Per month" is a
monthly basis without a date. The raw phrase is kept in `time_period`.

## The observed side

SEC revenue is chosen only from 10-K facts covering a full fiscal year
(350-380 days). A 10-K can also tag a 90-day Q4 ending on the same day as the
year; with Apple's recorded FY2020 rows listed quarter-first, the previous
selection picked the quarter. Not reproduced as SEC serves them today (list
order saved it), so this ships as a guard rather than a separate fix.

The observed fiscal year is the **filer's own label**: the lowest `fy` among
10-K rows for exactly that period, because a restated prior year carries the
later filing's `fy` (Nike's FY2025 also appears with fy 2026).

## Comparison

| Claim | Evidence | Result |
|---|---|---|
| no usable period | any | today's rule: agreement verifies; a gap is `period_unknown` |
| a kind | a different kind | `period_mismatch`: blocks verified **and** contradicted |
| annual, same fiscal-year label or exact end date | annual | comparable: agreement verifies, a gap may be contradicted |
| annual, different label or end date | annual | `period_mismatch` |
| annual, end date within 7 days but not exact | annual | `period_unresolved`: agreement verifies, a gap does not contradict |
| annual, no label or date | annual | `period_unresolved` |

A fiscal year is never compared with an end date. Nike's answer key C01
("FY2026 revenue $52.8B" against $46,398M for the year ending 2026-05-31,
filer label FY2026) is the frozen path to `contradicted`.

## Historical reports

`TRUTH_DELTA_SEMANTICS` is `td.5`. Reports stamped `td.4` or earlier keep the
rule they were produced under; nothing is rewritten. Claims and observations
stored before td.5 have no structured period and are never backfilled.

## Not in scope

Cross-line period attachment; quarterly or monthly evidence (SEC supplies
annual revenue only); headcount periods (point-in-time); FX conversion and
annualisation (never).
