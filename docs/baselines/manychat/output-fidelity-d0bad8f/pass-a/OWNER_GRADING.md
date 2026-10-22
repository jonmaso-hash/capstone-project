# Independent grade — ManyChat memo 102 (document 3144), after PR #287

**Additive.** This file changes nothing in [RERUN_LEDGER.md](RERUN_LEDGER.md), the run's artifacts, memo 102, its raw model response, its eight model calls, any earlier run, the frozen key, protocols or accepted grades.

## Decision: RA-109 output acceptance stays OPEN

| Item | Value |
|---|---|
| Code | `d0bad8fdaace39f2f64be9f576874da9b0bf5e7a`, merge of PR #287 |
| Evidence | `6d131f585cb5232a7535d896d6659583b5ecb053` on `docs/manychat-output-fidelity-d0bad8f` |
| New rows | Document 3144; claims 2385–2388; Entity Integrity 43; Truth Delta 96; memo 102 |

| ID | Grade | Finding |
|---|---|---|
| OF-1003 | **P2, blocking** | `base_scenario`: "If the traction figures [S1, S2, S3] are taken at face value under the 'Traction by Apr-16' framing, ManyChat had reached meaningful platform scale at that point in time." S1 and S2 come from page 10, which carries that heading; S3 is page 12's monthly statement and has no supplied date context. "Taken at face value" does not establish that S3 shares page 10's date. This answers the ledger's Q-1: the date transfer is unsupported, not an explicit hypothesis |
| OF-1004 | **P2, blocking** | `open_concerns` 1 and `business_model_analysis` associate the monthly figure with `[C3, S3]`. The mapping is C3 / S2: page 10, 500M messages, interval unstated; C2 / S3: page 12, 500M messages/month. The correct S3 beside an incorrect C3 does not make that claim citation accurate. This answers Q-2: P2 |
| OF-1005 | **Not an additional context blocker** | The complete `business_model_analysis` sentence explicitly places the monthly figure "elsewhere [S3]" and attaches [S1, S2] to page 10's heading. Its wrong claim citation remains covered by OF-1004. This answers Q-3 |

The ledger's other readings and the P3 classifications (OF-1008 under OF-909, OF-1009 under OF-910, including RA-108) are not changed by this grade. The Chrome walks remain **blocked** (OF-1015 / D-9) and are not counted as passed.

## Status

- **RA-109:** live output acceptance stays **OPEN** for OF-1003 and OF-1004.
- **Still open:** RA-108, RA-114 and overall Zelda hardening; the browser walks for a full Pass A record.
- **Next:** a correction branch from current `origin/main`. It must reproduce OF-1003 and OF-1004 from memo 102's recorded response through the full guard sequence and the memo writer, then correct them using claim identity, statement, measurement basis, page and supplied context, without regenerating memo 102 or repeating its Q1–Q7. No live run until a corrected build is independently reviewed and merged.
