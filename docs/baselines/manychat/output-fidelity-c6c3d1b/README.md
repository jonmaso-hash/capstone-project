# ManyChat Pass A at `c6c3d1b` (after PR #288): post-merge live validation for RA-109

**Additive evidence.** It edits no frozen key, protocol, historical ledger, grade, fixture, earlier memo (including memo 102) or earlier evidence. The run's record and my provisional readings are in [pass-a/RERUN_LEDGER.md](pass-a/RERUN_LEDGER.md), whose Part 1 (execution) and Part 2 (assessment) are kept separate. **RA-109 acceptance remains pending independent review**; this run does not declare it.

| Item | Value |
|---|---|
| Execution SHA | `c6c3d1b9b1fe8b5e32d856c64a5b535a986684a0` (merge of PR #288; tree identical to the reviewed head `d9f3ac7`; `origin/main` was exactly `c6c3d1b` when fetched). One code state; no application, prompt, guard, fixture or test change |
| Tests on the merged code | 238 + 77 + 67 = **382 OK**; `check` and `makemigrations --check --dry-run` exit 0 |
| Branch | `docs/manychat-output-fidelity-c6c3d1b`, evidence only, unmerged |
| Deck | SHA-256 `be7a7171bbc84b9895a45adfbc41f2533f3d23b3a4a561c82a8d9de6b94f3ef1`, verified, uploaded once |
| New rows | Document **3145**; chunks 12; insights 5201–5204; claims **2389–2392**; Entity Integrity **44**; Truth Delta **97**; memo **103** |
| Model calls | **8:** 1 memo generation (`msg_011CgL4BQwx1J4Q5cxbHKjGo`) and 7 `/ask/` (Q1–Q7, once). No retry, no failure |
| Isolation | SQLite backup copy of the dev DB, migrated and sequence-advanced in the copy only. Local Memurai dbs 1/6 (no empty db existed; D-8). Six paid keys blank and `pending=0` inside server and worker. Memos 90/91 and 94–102 byte-identical before and after. Memory watchdog running throughout |
| Browser | **Gate passed, walks completed.** "Browser 1" failed four loopback probes (another machine; D-10). Chrome "Browser 2" on this computer showed a fresh loopback nonce with the request in the server log, then loaded the run server before any model call. Owner, Lite, paid, staff (real TOTP) and anonymous walks done, with screenshots |

## Result (provisional, pending independent review)

- **Observed failure: OF-1102 (OF-1003 / OF-904 class), provisional P2, blocking.** `base_scenario`: "Taking the self-reported traction at face value without independent verification [S1, S2, S3], the company had deployed a meaningful bot platform by the period referenced in the 'Traction by Apr-16' slide context, with Pitch Deck Hunt listing $23.1M in prior funding [C1, S4]." Page 12's S3 is dated by page 10's period. The merged guard did not edit it. A read-only replay shows the guard corrects memo 101's and memo 102's graded sentences, but not this wording: either the hedge "without independent verification" or the trailing funding clause keeps `basis_source_context` from reading it.
- **Open for the grader: OF-1103 (Q-1).** `upside_scenario` places [S3]'s monthly figure "at the time of the 'Traction by Apr-16' slide" under a condition about accuracy and basis, not about the date. My reading: the same class.
- **Pass: OF-1004.** All 39 citation brackets resolve, and each figure's group names its own claim and statement; page 12's figure is cited [C2/S3] or [S3], never with C3.
- **Pass:**
  - **Did not recur:** OF-905, OF-906, OF-807.
  - **Also held:** separation elsewhere; no annualisation; clarification sought; interval wording; funding attributed on every surface; historical framing; no platform counts, identity or advice; Truth Delta and Entity Integrity states; the 90-row matrix (identical to memo 102's); owner-only reconciliation; canary boundaries; UTF-8 Markdown; **all five browser walks**.
- **P3 / questions:**
  - "total vs. per month" for page 10 (Q-2);
  - "how much of the narrated $23.1M raised … remains available" (OF-909 class);
  - "the company has sought to characterise a meaningful prior capital history" after Pitch Deck Hunt's listing (Q-3);
  - "The verification pass identified …" (RA-108 recurrence, OF-910 class);
  - hedged product-category inferences (Q-4).
- **RA-114:** `/ask/` still returns the marketplace fallback for all seven questions.

## Status

- **Not accepted:** this sample does not meet the RA-109 output criteria (OF-1102). RA-109 acceptance is pending independent review.
- **Still open:** RA-108, RA-114 and overall hardening. No deployment, paid-source Pass B or other deck was run.
