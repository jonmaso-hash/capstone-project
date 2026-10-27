# The inherited base procedure (`1aab9e3`) and how revisions 1 and 2 relate to it

## Where it is, durably

| | |
|---|---|
| File | `docs/baselines/three-deck-audit/output-f1-f2-post-merge-b278364/NEXT_LIVE_VALIDATION.md` |
| Commit | `1aab9e345af13dc79c69680a373f50f2c5c32c04` ("Record the post-merge verification of PR #290 at b278364") |
| On main? | **No.** Only on `origin/docs/post-merge-verification-b278364` |
| **Durable reference** | annotated tag **`ra114/base-live-procedure-1aab9e3`** (tag object `da77276…`), pushed to origin, pointing at `1aab9e3`. It keeps the commit reachable if the branch is deleted |
| Verbatim copy | `inherited/NEXT_LIVE_VALIDATION_1aab9e3.md`, sha256 `ec3dadc6c4e08ca6b78d4f44a5598a8c139f62c6c77c60f0d415c3d93bf01fda`, equal to the blob at `1aab9e3` |

The copy is a preservation copy, not a new revision. The tagged commit stays authoritative. If this folder merges, the procedure also becomes reachable from main.

## How the three documents stack

| Layer | File (commit) | What it adds or changes |
|---|---|---|
| **Base** | `1aab9e3` | preconditions 1–7 (go-ahead, code SHA, tests, isolation, memory, browser gate, accounts); steps 1–7; the 8-call budget, no retries, ledger; integrity, F-1, F-2 (with **"not exercised"**), regressions; RA-108, RA-114 and Q-2–Q-4 recorded, not decided |
| **Revision 1** | `6917e84` (`output-ra114-ask-document-e4d17d7/NEXT_LIVE_VALIDATION_REV_RA114.md`) | RA-114 becomes decided: Q1–Q7 asked twice (document form 0 calls, marketplace form 7 calls); criteria 1–7; authorization probe (Lite, paid, unrelated investor); per-question grounding table; ledger checkpoints around the document form |
| **Revision 2** | `8d08fe5` (`output-ra114-ranking-panel-9ee8d3d/NEXT_LIVE_VALIDATION_REV2_RA114.md`) | new offline prediction (ranking changed); unrelated-question control; panel document check, with checkpoints around it; the marketplace panel form is not sent live |
| **This runbook** | this folder | *how* to execute revision 2: manual sign-in, in-browser probe, temporary Memurai, code-enforced gate, unrelated-investor fixture. **No criterion is changed** |

Each revision says "everything not changed here still applies". Read bottom-up, a requirement holds unless a higher layer changes it. No layer loosens a criterion.

## Inherited requirements the runbook had to change in method, and why

1. **Preconditions 4 and 7, and steps 3 and 5.** The base's tooling (`f73bef5`) read `pw.txt` and TOTP files. The runbook removes every credential-file read: sign-ins are manual, and staff MFA is completed by hand.
2. **Precondition 4: "new, unused Memurai dbs".** That can't be met on the installed instance (all 16 dbs hold keys, per `99c92ea`). A separate temporary instance meets its intent.
3. **"No retries."** Now enforced against the SDK's own retries too. The background default is 2.
