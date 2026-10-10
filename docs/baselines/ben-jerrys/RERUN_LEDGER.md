# Ben & Jerry's — rerun ledger (after claim-extraction PR 2, Pass A, narrow)

Graded against the frozen [ANSWER_KEY.md](ANSWER_KEY.md), [LEDGER.md](LEDGER.md) and
[../three-deck-audit/PROTOCOL.md](../three-deck-audit/PROTOCOL.md). None of those files is edited.
This rerun asks one question: **what changed on a real deck after claim-extraction PR 2**
(attribution #265, currency #266, periods #268, semantics `td.5`)?

## Run record

| Item | Value |
|---|---|
| Date | 2026-10-10 (upload 22:22:13 UTC) |
| Code state | `main` @ `cbda41a` (PR #268). No local `.py` or template changes |
| Deck | `ben_jerrys_public_pitch_deck_test.pptx`, 18,072,747 bytes, SHA-256 `0cb1be12…3fea`, matched the key immediately before the request. One upload |
| Document | 3130, `document_type=pitch_deck`, `source_entity="Ben & Jerry's"` |
| Principal | `rbj_owner` (user 308, application 44): `company_name="Ben & Jerry's"`, `geography="South Burlington, VT"`, no financial fields, canary `CANARY-BJ-2084` in `reason_for_capital`, PRIVATE |
| Pass | A only (owner decision 2026-10-10). Six paid keys blank; Anthropic present |
| Scope | Narrow (owner decision): extraction → claims → Truth Delta → Entity Integrity → memo, plus B-1. No authorization matrix or browser walks: no authorization code changed since the frozen run |

### Setup controls

- `manage.py preflight --local` under the run environment: broker (write/read), result backend and cache all `redis://localhost`; migrations 0 pending.
- Key check from a Django process started with the same environment file as the server and worker: Crunchbase, DataForB2B, NewsAPI, USPTO, CompanyEnrich, Filed all blank; Anthropic set. Positive control without the run environment: five of the six set (Crunchbase is empty in `.env`).
- Worker banner: `transport: redis://localhost:6379/0`, `results: redis://localhost:6379/1`. Local `celery` queue length 0 before the upload.

### Deviations from the frozen protocol, each recorded

| # | Deviation | Why |
|---|---|---|
| D-1 | Upload client: a scripted session login, then one `POST /api/v1/zelda/documents/ingest/` with `source_entity` and `document_type=pitch_deck` | The frozen surface, the Zelda widget `#document-upload-form`, was removed in #242. Its handler sent this same request; the server path is identical |
| D-2 | Process key checks ran in a sibling process sharing the server's and worker's environment file, not inside the server and worker | The frozen run wrapper is not in the repo; the worker banner shows the local transport directly |
| D-3 | The local dev DB was 20 migrations behind and was migrated before the run (backup kept outside the repo) | Protocol requires `pending=0` |
| D-4 | 18 stale messages sit in the local `high_priority` list. Nothing in current code routes there and this worker does not consume it | Left untouched; recorded |
| D-5 | A third profile now carries `company_name="Ben & Jerry's"` (frozen L-012 named two) | Fixture requirement; L-012 is not re-tested |

## Results, before and after

| Layer | Frozen run (doc 3128, `b9f6867`) | Rerun (doc 3130, `cbda41a`) | Change |
|---|---|---|---|
| Chunks / insights | 11 / 7 | 11 / 7, **identical insight text** | None |
| Claims | 0 | 0 | None |
| Truth Delta | `no_claims` | `no_claims`, no report row; summary "no verifiable claims were extracted" | None |
| `verification_state` | `no_claims` | `no_claims` | None |
| Entity Integrity | SEC filer `not_found` | Report 31: SEC filer `not_found`; website checks `not_applicable` (no website on the profile) | None |
| Memo | Generated | **Not saved: R-001** | Regression |
| Document status | `analyzed` | `error` (set by the memo failure) | Regression (R-001) |

### Why there are still zero claims (insight-gate replay with the production functions)

| Insight (page, category) | Mapped | Admissible | Ownership | Amount |
|---|---|---|---|---|
| p2 Market "Test whether Truth Delta separates brand facts, parent-company facts…" | market_size | yes | implied | none |
| p6 Revenue "These are parent/ice-cream-unit figures, not standalone Ben & Jerry's…" | revenue | yes | named | none |
| p4 Team "The brand is unusually transparent about values…" | employees | no | — | — |
| p3 Traction "Ben & Jerry's publicly frames the business around 'linked prosperity'…" | customers | no | — | — |
| p8 Problem, p3 Product, p2 Risk | narrative, not mapped | — | — | — |

Page 10's "Unilever's ice cream unit generated €7.9B in 2024 sales" is never selected as an insight, so the attribution rule that would refuse it (ownership: third party, "Unilever") is not exercised by this deck. C5 passes by abstention, as in the frozen run.

## Ledger

| ID | Layer | Principal | Observation | Key ref | Period phrase | Grade | Bucket | Sev | Blocking |
|---|---|---|---|---|---|---|---|---|---|
| R-001 | 7 (memo) | owner | **New, production.** The memo call succeeded (Anthropic 200, 2,888 input / 2,542 output tokens) and the save failed: `'list' object has no attribute 'encode'`. Cause: `archive_generated_memo` (`zelda_api/signals.py`, from `e566bea`, #245, 2026-10-08) sizes the memo with `.encode('utf-8')` on each text field of the in-memory instance; when the model returns a list for a section, that attribute is still a list. Reproduced in isolation: a string section saves, a list section raises the same error. The memo is lost after a billed call and the document is marked `error`. Recorded, not fixed (no repairs during a run) | C1–C8 memo grounding | — | Blocks memo checks | CORRECTNESS | P1 | Blocks memo layer only |
| R-002 | 7 (status API) | owner | The status endpoint returns the raw internal error string (`"Memo error: 'list' object has no attribute 'encode'"`) to the document owner | — | — | — | UX / hygiene | P3 | No |
| R-003 | 4 | — | Insights identical to the frozen run (7, same text); 0 claims. PR 2 changes nothing on this deck because no candidate carries an amount. C5 (€7.9B parent figure) and S-3 pass by abstention; the euro attribution case is covered only by fixtures (`tests_claim_attribution`, `tests_claim_currency`) | C5 | "2024 sales" (p10, not reached) | Not extracted | INTEL-QUALITY | P2 | No |
| R-004 | 5 | owner | B-1 holds: status, Truth Delta API and page all say `no_claims` / "no verifiable claims were extracted". "no public data found" absent. Page positive control: HTTP 200, 53 KB, phrase present | B-1 | — | PASS | — | — | No |
| R-005 | 6 | owner | Entity Integrity unchanged: EDGAR finds no filer for "Ben & Jerry's" (CIK 768384 not resolved by name), so S-4 staleness cannot occur; nothing presented as current | E1, E2, S-4 | — | PASS (abstention) | — | — | No |
| R-006 | 5 | owner | B-2: no claims, so no profile/deck pair exists; the reconciliation panel is correctly absent. Non-owner absence not re-tested (narrow scope) | B-2 | — | N/A | — | — | No |
| R-007 | 4 | — | Period language: no claims, so no `time_period`/structured period to grade. Key D's "1978" and "2000" never reach a claim | D | 1978, 2000 | N/A | — | — | No |

## Summary

PR 2 is invisible on this deck: the analyzer's insight selection is unchanged and none of its candidates carries an amount, so claims stay at zero and every claim-level trap still passes by abstention. The run did surface one production regression unrelated to PR 2: **R-001**, memo saves failing whenever the model returns a list section (introduced 2026-10-08). The memo-grounding checks are blocked until it is fixed.

Artifacts: [rerun/3130_dump.json](rerun/3130_dump.json) (read-only dump, including the insight-gate replay), [rerun/upload.txt](rerun/upload.txt).
