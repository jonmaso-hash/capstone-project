# Review of the arithmetic/nesting correction at `2465791` (changes required)

**Separate, additive record.** It edits no earlier evidence, grade, memo, ledger or frozen fixture.

| Item | Value |
|---|---|
| Decision | **Changes required.** Keep `fix/basis-label-source-context` unmerged: one data-loss blocker remains |
| Application head reviewed | `2465791` |
| Confirmed fixed | "(700M messages)" and "(500M, 500M/month, 700M)" keep the sentence; the accepted "(500M, 500M/month)" control still repairs |
| Independent execution | Reproduced through the full guard sequence on memo 99's payload. The recorded 69/69 mutations and 1,395 batch tests were not independently rerun, and they miss this boundary |

## Finding

| Input aside | Result at `2465791` |
|---|---|
| "(500M+)" | The "+" qualification is dropped |
| "(500M+/month)" | The "+" qualification is dropped |
| "(500M/messages)" | The unsupported denominator is dropped |

**Cause:** `_figure_key()` discards the "+", and a slash suffix passes whenever its words appear in the general vocabulary. Neither proves that the complete figure matches an admitted statement.

## Required

- Keep the sentence unless the complete figure, its qualification and its denominator are supported.
- Add full-sequence regressions and boundary mutations.
- Keep the existing positive controls and memo repairs.
- Rerun validation and push separate application and evidence commits.

RA-109 live acceptance, RA-108 and overall hardening remain open.

Addressed at `9d24d97`: see [`../output-figure-form-9d24d97/`](../output-figure-form-9d24d97/README.md).
