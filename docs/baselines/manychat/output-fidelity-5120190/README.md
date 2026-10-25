# ManyChat Pass A at `5120190` (after PR #289): post-merge live validation for RA-109

**Additive evidence.** This folder changes nothing that already exists: no frozen key, protocol, earlier ledger, grade, fixture, earlier memo (including memo 103) or earlier evidence.
- **Where the record is:** the run's record and my provisional readings are in [pass-a/RERUN_LEDGER.md](pass-a/RERUN_LEDGER.md). Part 1 (execution) and Part 2 (assessment) are kept separate.
- **What stays open:** **RA-108, RA-109, RA-114, Q-2–Q-4 and overall acceptance remain open.** This run declares none of them.
- **Credentials:** no password, TOTP secret, setup key, recovery code, session cookie or API key is recorded here.

| Item | Value |
|---|---|
| Execution SHA | `5120190ce47708e99cff5b417baf2c565059cf7f` (merge of PR #289). One code state; no application change during the run |
| Tests | 259 + 77 + 67 = **403 OK**; `check` and `makemigrations --check --dry-run` exit 0 |
| Branch | `docs/manychat-output-fidelity-5120190`, evidence only, unmerged |
| Deck | SHA-256 `be7a7171bbc84b9895a45adfbc41f2533f3d23b3a4a561c82a8d9de6b94f3ef1`, uploaded once |
| New rows | Document **3146**; claims 2393–2396; Entity Integrity 45; Truth Delta 98; memo **104** |
| Model calls | **8:** 1 memo (`msg_011CgMuwRh2dFNCNMdNSAs2z`) and 7 `/ask/` (Q1–Q7, once). No retry, no failure |
| Isolation | SQLite copy of the dev DB; Memurai dbs 8/9; paid keys blank; the original DB and memos 94–103 byte-identical before and after |
| Browser | Gate passed on Chrome `b60b1997` before any model call, and again after the restart. Two failed attempts on `203c1a8f` are preserved. **Anonymous, owner, Lite, paid and staff checks completed by manual sign-in; none left unrun** |

## Result (provisional, pending independent review)

- **F-1, provisional P2: funding-guard word split.**
  - **Raw reply:** "the $23.1M reportedly raised [S4]".
  - **Stored and rendered to staff:** "the $23.1M reported (per Pitch Deck Hunt)ly raised [S4]".
  - **Cause:** `_FIGURE_TAIL` in `zelda_api/funding_fidelity.py:100` matches "reported" inside "reportedly" because there is no word boundary.
  - **Reproduced** read-only and idempotently ([assessment/repro_reportedly.json](pass-a/assessment/repro_reportedly.json)). PR #289 did not touch this rule.
- **F-2, for the grader: possible OF-1003 class.**
  - **The sentence:** `business_model_analysis` puts the page-10 heading 'Traction by Apr-16' over [S2, S3]. S3 is page 12's "500M messages/month", which has no context.
  - **What it doesn't do:** no date is asserted ("undated as counts"), and the guard leaves it unchanged.
  - **Evidence:** the full sentence, S1/S2/S3 source text, page boundaries and replay are in [assessment/heading_concern.json](pass-a/assessment/heading_concern.json).
- **OF-1102 / OF-1103 did not recur.** Neither base nor upside dates page 12's figure. A read-only replay of memo 103's graded sentences through the merged guards corrects both, and the five controls (denial, unrelated consequence, unknown trailing clause, date as hypothesis, qualifier and attribution without a heading) stay unchanged.
- **Held:**
  - verification qualifiers and funding attribution on every surface;
  - historical dates;
  - all 35 citation brackets resolve;
  - the 90-row matrix is identical to memo 103's;
  - canaries absent; reconciliation owner-only; UTF-8 Markdown;
  - all five browser checks.
- **Open:**
  - RA-114: `/ask/` returns the marketplace fallback for all seven questions;
  - RA-108: "The verification process identified …";
  - P3 wording for Q-2–Q-4.

## Interruptions and repairs (details in the ledger, Deviations)

- **Low-memory shutdown.** Claude Code stopped the server, worker and watchdog at 0.97 GB free.
  - Data was verified intact read-only.
  - The restart happened only once free RAM held at **1.2 GB or more**: watchdog first, then the server only. The worker stayed stopped.
  - The browser gate was re-run.
- **Two sign-ins landed on the wrong account,** both from Chrome autofill. They were identified, signed out and not counted.
- **Staff test-account setup repair.** The probe-created MFA enrollment couldn't be used by the owner.
  - It was reset with the app's own `reset_staff_mfa` command, for that one account, on the copy.
  - The owner then re-enrolled through the normal page.
  - The MFA requirement and all other accounts were unchanged.

## Status

- **Not proposed for acceptance** (F-1; F-2 open).
- **Still open:** RA-108, RA-109, RA-114, Q-2–Q-4 and overall hardening.
- **Not done:** no merge or deployment.
