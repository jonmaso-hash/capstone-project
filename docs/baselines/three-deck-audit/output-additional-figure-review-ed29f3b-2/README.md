# Second review of the parenthetical-aside correction at `ed29f3b` (changes required)

**Separate, additive record.** It edits no earlier evidence, grade, memo, ledger or frozen fixture. This is a second review of `ed29f3b`, received after `bcf9e0a` / `aa42a62` (the response to the first review of `ed29f3b`) had been pushed.

| Item | Value |
|---|---|
| Decision | **Changes required.** Keep `fix/basis-label-source-context` unmerged |
| Application head reviewed | `ed29f3b` |
| Independent execution | The reviewer reproduced the finding. The recorded 60/60 mutations and 1,392 batch tests were not independently rerun |

## Finding

| Input | Output at `ed29f3b` |
|---|---|
| "The company states the message figures (600M messages) on the same slide [S2, S3]." | "600M messages" is deleted and the clause replaced with the cited 500M figures |
| "… (500M, 600M/month) …" and nested "… (500M (600M)) …" | Also lost |

**Cause:** `_plain_words()` accepts every numeric token without checking whether the cited facts support it.

## Required

- Add these regressions, including full guard-sequence coverage.
- Preserve unknown numbers, arithmetic and unclassified nested parentheses.
- Keep the accepted "(500M, 500M/month)" repair and the memo replays.
- Add a mutation for numeric validation, rerun the affected checks, and push separate application and evidence commits.

RA-109 live acceptance, RA-108 and overall hardening remain open.
