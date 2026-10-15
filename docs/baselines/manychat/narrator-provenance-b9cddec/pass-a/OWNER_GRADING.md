# Independent grading — ManyChat memo 97 after PR #281 (document 3139)

**Reviewed:** 2026-10-14 (America/Tijuana). **Additive:** this file changes nothing in [RERUN_LEDGER.md](RERUN_LEDGER.md), the run's artifacts, memo 97, any earlier memo, document, ledger, grading, answer key or protocol, or the accepted memo-96 staff addendum.

## Reviewed state

| Item | Value |
|---|---|
| Application code | `b9cddecd9e6cc003f377aefbf6ed5fbff94ffd32` (merge of PR #281) |
| Evidence | `ea3ab136c6853b0ee53b009bd0d11133142ad1e6` on `docs/manychat-narrator-b9cddec`: 60 files under this folder; no application source or earlier evidence changed |
| Rows | Document 3139; claims 2366–2368; Entity Integrity 38; Truth Delta 91; memo 97 |

The reviewer graded the pushed artifacts directly, not the Windows ZIP.

## Grade

**Focused post-merge validation: PASS**, with nonblocking P3 wording notes. The original RA-106 failure is absent from the newly generated memo and from its captured reader surfaces. The live post-fix requirement is accepted for the new-memo path at b9cddec.

**Overall Zelda hardening: NOT COMPLETE.** This focused pass closes none of the wider audit's recorded open findings.

| Item | Grading decision |
|---|---|
| RA-106 (stale/current funding presentation) | **Live validation accepted for future memos at this code state.** The recorded input preserves Pitch Deck Hunt as narrator, `as_of: not stated`, and 2015 as a contextual date that is not the as-of date. The fresh memo does not present the funding as current and does not use 2015 as its amount's date. **Historical memo 91 stays as stored** and remains historical evidence of the original failure |
| FF-405 / NP-502 (narrator provenance) | **No recurrence in memo 97.** Funding is credited to Pitch Deck Hunt, the company's bot and message statements stay separate, and no false equality appears. The provenance rule did not execute, so this run does not show a live correction by that rule. The corrective behaviour remains supported by the accepted regressions and mutations |
| FF-411 / NP-512 (Markdown) | **PASS, live.** The response declares UTF-8. The committed export bytes match the recorded response hash and character counts |
| NP-503 (active-round premise) | **PASS, live correction.** "for this round" became "for any current or planned raise" |
| NP-504 (profile context) | **PASS, live correction.** The sector receives the current-profile/undated label. Whether the label is useful on a sector field is a wording concern, not a factual error |
| NP-508 (upside deployment wording) | **Nonblocking P3 clarity note.** The passage is conditional, says confirmation is required, and states that the evidence is absent. It does not establish that funds were received, spent or are available, and it gives no runway or cash estimate. Preferred wording first asks whether the reported funding occurred, then how any verified proceeds were deployed |
| NP-509 (amount-free funding references) | **Nonblocking P3 source-continuity note.** Both references cite C1 and call the funding unconfirmed or unverified. Neither attributes it to the company or asserts external verification, and the information-readiness list names Pitch Deck Hunt just before. Naming the narrator on each standalone reference would help snippets. This is not the earlier company/third-party misattribution failure |
| RA-108 / NP-510 | **OPEN.** The memo's comparison with what a plain AI summary would do is unmeasured. Correct attribution does not validate that self-comparison |
| Other frozen-audit findings | **Open or unchanged as recorded**: I1 (cumulative messages vs messages/month) missed; audit-framing material still supplies a funding claim (RA-103); the direct Truth Delta page is unstyled (FF-413); the Ask Zelda limitation (RA-114); and the rest of the recorded backlog |

The targeted RA-106 live gate is no longer waiting for a freshly generated memo. This is a scoped acceptance. It is not a claim that the whole ManyChat audit, or every possible model output, passes.

## Independent verification by the reviewer

The reviewer replayed the recorded model reply with the merged helper code, the recorded grounded payload and the recorded `time_wording_allowed` map (empty for all six dated items). The run database was not available to the reviewer. A fresh database-backed `GroundedContext.build` therefore rests on the run's record and was not re-executed.

| Check | Result |
|---|---|
| Sent payload vs rebuilt-payload artifact | Equal |
| Raw reply → `memo_text` → time guard → funding guard vs stored memo | All 17 stored fields match |
| Reversed context item order | Same output and changes for every field |
| Second pass through both guards | All fields unchanged, no further edits |
| Citation sequence, normalized reply vs stored | Preserved in every field |
| Guard edits reproduced | Five fields: `market_analysis`, `risk_assessment`, `what_would_change_the_picture`, `upside_scenario`, `questions_for_management` |
| Rule families observed | `attribution`, `profile_undated`, `raise_premise`; no `provenance` correction |
| Markdown bytes | 12,177 bytes; SHA-256 `c63433aff1074f20a67c1d8986e912747121bb13017df333ac6030553876fce7`; strict UTF-8 decode passes; 18 bullets and 26 em dashes, matching the recorded response |
| Four snapshot pairs (original, memo 94, 95, 96) | Before/after bytes identical within this run |
| Historical snapshot contents vs earlier committed artifacts | Same memo hashes and row data, after omitting the older startup warning (see below) |
| Recorded source-DB hash pairs | Equal |
| Recorded server and worker gates | Local isolated DB and broker; zero pending migrations; six paid-provider booleans false; Anthropic key present |
| Authorization matrix vs memo-96 run | All 90 principal/surface rows match on status, reconciliation panel and canary |
| Canary and reconciliation | Canary only on the owner and staff profile; reconciliation only for the owner |
| Worker chain | The memo task succeeded; its logged edits match the independent replay |
| Server log and recorded browser DOM | Staff MFA, fresh Truth Delta requests and the logout sequence are recorded; five browser walks have positive controls |
| Model-call record | Eight calls: one memo call plus seven probe calls |
| Evidence scope | One additive documentation commit; no application-code changes |

**Not performed by the reviewer:**
- another live generation;
- paid-provider calls or production access;
- a full application test run;
- a fresh browser session. The browser conclusions rest on the recorded DOM checks and the server log.

The GitHub connector could not decode the committed JPEGs, so the reviewer did not inspect the images.

The terminal's background-wrapper exit notices do not indicate a pipeline failure. The worker log records memo 97's successful generation before the intentional PID shutdown.

## Documentary correction (additive; the frozen ledger is not edited)

The ledger's run record says the new before-snapshots are identical to the earlier committed snapshot files "with line endings normalized". That understates the difference for the original, memo-94 and memo-95 snapshots:
- **The difference:** the earlier committed files (5f08c05 `snapshots/*_snapshot_after.txt`) each contain a startup line beginning `Invalid line` (a `.env` parse warning). The new snapshots do not.
- **How the run compared:** it removed `Invalid line` lines as well as carriage returns before comparing. The run's own record shows this: the comparison commands filtered with `grep -v "^Invalid line"`, and `assemble_np.py` drops lines starting with `Invalid line`. The ledger described only the line-ending normalization.

After omitting that warning, the memo hashes and captured row contents match. The new before/after files are byte-identical to each other. This corrects how the record describes the comparison. It is not evidence of a modified source DB or historical memo.

## Status after grading

- **Memo 97:** kept as generated; not regenerated or edited.
- **Memo 91:** unchanged; historical evidence of the original RA-106 failure.
- **RA-106:** the new-memo live acceptance is **satisfied** at b9cddec (scoped as above).
- **Open:** RA-108, RA-109/I1, RA-103, FF-413, the Ask Zelda limitation (RA-114), RA-105, PF-206/FF-311, and the other documented findings.
- **NP-508 / NP-509:** separate P3 clarity work if wanted. No further live run is planned just to sample different wording.
- **Zelda hardening:** NOT COMPLETE. Nothing was deployed. Paid-source Pass B was not run and is not needed to record this grade.
- **Suggested next correctness item:** RA-109/I1. Preserve and detect 500M cumulative messages versus 500M messages/month without merging the two meanings. Scope it and reproduce it before changing extraction.
