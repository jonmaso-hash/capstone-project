# ManyChat Pass A at `d0bad8f` (after PR #287): live sample for RA-109 output review

**Additive evidence.** It edits no frozen key, protocol, historical ledger, grade, fixture, earlier memo (including memo 101) or earlier evidence. The run's readings and grades are in [pass-a/RERUN_LEDGER.md](pass-a/RERUN_LEDGER.md). **RA-109 acceptance remains pending independent review of this live evidence**; replay evidence alone is not acceptance.

| Item | Value |
|---|---|
| Execution SHA | `d0bad8fdaace39f2f64be9f576874da9b0bf5e7a` (merge of PR #287; tree identical to `44af018`; `origin/main` had no newer commits). One code state; no application or test change |
| Tests on the merged code | 199 + 77 + 67 = **343 OK**; `check` and `makemigrations --check --dry-run` exit 0 |
| Branch | `docs/manychat-output-fidelity-d0bad8f`, evidence only, unmerged |
| Deck | SHA-256 `be7a7171bbc84b9895a45adfbc41f2533f3d23b3a4a561c82a8d9de6b94f3ef1`, verified, uploaded once |
| New rows | Document **3144**; chunks 12; insights 5197–5200; claims **2385–2388**; Entity Integrity **43**; Truth Delta **96**; memo **102** |
| Model calls | **8:** 1 memo generation (`msg_011CgGuZmFdgsGm76mWcyKAZ`) and 7 `/ask/` (Q1–Q7, once). No retry, no failure |
| Isolation | SQLite backup copy of the dev DB, migrated and sequence-advanced in the copy only. Local Memurai db 1/4 (no empty db existed; see D-8). Six paid keys blank and `pending=0` inside server and worker. Memos 90/91 and 94–101 byte-identical before and after. Memory watchdog running throughout |
| Browser | **Chrome walks BLOCKED (D-9).** The connected browser got `ERR_CONNECTION_REFUSED` for `127.0.0.1:8000` and `localhost:8000`, while local HTTP returned 200 and no browser request reached the server log. Root cause not established; HTTP-fetched pages are not counted as browser validation |

## Result

The merged guards made **no basis edit** on this reply; the stored memo equals the model's reply except one funding narrator insertion.

- **Pass:**
  - **Did not recur:** OF-905 (no judgment wording anywhere), OF-906 (no presupposed cumulative), OF-907 and OF-807.
  - **Also held:** no annualisation; clarification sought; interval wording; funding attributed in 44/44 sentences; historical framing; no platform counts, identity or advice. Truth Delta and Entity Integrity states, the 90-row matrix (identical to memo 101's), owner-only reconciliation, canary boundaries and UTF-8 Markdown hold (HTTP).
- **Fail (provisional P2):**
  - **OF-1003 (OF-904 class):** `base_scenario` says "If the traction figures [S1, S2, S3] are taken at face value under the 'Traction by Apr-16' framing, ManyChat had reached meaningful platform scale at that point in time." This places page 12's monthly source under page 10's context. The condition is only about face value, so the run reads it as violating the criterion (Q-1 for the grader).
  - **OF-1004 (citation identity):** page 12's "500M messages/month" is cited `[C3, S3]` in `open_concerns` and in `business_model_analysis`. C3 is page 10's claim (2387); page 12's is C2 (2386).
- **P3:** OF-1008 ("capital deployed or remaining reserves", OF-909 class); OF-1009 ("internally inconsistent", "conflicting bases", "the same 500M messages figure", "which is correct", "see consistency note", and "The verification pass surfaced …" (RA-108); OF-910 class).
- **Open grading questions:** Q-1 (OF-1003 conditional), Q-2 (OF-1004 severity), Q-3 (OF-1005: S3 in the parenthesis before page 10's context).
- **RA-114:** `/ask/` still returns the marketplace fallback for all seven questions.

## Status

- **Defects for review, not fixed here:** OF-1003 and OF-1004 are shapes no merged rule reads:
  - a face-value condition carrying another page's context;
  - a wrong claim ref inside a citation group.
- **Blocked:** the Chrome walks (OF-1015).
- **Open:** RA-109 acceptance pending independent review; RA-108, RA-114 and overall hardening remain open. No deployment, paid-source Pass B or other deck was run.
