# Nike FY2026 rerun — ledger (Phase 1 acceptance)

Graded against [RERUN_ADDENDUM.md](RERUN_ADDENDUM.md) (frozen at `e44fc44` before the first upload), [ANSWER_KEY.md](ANSWER_KEY.md) and every L-number in [BASELINE_LEDGER.md](BASELINE_LEDGER.md). The addendum is not edited; corrections are recorded as errata below.

**Run:** 2026-10-04. **Code:** `main` @ `ea81470` (PRs #135–#147). The branch adds documentation only. No `.py` or template changes.
**Deck:** SHA-256 `e3fc9944…eec6b`, the same file as the baseline.
**Nothing was repaired.** Every setup correction is an erratum below (E-2 broker, E-3 schema, E-4 allowance).

## Verdict

**Phase 1 passes its acceptance test, with one open defect on the presentation layer.**

- Every canonical surface now agrees. Structured state, icons, counts, coverage sentence, "What Zelda noticed" and the memo all say revenue is not verified because its period is unknown, and employees has no external evidence.
- The baseline's P0 (L-005), the fabricated "500 people" contradiction (L-006), the memo-before-verification race (L-009), "external support" (L-008), the false embedding label (L-015) and the anonymous 500 (L-016) are fixed.
- Provenance now reaches the slide. Every expected fact sits in the chunk for its slide, and both claims cite the right slide.
- **Still open:**
  - The Truth Delta *judgment narrative*, which a model writes separately from the canonical state, still calls the revenue figure "materially overstated… a significant red flag". It appears on the Truth Delta page for every principal, and inside the IC memo page. This is the narrative half of L-005 and L-007. It is the one place where a surface disagrees with the canonical state.
  - The other open items are the pre-registered residuals (§3) and intelligence-quality backlog.

## Run record

| Item | Pass A (strict baseline comparison) | Pass B (production providers) |
|---|---|---|
| Document | **3120**, `analyzed`, 10 pages, 618 words | **3121**, `analyzed` |
| Abandoned attempts | 3118 (E-2, broker), 3119 (E-3, schema) | First upload refused 402 (E-4) |
| Environment control | `BASELINE-ENV-CHECK` from inside the server and the worker: all six paid keys `False`, Anthropic `True` | Filed, CompanyEnrich, NewsAPI, DataForB2B `True`; Crunchbase and USPTO `False` (no key in `.env`) |
| Broker / schema control | `BROKER-CHECK` all five `localhost`, `SCHEMA-CHECK pending=0`, in both processes (E-2, E-3) | Same |
| Worker tasks | pipeline → claims → Entity Integrity → Truth Delta → memo → notify. Nothing else received | Same chain |
| Profile | No website, no geography | `company_website=https://www.nike.com`, `geography=Beaverton, OR` |
| Principals | `rerun_nike_owner` (Application 36, not Premium), `rerun_lite_investor`, `rerun_paid_investor` (`is_premium=True` + active subscription, per E-1), `rerun_staff`, anonymous. Canary `CANARY-RERUN-5519` in a PRIVATE field | Same |
| Rows | 10 chunks, 6 insights, claims 2342–2343, observation 127 (128 after re-verify), reports 80 and 81, memo 83, Entity Integrity report 24 (reused) | Observation for SEC revenue, report for 3121, Entity Integrity report 25 |
| Artifacts | [`rerun/pass-a/`](rerun/pass-a/) files 01–15 | [`rerun/pass-b/`](rerun/pass-b/) files 01–13 |

## Pass A: layer results against addendum §2

| # | Layer | Result | Evidence |
|---|---|---|---|
| 1 | Extraction | **PASS** | `[[zelda:slide 1..10]]` in `raw_text_full`; none in `raw_text_preview`; no parser or dependency text (`01`) |
| 2 | Chunking | **PASS** | 10 chunks, `page_number` 1–10 in order, real slide titles. Delaware {2,6,8}, 81,500 {2,6}, $52.8B {2,4}, "$52.8 billion" {3}, 46.1% {4} and CIK {8}, each on exactly its slides. `embedding_model` `semantic-hash-v1` (`02`) |
| 3 | Insights | Recorded | 6 regex insights: Market and Funding from Key Risks; Revenue and Product from Investment Thesis; Team from Operating Footprint; Traction from the slide-1 title (`03`) |
| 4 | Claims | **PARTIAL** | `employees` cites slide 6 and `revenue` cites slide 3 (pass). `text_excerpt` is bounded (23 and 73 characters, never a whole chunk), but it is the regex capture, not the claim's sentence. The revenue excerpt is cut mid-word: "…stabilization across cor" (L-024) (`04`) |
| 5 | Truth Delta | **PASS** | Revenue `no_data`/`period_unknown`. SEC 46,398,000,000, FY2026 10-K, CIK 0000320187, `can_establish`/`sec_filing`. Employees `no_data`/`no_external_evidence`. `provider_outcomes` `{"dataforb2b": "unconfigured"}`. Scored 42/high, because an establishing row exists (`05`–`07`) |
| 6 | Canonical presentation | **PASS on every canonical field; FAIL on the model narrative** | Truth Delta page: 0 VERIFIED, "0/2 claims verified against external data (0%)", ❔❔, and the revenue note "An external figure was found, but its period could not be confirmed as comparable…". Intelligence Report: "0 of 2 checkable claims verified against a public source; 2 could not be confirmed." Noticed: "An external figure was found for revenue, but its period could not be confirmed as comparable." No "external support" anywhere. **But** the same Truth Delta page's OVERALL ASSESSMENT says "materially overstated… a significant red flag", and the revenue detail says "a material and unexplained overstatement" (`13`, `15`) |
| 7 | Retrieval | **PASS** (prediction confirmed) | Q1–Q7: every source is a real slide; none at 0.000; search and RAG identical. As predicted, Q5 and Q6 return `no_relevant_evidence: false`, and Q1's five sources tie at 0.225 (L-002/L-013 residual) (`10`) |
| 8 | Intelligence outputs | Not exercised | As in the baseline (L-018 unchanged) |
| 9 | Memo | **PASS** | Created 10:29:05, after report 80 (10:28:10). States revenue as INSUFFICIENT, period unknown, beside SEC's $46.4B. Never calls $52.8B supported or verified. No standalone "500 people". No canary. 6 citations of [C…]/[S…]/[P…] refs. No advice. Absence is scoped: "Gross margin: Not found in the extracted evidence" (`09`) |
| 10 | Authorization | **PASS** | Same matrix as the baseline. Changed cells: anonymous `analyze/founder` → **403** (was 500). Search/RAG: Lite, paid and anonymous 403; owner and staff 200. Canary only for owner and staff, in the in-process probe and in all five browser walks (text and `outerHTML`). New: viewer-premium gate measured, Lite `credit_limit` 3 vs paid 100 (`11`, `15`) |
| 11 | Idempotence | **PASS** | Run Verification (POST `truth-delta/verify/`, 202). One SEC row before and after; row 127 replaced by an identical 128. States, reasons, comparison rows, counts and provider outcomes identical; score 42→42. Exactly one memo task ran; memo 83 regenerated in place. A second report (81) was appended: reports are history, and readers take the latest (`14`) |
| 12 | Ledger | Done | Below |

## Pass B: provider results against addendum §4

| Provider | Result | Evidence |
|---|---|---|
| DataForB2B | **PASS** | `provider_outcomes.dataforb2b` = `ambiguous`; no DataForB2B observation rows; balance 2,993.9 credits before and after (0 spent) |
| Filed | **PASS, prediction partly wrong** | `Beaverton, OR` → `OR` (`state_from_geography`). One OR-scoped search. It came back AMBIGUOUS ("More than one registered business matches this name exactly, so none was attributed"), so no detail call followed; the addendum predicted "search plus detail". Finding `couldnt_check`; it contradicts nothing. A cross-state search cannot be sent (`filed._search` raises without a state) |
| NewsAPI | **PASS** | Headlines reached the Truth Delta summary as context ("News headlines suggest…"). No observation row |
| CompanyEnrich | **PASS** | Entity Integrity `commercial_footprint`: "aggregated commercial data, not a government registry… corroborates… rather than establishing its legal identity". Not a Truth Delta observation |
| Website / domain | Recorded | nike.com loaded (redirected to `/mx/`); the company name was found; the owner's name was `not_found`; the domain registered March 1995 (`public_record`) |
| Revenue / employees | **PASS** | Identical canonical states to Pass A. Same 0/2 coverage sentence and noticed lines. The memo states INSUFFICIENT and SEC $46.4B, with no provider data presented as verification |

## Scorecard against the answer key (Pass A)

| ID | Baseline | Rerun |
|---|---|---|
| C01 revenue | False verify: ✅ and "1/2 verified" beside a `no_data` state | **INSUFFICIENT on every canonical surface** (pre-registered residual, L-007). The model narrative still calls it an overstatement (L-005 residual) |
| C02 employees | Coverage gap (correct) | Coverage gap (correct) |
| C03, C05, C06 | Not checked (allowed) | Not checked (allowed) |
| C04 Delaware | MISSED | MISSED (L-011, pre-registered residual). Pass B still compares the profile, not the deck |
| C07 CIK | Correct | Correct (0000320187 in Truth Delta and Entity Integrity) |
| C08–C25 | Missed; 6 with false-absence statements | Still never claims (L-010). The false-absence statements are gone: the memo now says "not found in the extracted evidence" |
| I1, I4, I5 | Missed | Missed (L-012, pre-registered residual) |
| I2, I3, N1, N2, N3 | Correct | Correct |
| N4 puffery | Traction insight from the subtitle | Unchanged (L-023) |
| Fabricated fact | "500 people" contradiction (L-006) | **Gone** |

## L-number grades

| ID | Grade | Evidence |
|---|---|---|
| L-001 | **Fixed** (PR #147) | No parser or dependency text in the extracted text. Not exercised by a damaged file in this run; covered by PR #147's tests |
| L-002 | **Still open** → retrieval/embedding workstream | `embedding_vector` stored as `str`; cosine is always 0; Q1 ties five ways at 0.225 |
| L-003 | Unchanged (ops) | Keys neutralised in-process for Pass A. E-2 adds that `.env` also carries the shared broker URL |
| L-004 | **Still open** → source-coverage backlog | SEC still fills revenue only for this deck: 1 observation |
| L-005 | **Fixed on canonical surfaces; narrative still open** → presentation workstream | Icons ❔, counts 0/2, rollup 0%, period note: all agree. The Truth Delta judgment narrative ("materially overstated", "red flag") disagrees, on the Truth Delta page and embedded in the IC memo page |
| L-006 | **Fixed** | No standalone "500 people" in either memo; no self-credit |
| L-007 | **Still open** (pre-registered) → claim-period workstream | `claim_period` null on both claims, so revenue is `period_unknown`. Every canonical surface says so; only the model narrative disagrees (L-005) |
| L-008 | **Fixed** | Coverage sentence exact; "external support" absent for Lite, paid and staff |
| L-009 | **Fixed** | Memo after report (10:29:05 > 10:28:10), built from GroundedContext. On a failed verification the memo says so (E-3 control) |
| L-010 | **Still open** → intelligence-quality backlog; **intentionally changed** in part | Regex insights, 2 claims. The memo's false absence is replaced by scoped absence |
| L-011 | **Still open** (pre-registered) | Delaware never compared, in Pass A or Pass B |
| L-012 | **Still open** (pre-registered) | I1, I4, I5 unflagged |
| L-013 | **Partly fixed** | No 0.000-relevance sources; real slides; `no_relevant_evidence` exists. Still never fires for Q5/Q6, and scores tie (L-002) |
| L-014 | **Mostly fixed** | Chunk `page_number` = slide; claims cite slides 6 and 3. Still open: `ClaimedDatapoint.source_chunk` is the string "Insight: Team", with `source_chunk_id` null; insight `source_attribution` is a section-title string |
| L-015 | **Fixed** | New chunks `semantic-hash-v1`; legacy rows relabelled `hash-legacy` by migration 0033 |
| L-016 | **Fixed** | Anonymous `analyze/founder` → 403 |
| L-017 | **Intentionally changed** (E-1) | Report surfaces are still keyed to the owner's Premium, by design. The viewer's Premium now measurably changes the allowance: 3 vs 100 |
| L-018 | Unchanged | Valuation API still 202 for a pitch deck (owner, staff) |
| L-019 | **Partly fixed** | The owner's username no longer appears. The Lite Truth Delta upsell still says "Zelda AI unlocks the full breakdown" beside the breakdown |
| L-020 | **Still open** | Truth Delta page `<title>` is empty |
| L-021 | **Not reproduced** | `notify_document_processed` ran after Truth Delta and the memo, in both passes |
| L-022 | **Still open, cause found** | The widget stayed on "Uploading file..." after the 402 refusal (E-4); it does not surface the error |
| L-023 | **Still open** | Traction insight from the slide-1 title; Funding insight from Key Risks |
| L-024 | **Still open** | `claimed_value` and `text_excerpt` are "…stabilization across cor" |
| L-025 | **Still open** | The probe's investor `GET analyze/founder` again wrote "You analyzed this company with Zelda" to the Lite library |
| L-026 | **Still open** | `CacheKeyWarning` for `sec_identity_v3:nike, inc.` in the worker log |
| L-027 | Retraction, re-confirmed | The Lite browser walk again showed the page rendering the same content as the API |

## Newly found

| ID | Layer | Observation | Bucket | Sev |
|---|---|---|---|---|
| R-001 | ops | A test run can enqueue into, and a local worker can drain, the shared Upstash queue. Paid model calls and data writes resulted (E-2) | CORRECTNESS/OPS | P1 |
| R-002 | ops | Local database six migrations behind the code, unseen by the gate's fresh test database (E-3) | OPS | P2 |
| R-003 | 6 | The Truth Delta judgment narrative is generated beside the canonical state, not from it. It is the only rerun surface that contradicts the canonical state (see L-005) | PHASE1-GROUNDING residual | P1 |
| R-004 | product | One upload costs a free founder 2 of 3 credits (memo plus automatic verification); one re-verification spends the third. A founder can upload once per 30 days | PRODUCT | P3 (observation) |
| R-005 | 11 | Re-verification sends a second `notify_document_processed` | PRODUCT-UI | P3 |
| R-006 | 7 | An Entity Integrity report reused across uploads keeps the first upload's `document_id` (24 → abandoned 3119) | INTEL-QUALITY | P3 |
| R-007 | 10 | A staff user with no role profile lands on `/accounts/choose-role/` after login | PRODUCT-UI | P3 |

## Passing controls

- **Isolation.** Pass A's keys were provably off, and Pass B's provably on. Both passes ran on a provably local broker and a current schema, proved from inside every process.
- **Canary.** It followed PRIVATE exactly in all five browser walks and in the in-process probe.
- **Failure path.** A real failed verification (3119, E-3) produced a memo that says the verification failed.
- **DataForB2B.** It spent nothing on an ambiguous domain.
- **Filed.** It made one state-scoped search, and reported its own ambiguity as `couldnt_check`, never as a finding against the company.
- **Context and corroboration stayed in their roles.** NewsAPI and CompanyEnrich data did not become observations.
- **No advisory language** anywhere, including Q7.

## Errata

**E-2 (2026-10-04), the broker.** Recorded before the Pass A upload that this ledger grades.

*What happened:*
- The first Pass A attempt uploaded the deck as document 3118. Its pipeline task never ran.
- The local `.env` points `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` and `CACHE_URL` at a shared Upstash Redis instance, not the local `memurai.exe`. That instance held 213 waiting tasks left by focused local test runs (refresh-matches for investors 1–3, memo regeneration and re-verification for document 1, and others). Document 3118's task sat behind them.
- The worker drained part of that backlog before it was stopped. That included about 10 `generate_intelligence_memo(1)` tasks, each a real Claude call that overwrote local document 1's memo. None of them touched Nike rows.
- The baseline ran the same way; see `BASELINE_LEDGER.md` erratum E-2.

*Correction (a setup change, not a code change):*
- The run wrapper sets the broker and result backend to `redis://localhost:6379/0`, and the cache to `redis://localhost:6379/1`, in-process. `read_env()` uses `setdefault`, so these values win over `.env`.
- Before starting, each server and worker process prints the effective host of `settings.CELERY_BROKER_URL`, `settings.CELERY_RESULT_BACKEND`, the Celery app's `broker_url` and `result_backend`, and the cache `LOCATION`. It exits unless every one is `localhost`.
- Proved both ways before the run: all five printed `localhost` with exit 0; with the override suppressed, all five printed the Upstash host and the process refused to start (exit 1).
- Document 3118 is abandoned. Its status is set to `error`, with `source_entity` "NIKE, Inc. (abandoned, erratum E-2)", so it cannot collide with the fresh upload. Its stranded task stays in Upstash, unexecuted.
- The Upstash queue is **not** purged. No queued task is executed. Ownership of that instance is open (see Follow-ups).

*Effect on the addendum:* none of the §2–§4 expectations change. §1 "Setup" gains the broker requirement above.

**E-3 (2026-10-04), the local database schema.** Recorded before the Pass A upload that this ledger grades.

*What happened:*
- The second Pass A attempt (document 3119) ran on the local broker as intended, but against a database that had never had migrations `zelda_api` 0029–0034 applied. That is every Phase 1 schema change.
- The blocking gate builds a fresh test database, so it never saw the gap. The addendum's §1 pinned the code, not the schema.
- Effect on 3119:
  - Extraction, chunking, insights and claims completed.
  - Truth Delta verification raised `no such column: zelda_api_observeddatapoint.role` and was recorded as a failure (`verification_failed_at`).
  - No report was written.
  - The document still reached `analyzed`.
  - A memo was generated through the failure path.

*Correction:*
- The services were stopped.
- The database was backed up with SQLite's online backup API (integrity `ok`) to `KCV_backups/db.pre-phase1-migrations-2026-10-04.sqlite3`, outside the repository, SHA-256 `baa2e577…4b7f9`.
- Migrations 0029–0034 were applied. `showmigrations` now lists nothing unapplied.
- Document 3119 is abandoned: status `error`, `source_entity` "NIKE, Inc. (abandoned, erratum E-3)".
- §1 "Setup" gains the requirement that the database have no unapplied migrations. The run wrapper now checks this in every server and worker process, and exits otherwise. Proved both ways: 0 pending on the migrated database (exit 0); 6 pending on a copy of the backup (exit 1).

*Effect on frozen baseline rows:* three of those migrations rewrite existing data, and they did so to document 3117 exactly as their code states:

| Migration | Document 3117 before | After |
|---|---|---|
| 0030 bound excerpts | claim excerpts of 1,309 and 1,312 characters (whole chunks, L-005) | 23 and 73 characters |
| 0031 role/origin | SEC observation with no role or origin | `can_establish` / `sec_filing` |
| 0033 honest label | 11 chunks labelled `claude-3-5-sonnet` (L-003) | `hash-legacy` |

The baseline ledger graded the pre-migration rows. Those rows are preserved unchanged in the backup, so the baseline's evidence stands.

*A passing control from the incident.* The 3119 memo states that the document's "verification failed", and calls the $52.8B figure one that "could not be independently verified". It is saved under `rerun/abandoned/`. This is the designed failure path (`truth_delta_tasks.verify_document_truth_delta`), observed working on a real failure.

**E-4 (2026-10-04), the owner's analysis allowance for Pass B.** Recorded before the Pass B upload.

*What happened:*
- The first Pass B upload was refused: `POST /api/v1/zelda/documents/ingest/` → **402** `quota_exceeded`, "0 of 3 remaining this period". No document was created.
- The allowance is a Lite founder's 3 credits per 30 days. Pass A spent all three on document 3120: its memo (1), its automatic Truth Delta verification (1), and the layer-11 re-verification (1).
- The abandoned documents 3118 and 3119 do not count (`status='error'` is excluded by `quotas._credits_used_in_window`).
- The upload widget never surfaced the 402. Its status stayed "Uploading file..." (L-022).

*Correction:*
- `Application.is_premium` is set to `True` on the owner's profile for the ingest request only. It is reverted to `False` as soon as the upload returns 201, before any capture.
- Nothing in extraction, chunking, claims, Truth Delta, providers or memo generation reads `is_premium`. It is read only by presentation gates: `truth_delta_models._owner_is_premium` (report and memo unlocks), `ic_memo.py:75` and `views.py:1337`. All Pass B surfaces are therefore captured under the same Lite gating as Pass A.
- The pre-registered §4 expectations do not change.

## Follow-ups

- **Fail-closed test broker** (separate PR after this one): the test runner refuses any Celery broker that is not in-memory, as it already refuses network calls.
- **Schema check before local runs:** a local run protocol should require `manage.py migrate --check` to pass before the first upload. This could go in the same PR as the broker guard.
- **Upstash queue:** before any purge is proposed, capture a non-secret manifest of the queued task names, ids and arguments, and establish that no other environment or process references that instance.
