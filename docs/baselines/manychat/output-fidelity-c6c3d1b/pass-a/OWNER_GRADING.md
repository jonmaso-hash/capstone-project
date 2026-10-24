# Independent grade — ManyChat memo 103 (document 3145), after PR #288

**Additive.** This file changes nothing in [RERUN_LEDGER.md](RERUN_LEDGER.md), the run's artifacts, memo 103, its raw model response, its eight model calls, any earlier run, the frozen key, protocols or accepted grades. It records the independent review's decisions as given.

## Decision: RA-109 output acceptance stays OPEN

| Item | Value |
|---|---|
| Code | `c6c3d1b9b1fe8b5e32d856c64a5b535a986684a0`, merge of PR #288 |
| Evidence | `4ee36395e61c5a943809940cab0f7bddc647cd57` on `docs/manychat-output-fidelity-c6c3d1b` |
| New rows | Document 3145; claims 2389–2392; Entity Integrity 44; Truth Delta 97; memo 103 |

| ID | Grade | Finding |
|---|---|---|
| OF-1102 | **P2, blocking** | `base_scenario` transfers page 10's April-2016 ("Traction by Apr-16") context onto page 12's monthly figure: "Taking the self-reported traction at face value without independent verification [S1, S2, S3], the company had deployed a meaningful bot platform by the period referenced in the 'Traction by Apr-16' slide context, with Pitch Deck Hunt listing $23.1M in prior funding [C1, S4]." |
| OF-1103 | **P2, blocking** | `upside_scenario` conditions accuracy and measurement basis ("are accurate and the per-month figure is the correct basis") but does not explicitly hypothesise the date, so placing [S3] "at the time of the 'Traction by Apr-16' slide" is an unsupported date transfer. **This resolves the ledger's Q-1.** |
| OF-1004 | **Passes in this sample** | Each figure's citations identify its own claim and statement |
| Browser | **Supports completion** | The owner, Lite, paid, staff (MFA) and anonymous walks in [15_browser_walks.json](15_browser_walks.json) are accepted as browser evidence for this run |
| Q-2, Q-3, Q-4 | **Not closed** | Remain separately tracked wording questions (OF-1105 "total vs. per month"; OF-1107 "the company has sought to characterise …"; OF-1109 hedged product-category inferences). They are neither graded nor closed by this decision |

The ledger's other readings and P3 classifications are not changed by this grade.

## Status

- **RA-109:** live output acceptance stays **OPEN** for OF-1102 and OF-1103.
- **Still open:** RA-108, RA-114 and overall Zelda hardening; Q-2, Q-3, Q-4.
- **Next:** a correction branch from current `origin/main`. It must reproduce OF-1102 and OF-1103 from memo 103's recorded response through the full guard sequence and the memo writer, without model calls, then correct the unsupported date transfer using each item's identity, page and supplied context, preserving the "without independent verification" qualification, the trailing Pitch Deck Hunt funding clause, explicit date hypotheses, conditions, denials, questions, unrelated facts and narrator attribution. No new live run until the correction is independently reviewed and merged.
