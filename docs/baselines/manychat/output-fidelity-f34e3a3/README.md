# ManyChat Pass A at `f34e3a3` (after PR #285): evidence for RA-109 live-output review

**Additive evidence for independent grading.** It edits no frozen key, protocol, historical ledger, grade, fixture, earlier memo or earlier evidence. The run's readings are in [pass-a/RERUN_LEDGER.md](pass-a/RERUN_LEDGER.md); they are not grades.

| Item | Value |
|---|---|
| Execution SHA | `f34e3a399349a2d7401f66d9b60b10834047e57a` (merge of PR #285; tree identical to 2bd9056). One code state throughout; no application change |
| Branch | `docs/manychat-output-fidelity-f34e3a3`, evidence only, unmerged |
| Deck | SHA-256 `be7a7171bbc84b9895a45adfbc41f2533f3d23b3a4a561c82a8d9de6b94f3ef1`, verified, uploaded once |
| New rows | Document **3142**; chunks 12; insights 5189–5192; claims **2377–2380**; Entity Integrity **41**; Truth Delta **94**; memo **100** |
| Model calls | **1 memo generation** (`msg_011CgAjqEXx9w6jVYHFirADz`) + **7 `/ask/`** (second Q1–Q7 attempt) = 8 successful; plus 5 calls rejected for the Anthropic credit balance in the first Q1–Q7 attempt |
| Isolation | SQLite backup copy of the dev DB (migrated and sequence-advanced in the copy only); local Memurai db 4/12; six paid keys blank and `pending=0` inside server and worker; memos 90/91 and 94–99 byte-identical before and after |

## What to look at

1. **Raw vs persisted:** [pass-a/09b_model_call.json](pass-a/09b_model_call.json) (the exact request and the model's own reply), [pass-a/09e_guard_changes.txt](pass-a/09e_guard_changes.txt) (every guard edit), [pass-a/09_memo.json](pass-a/09_memo.json) (stored memo 100), [pass-a/09d_memo_input_output_check.json](pass-a/09d_memo_input_output_check.json) (four-step replay, all 15 fields equal).
2. **Measurement basis:** the raw reply's "If the cumulative figure was restated as a monthly figure, … materially overstated" and "Contradictory … measurement bases" were **corrected live** by the merged basis guard. For grading: `business_model_analysis` "500M messages [S2, S3] … (in a slide context headed 'Traction by Apr-16')" (OF-805) and `open_concerns` "one or both figures may misrepresent the scale of actual activity" (OF-806), both uncorrected.
3. **Surfaces:** [pass-a/11_authorization_matrix.json](pass-a/11_authorization_matrix.json) (90 rows, identical to memo 99's run), [pass-a/15_browser_walks.json](pass-a/15_browser_walks.json) and [pass-a/browser/](pass-a/browser/) (owner, Lite, paid, staff with real MFA, anonymous).
4. **Ask Zelda:** [pass-a/10_retrieval_ask_q1_q7.json](pass-a/10_retrieval_ask_q1_q7.json) (first attempt: billing failure) and [pass-a/10b_retrieval_ask_q1_q7_second_attempt.json](pass-a/10b_retrieval_ask_q1_q7_second_attempt.json) (one second attempt after the owner reloaded credits).

## Blockers and unresolved questions

- **Anthropic credit balance (resolved during the run):** the first Q1–Q7 attempt failed (500 ×5 with API 400 "credit balance is too low", then 503 ×2). The owner reloaded credits; one recorded second attempt succeeded. The memo generation had already completed before the failure.
- **Chrome reachability (resolved during the run):** the connected browser first got "connection refused" on the run server; after the owner re-selected the browser, all five walks ran.
- **Open for the grader:** whether OF-805 (a page-12 source cited under the page-10 context, in wording the location rule does not cover) and OF-806 (an unresolved "may misrepresent" judgment) keep RA-109 open.

**RA-109 live acceptance is pending independent grading. RA-108 and overall hardening remain open.** No deployment, paid-source Pass B, other deck, mutation run or application change.
