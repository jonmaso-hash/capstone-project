# Review of the bounded location restatement at `d76237d` / `191e627` (changes required)

**Separate, additive record.** It edits no earlier evidence, grade, memo, ledger or frozen fixture.

| Item | Value |
|---|---|
| Decision | **Changes required.** Keep `fix/basis-label-source-context` unmerged |
| Application head | `d76237d` |
| Evidence commit | `191e627` |
| Independent execution | All 93 non-database tests passed. The 58/58 mutations and 1,389 batch tests were not independently rerun |

## Corrected (per the reviewer)

The earlier funding, revenue and negation probes now behave correctly.

## New finding

### P2: the location repair deletes unrelated information inside parentheses

Through normalisation → time → funding → basis on the actual memo-99 payload:

| Input | Output at `d76237d` |
|---|---|
| "The company states the message figures (revenue is $10M) on the same slide [S2, S3]." | The two message facts are restated on their own pages; "revenue is $10M" disappears |

**Cause:** `_placing_words()` removes parenthetical text before checking whether reconstruction is safe, and the reconstruction then discards that text.

## Required

1. Add this exact failing regression, with full guard-sequence coverage.
2. Preserve parenthetical facts and qualifications; when they cannot be safely classified, leave the sentence unchanged.
3. Keep the existing positive control for "(500M, 500M/month)" and all accepted memo repairs.
4. Add a mutation for this boundary, rerun affected validation, and push separate application and additive evidence commits.

RA-109 live acceptance, RA-108 and overall hardening remain open.
