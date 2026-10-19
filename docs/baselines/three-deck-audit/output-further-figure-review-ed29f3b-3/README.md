# Third review of the parenthetical-aside correction at `ed29f3b` (changes required)

**Separate, additive record.** It edits no earlier evidence, grade, memo, ledger or frozen fixture. This review of `ed29f3b` was received after `2465791` / `825d6c0` had been pushed.

| Item | Value |
|---|---|
| Decision | **Changes required.** Keep `fix/basis-label-source-context` unmerged |
| Application head reviewed | `ed29f3b` |
| Independent execution | The reviewer reproduced the finding. The recorded 60/60 mutations and 1,392 batch tests were not independently rerun |

## Finding

| Input | Output at `ed29f3b` |
|---|---|
| "The company states the message figures (700M messages) on the same slide [S2, S3]." | "700M messages" is deleted and the clause restated from the cited 500M figures |

**Cause:** `_plain_words()` accepts every numeric token without checking whether the cited facts contain that number.

## Required

- Preserve the sentence when a parenthetical contains an additional or unclassified figure.
- Add regressions for "(700M messages)" and "(500M, 500M/month, 700M)", with full guard-sequence coverage.
- Keep the accepted "(500M, 500M/month)" positive control and the memo repairs.
- Add a mutation for this boundary, rerun the affected validation, and push separate application and additive evidence commits.

RA-109 live acceptance, RA-108 and overall hardening remain open.

## Where it stood

Both inputs already kept their sentence at `bcf9e0a` and at `2465791`. The regression and mutation P32 were added in `d4c2ba8`. The review of `2465791` arrived while that validation was paused, so both were validated together at `9d24d97`: see [`../output-figure-form-9d24d97/`](../output-figure-form-9d24d97/README.md).
