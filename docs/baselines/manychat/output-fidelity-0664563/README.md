# ManyChat Pass A at `0664563` (after PR #286): live sample for RA-109 output review

**Additive evidence.** It edits no frozen key, protocol, historical ledger, grade, fixture, earlier memo (including memo 100) or earlier evidence. The run's readings and grades are in [pass-a/RERUN_LEDGER.md](pass-a/RERUN_LEDGER.md). **RA-109 acceptance remains pending independent review of this live evidence**; replay evidence alone is not acceptance.

| Item | Value |
|---|---|
| Execution SHA | `066456341935d5ace32760a00788f78ec61a047a` (merge of PR #286; tree identical to `5937e51`; `origin/main` had no newer commits). One code state; no application change |
| Branch | `docs/manychat-output-fidelity-0664563`, evidence only, unmerged |
| Deck | SHA-256 `be7a7171bbc84b9895a45adfbc41f2533f3d23b3a4a561c82a8d9de6b94f3ef1`, verified, uploaded once |
| New rows | Document **3143**; chunks 12; insights 5193–5196; claims **2381–2384**; Entity Integrity **42**; Truth Delta **95**; memo **101** |
| Model calls | **8:** 1 memo generation (`msg_011CgAzJTbee4vwx4LZDstnV`) and 7 `/ask/` (Q1–Q7, once). No retry, no failure |
| Isolation | SQLite backup copy of the dev DB, migrated and sequence-advanced in the copy only. Local Memurai db 1/3 (no empty db existed; see D-8). Six paid keys blank and `pending=0` inside server and worker. Memos 90/91 and 94–100 byte-identical before and after. **Memory watchdog running throughout** |

## Result

The merged guards made **no basis edit** on this reply; the stored memo equals the model's reply except one funding narrator insertion. The run's grading against the frozen criteria:

- **Pass:**
  - **OF-807 did not recur:** the conditions stay hypotheses.
  - **Funding:** narrator on 32/32 sentences; undated; unverified; not cash.
  - **Also held:** April-2016 traction is historical, with no platform counts, SEC identity, invented revenue or advice. Truth Delta states, note visibility, the 90-row authorization matrix (identical to memo 100's), owner-only reconciliation, canary boundaries and UTF-8 Markdown all hold.
- **Fail, in new wordings outside the merged rules' lexical scope (P2, provisional):**
  - **OF-903 (OF-805 class):** `business_model_analysis` says "500M messages (with an ambiguity … [S2, S3]) in a slide context headed 'Traction by Apr-16'".
  - **OF-904 (OF-805 class):** `upside_scenario` / `base_scenario` date the page-12 monthly figure by page 10's "Traction by Apr-16" context.
  - **OF-905 (OF-806 class):** `risk_assessment` 1 says "These figures … — raising the possibility of metric inflation or imprecise reporting".
  - **OF-906 (UB-604 class):** `downside_scenario` says "the inconsistency between the cumulative and monthly presentations", presupposing page 10 is cumulative.
- **P3 (provisional):** merged "500M messages [S2, S3]" citations with no place claimed (OF-907); a question presupposing the $23.1M is deployable (OF-909); "inconsistency", "delivered" and "The verification process identified …" (OF-910, RA-108).
- **RA-114:** `/ask/` still returns the marketplace fallback for all seven questions.

## Blockers and next step (documented before any fix)

- **Run blocker, resolved:** Chrome first could not reach the run server; the walks ran after the owner re-selected the browser (D-9).
- **Defects for review, not fixed here:** OF-903–OF-906.
  - **Common cause:** each guard rule matches specific wordings:
    - a parenthesised context aside;
    - the referents "one or both figures" / "the figures";
    - the judgment vocabulary;
    - "the cumulative figure/total/…".

    The model expressed the same failures in other wordings.
  - **Proposed direction:** for review only, not implemented. Instead of adding more phrasings, make the checks structural: a page-12 basis-pair ref cited in a clause that names page 10's context, a judgment word in a sentence continuing a basis item, and "cumulative" applied to the no-interval side. It would come with recorded-reply regressions from memo 101, as before.
  - **Next step:** await your review.
- **Open:** RA-109 acceptance pending review; RA-108, RA-114 and overall hardening remain open. No deployment, paid-source Pass B or other deck was run.
