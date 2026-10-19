# Independent grade — ManyChat memo 100 (document 3142), after PR #285

**Additive:** this file changes nothing in [RERUN_LEDGER.md](RERUN_LEDGER.md), the run's artifacts, memo 100, its raw model response, any earlier run, the frozen key, protocols or accepted grades.

## Decision: RA-109 output acceptance stays OPEN

| Item | Value |
|---|---|
| Code | `f34e3a399349a2d7401f66d9b60b10834047e57a`, merge of PR #285 |
| Evidence | `d8b224cda84fd8675adbbd5ddeef03148f0f7b25` on `docs/manychat-output-fidelity-f34e3a3` |
| Folder | `docs/baselines/manychat/output-fidelity-f34e3a3/pass-a/` |
| New rows | Document 3142; claims 2377–2380; Entity Integrity 41; Truth Delta 94; memo 100 |

**Confirmed:** the raw reply's cumulative/overstatement sentence (`risk_assessment`) and its "Contradictory" heading (`open_concerns`) were corrected live in memo 100 by the merged basis guard (OF-803, OF-804).

**Open:** three P2 grounding failures remain in the stored output.

## OF-805 — P2 grounding failure

`business_model_analysis` states "the company states 140,000+ bots [S1] and **500M messages [S2, S3]** as traction metrics **(in a slide context headed 'Traction by Apr-16')**". It combines the two message figures under the page-10 "Traction by Apr-16" context and incorrectly includes page 12's monthly source (S3) there.

## OF-806 — P2 grounding failure

`open_concerns` 1 ends "**One or both figures may misrepresent the scale of actual activity.**" It makes an unsupported judgment from measurement ambiguity alone.

## OF-807 — P2 grounding failure

`upside_scenario` says "These conditions are stated by the company [S1, S2, S3]". It attributes the analytical conditions, including active, paying customers, to the company, although the supplied evidence states only the figures.

## RA-114 — remains open

The seven HTTP-200 `/ask/` responses in the second Q1–Q7 attempt are marketplace fallbacks ("I couldn't find specific search criteria …"). They do not constitute successful document answers.

## Status

- **RA-109:** live output acceptance stays **OPEN** for OF-805, OF-806 and OF-807.
- **RA-114:** open.
- **Still open:** RA-108 and overall Zelda hardening.
- **Next:** a correction branch from `f34e3a3` scoped to OF-805–807, using the recorded memo-100 response; no live model run during correction.
