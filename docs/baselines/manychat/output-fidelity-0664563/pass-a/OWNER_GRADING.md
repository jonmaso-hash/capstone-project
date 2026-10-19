# Independent grade — ManyChat memo 101 (document 3143), after PR #286

**Additive:** this file changes nothing in [RERUN_LEDGER.md](RERUN_LEDGER.md), the run's artifacts, memo 101, its raw model response, any earlier run, the frozen key, protocols or accepted grades.

## Decision: RA-109 output acceptance stays OPEN

| Item | Value |
|---|---|
| Code | `066456341935d5ace32760a00788f78ec61a047a`, merge of PR #286 |
| Evidence | `82771ef3e4b5e27da82837ec1237e24cfa305e23` on `docs/manychat-output-fidelity-0664563` |
| New rows | Document 3143; claims 2381–2384; Entity Integrity 42; Truth Delta 95; memo 101 |

**Confirmed by independent inspection:** RA-109 remains open for OF-903, OF-904, OF-905 and OF-906.

| ID | Grade | Finding |
|---|---|---|
| OF-903 | **P2, blocking** | `business_model_analysis` cites page 12's monthly source (S3) together with page 10's (S2), inside the ambiguity parenthesis, and places both "in a slide context headed 'Traction by Apr-16'". Context is shared across different sources |
| OF-904 (base) | **P2, blocking** | `base_scenario` asserts that the platform was built "by the period referenced in the 'Traction by Apr-16' slide context" on the strength of "[S1, S2, S3]". The page-12 monthly figure is given page 10's date context as an assertion |
| OF-904 (upside) | **Recorded separately; not treated as an asserted date** | `upside_scenario`: "If the self-reported figure of 500M messages/month [S3] reflects a monthly run-rate as of the 'Traction by Apr-16' slide context …" is a hypothesis inside a condition. It is recorded, and is not blocking on its own |
| OF-905 | **P2, blocking** | `risk_assessment` 1: "These figures carry different measurement bases and cannot be directly compared without clarification — raising the possibility of metric inflation or imprecise reporting." A judgment from measurement ambiguity alone |
| OF-906 | **P2, blocking** | `downside_scenario`: "the inconsistency between the cumulative and monthly presentations of the 500M messages figure [C2, C3]" presupposes that page 10 is a cumulative presentation, which nothing admitted supports |

The ledger's other readings (OF-901/902/908/909/911/912 PASS; OF-907, OF-910 P3; OF-913 RA-114) are not changed by this grade.

## Status

- **RA-109:** live output acceptance stays **OPEN** for OF-903, the OF-904 base scenario, OF-905 and OF-906.
- **Still open:** RA-108, RA-114 and overall Zelda hardening.
- **Next:** a correction branch from current `origin/main`. It must reproduce the defects from memo 101's recorded response through the full guard sequence and the memo writer, then correct them on citation identity, source context and measurement basis. No live run until a corrected build is reviewed.
