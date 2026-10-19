# Review of the parenthetical-aside correction at `ed29f3b` / `b38bb22` (changes required)

**Separate, additive record.** It edits no earlier evidence, grade, memo, ledger or frozen fixture.

| Item | Value |
|---|---|
| Decision | **Changes required.** Keep `fix/basis-label-source-context` unmerged |
| Application head | `ed29f3b` |
| Evidence commit | `b38bb22` |
| Independent execution | The reviewer reproduced the finding with the actual guard and constructed source facts. The recorded 60/60 mutations and 1,392 batch tests were not independently rerun |

## New finding

### The location repair deletes an additional figure inside parentheses

| Input | Output at `ed29f3b` |
|---|---|
| "The company states the message figures (250M messages/month) on the same slide [S2, S3]." | Restated from the two 500M source figures; "250M messages/month" disappears. A nested version loses it too |

**Cause:** `_plain_words()` accepts every token beginning with a digit or `$`. It checks the vocabulary without establishing whether the parenthetical holds an additional figure.

## Required

1. Add this exact regression through the full guard sequence, plus the nested case.
2. Preserve additional figures; leave uncertain sentences unchanged.
3. Keep the accepted "(500M, 500M/month)" control and the memo repairs.
4. Add a mutation for this boundary, rerun affected validation, and push separate application and additive evidence commits.

RA-109 live acceptance, RA-108 and overall hardening remain open.
