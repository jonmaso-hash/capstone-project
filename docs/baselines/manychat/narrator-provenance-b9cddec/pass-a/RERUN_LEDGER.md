# ManyChat — narrator-provenance Pass A ledger at `b9cddec`

**A new, separate live run after PR #281.** It edits or replaces no earlier record:
- the frozen narrow run (document 3129);
- the 458bdc9 rerun (document 3133, memo 91);
- the post-fix run (document 3136, memo 94), graded partial pass (88df894);
- the funding-fidelity runs: document 3137 / memo 95 (9688474) and document 3138 / memo 96 (5f08c05), each graded partial pass, including memo 96's accepted staff Truth Delta addendum;
- the narrator-provenance code-review evidence on main (`docs/baselines/three-deck-audit/narrator-provenance-*`).

It is graded against the frozen [../../ANSWER_KEY.md](../../ANSWER_KEY.md) under [../../../three-deck-audit/PROTOCOL.md](../../../three-deck-audit/PROTOCOL.md) and [../../../nike-fy2026/PROTOCOL.md](../../../nike-fy2026/PROTOCOL.md). The key, protocols and errata are unchanged ([00](00_setup.json) `frozen_artifacts`). The key was used for grading only, and none of its text reached the model ([09d](09d_memo_input_output_check.json)).

**Status: ungraded by the owner.** The grades below are the run's own reading. RA-106, RA-108 and Zelda hardening stay **PENDING** until this run is independently graded. Nothing was deployed. Paid-source Pass B was not run, and no application code was changed.

## Run record

| Item | Value |
|---|---|
| Date | 2026-10-14 local / 2026-10-15 UTC. Upload 03:43:18 UTC |
| Code | `b9cddecd9e6cc003f377aefbf6ed5fbff94ffd32`, "Merge pull request #281 from jonmaso-hash/fix/narrator-provenance". Parents: 9b6d215 and the reviewed PR head f3847db. **origin/main was exactly b9cddec when fetched: no mismatch.** No migrations since 9b6d215. New worktree `KCV-mc-np` on branch `docs/manychat-narrator-b9cddec`, created at b9cddec. Server and worker each print `CODE-DIFF non_pyc_files_differing_from_b9cddec=0`; only tracked `__pycache__` changed (allowed by the Nike protocol, rule 2) |
| Deck | `manychat_series_a_audit_deck.pptx`: 175,622 bytes, SHA-256 `be7a7171bbc84b9895a45adfbc41f2533f3d23b3a4a561c82a8d9de6b94f3ef1`. It matches the key on disk and again in the upload process. **One upload** |
| IDs (all new) | Document **3139** (`analyzed`, `complete`); 12 chunks; insights 5178–5180; claims **2366** `funding_raised`, **2367** `usage` messages, **2368** `usage` bots; Entity Integrity report **38**; Truth Delta report **91**; memo **97** |
| Database | A new SQLite backup **copy** of the dev DB: `scratchpad/np/db_np_copy.sqlite3`, made with the sqlite3 backup API from the original opened `mode=ro`. `integrity_check` ok. `zelda_api.0044` was applied to the copy only. The original `db.sqlite3` (`5a0b8c1c…7e9a2`) and the memo-94/95/96 run copies are byte-identical before and after ([snapshots/hashes_*.json](snapshots/)) |
| Isolation gate | The wrapper refuses to start unless the DB is this run's copy (the original and all three earlier run copies are named and refused), the Redis URLs are local db 6/7/14, every paid key is blank, the Anthropic key is present, there are no pending migrations, and there are no non-`.pyc` file differences from b9cddec. Before the migration it refused (`pending=1 ['zelda_api.0044_claim_source_context']`) |
| Broker / cache | Local Memurai, run-only databases: broker **6**, results **7**, cache **14**. All were empty and had no clients before the fixtures. Worker `mcnp@inventoroftues`, queue `celery`, `--pool=solo --concurrency=1`. Every other Redis db has the same key count before and after |
| Gates from inside both processes | Server pid 6712 and worker pid 14624 each print the following ([00](00_setup.json)):<br>• six paid keys `False`: `FILED_API_KEY`, `COMPANYENRICH_API_KEY`, `NEWS_API_KEY`, `DATA4B2B_API_KEY`, `USPTO_ODP_API_KEY`, `CRUNCHBASE_API_KEY`;<br>• `ANTHROPIC_API_KEY` `True`;<br>• `BROKER-CHECK` local, db 6/6/7/14;<br>• `DB-CHECK is_copy=True is_original=False is_historical_copy=False`;<br>• `SCHEMA-CHECK pending=0`, with applied heads zelda_api `0044_claim_source_context`, matchmaking `0095_profile_reporting_currency`, accounts `0017_personprofile_is_public` and billing `0007_truth_delta_credit_wallet`;<br>• `CELERY_TASK_ALWAYS_EAGER=False`.<br>`preflight --local`: ok. No code at this commit reads `USPTO_ODP_API_KEY`; it was blanked anyway |
| Memory | `tools/memwatch.ps1` from the main checkout (untracked there), threshold 1,500 MB, ran throughout. No process crossed the threshold ([process/memwatch.log.txt](process/memwatch.log.txt)). No tests or mutation work were run |
| Task order ([06](06_worker_chain.txt)) | 1. Fixture match refreshes (3; queued by the fixture saves). 2. `process_document_pipeline` (12 chunks, 3 insights). 3. `extract_claims_from_insights` (3). 4. `verify_entity_integrity` (38). 5. `verify_document_truth_delta` (91). 6. `generate_intelligence_memo` (**97**, 52.5 s). 7. `notify_document_processed` |
| Model | **8 calls in all.** One live memo call in the worker: `claude-sonnet-4-6`, `max_tokens` 4000, `end_turn`, 3,317 in / 2,406 out tokens. Seven `/ask/` query-extraction calls came from the HTTP probe's Q1–Q7 ([09b](09b_model_call.json), [09c](09c_all_model_calls.json)). No retry and no second generation |
| Principals | `npmc_owner` (321, Application 50, not Premium); `npmc_lite` (322); `npmc_paid` (323, `is_premium` plus an active local `INVESTOR_PREMIUM` subscription 9 with fake Stripe IDs, no payment action); `npmc_staff` (324, `is_staff`, real staff-MFA setup by HTTP, then real verify in Chrome); anonymous |
| Profile fixture (§E) | `company_name="ManyChat"`, `prior_amount_raised=163000000`, `raising_amount=0`, revenue blank, **reporting currency blank**. The currency erratum is carried forward: B-2 is `not_comparable / profile_currency_unknown`, not the key's `differs`. Canary `CANARY-MANYCHAT-4417` is in `reason_for_capital` (PRIVATE) |
| Preserved | Read-only snapshots (`PRAGMA query_only`) of memos 90/91 with documents 3132/3133 (original DB), memo 94/3136, memo 95/3137 and memo 96/3138 (their run copies). Each is identical before and after this run. The before-snapshots are identical to the committed 5f08c05 snapshots, including memo 96's accepted-addendum snapshot (`1f23b917…493a`). Committed evidence trees for runs 94/95/96 and review2 equal their known commits ([00](00_setup.json) `frozen_artifacts`) |

### Deviations

- **D-1: ingest API upload.** The deck was uploaded through the session-authenticated ingest API `POST /api/v1/zelda/documents/ingest/` (as the owner, `document_type=pitch_deck`), as in earlier runs. The only deck-upload form left in the UI is the Zelda product panel's intake (`zelda_products.js`), and it leads to Stripe checkout or a credit redemption (a payment action). The valuation form posts `business_valuation`.
- **D-2: repeated ID numbers.** The zelda_api AUTOINCREMENT counters were advanced **in this copy only** to the memo-96 run copy's maxima, read with `mode=ro`, so document, claim, report and memo IDs are new. User IDs 321–324 and Application 50 repeat earlier runs' numbers, but they are separate rows in a separate DB. Other "ManyChat" profiles 42/45/47 exist in the copy, inherited from the original DB.
- **D-3: instrumentation.** `anthropic` `Messages.create` was wrapped in-process to record the request kwargs and reply. No repo change, and no credentials are in the kwargs.
- **D-4: Chrome mechanics.**
  - **Sign-in:** the form fields were set and `form.requestSubmit()` called. Staff entered a current TOTP code on the real verify page.
  - **What was navigated:** every Truth Delta check was a navigation, including **staff's direct navigation after real login and MFA**. So were the owner and staff IC memos and the Lite and paid overviews.
  - **What was fetched in-page:** the Lite/paid IC memo 404s, the staff Markdown (so no file landed in Downloads) and the staff overview.
  - **Text capture:** the extension truncates long page text, so [15](15_browser_walks.json) records counts and the relevant sentences read from the DOM, not whole pages.
- **D-5: process stop.** Server and worker were stopped by exact PID (6712, 14624). No command-line match was used.
- **D-6: probe marker false positive.** The HTTP probe's case-insensitive marker "Form D" matches "plat**form d**ependency" in the memo. No Form D, CIK or SEC registrant appears ([09f](09f_section_scan.txt)).

## Memo input and output ([09a](09a_grounded_context_rebuilt.json), [09b](09b_model_call.json), [09d](09d_memo_input_output_check.json))

- **Input.** The payload sent equals the payload rebuilt from the stored rows. It also equals a fresh `GroundedContext.build` for the **actual generation principal** (`Principal.for_user(document.uploaded_by=321, ORIGIN_TASK)`, as `zelda_api/tasks.py:244`). Prompt rule 10 and the dated-runway sentence are present.
  - C1/S3 `$23.1M raised` carry `narrator: Pitch Deck Hunt`, `as_of: not stated` and `dates_not_as_of: ["2015"]`.
  - C2/C3/S1/S2 carry **no narrator** and `source_context: Traction by Apr-16`.
  - `ref_sources` gives Pitch Deck Hunt only for C1/S3.
  - `time_wording_allowed` is empty for every dated item.
  - `raise_supported` is false, and there is no cash, burn or runway.
  - Absent from the input: the canary, 163,000,000, Bessemer, TechCrunch, Summit Partners, 2019, $18M, $140M, the founders, the key's error labels, and the fixture's owner name and description.
- **Output.** All 17 stored sections equal the pipeline's own replay of the model's reply (list normalisation, then the time guard with the actual `time_wording_allowed`, then the funding guard). Every section passes three further checks:
  - **item-order stable:** the facts built from the reversed item list give identical output;
  - **idempotent:** a second pass of both guards changes nothing;
  - **citations preserved:** every ref is kept in order (no regrouping occurred).
- **Guards.** The time guard removed nothing. The funding guard changed 5 sections ([09e](09e_guard_changes.txt)):

| Section | Rule | Model wrote | Stored |
|---|---|---|---|
| `market_analysis` | `profile_undated` | "The sector is listed as Software [P2], and…" | "…Software [P2] **(current profile, undated)**, and…" |
| `risk_assessment` | `raise_premise` | "…dilution, valuation, and remaining capacity **for this round** are unknown." | "…remaining capacity **for any current or planned raise** are unknown." |
| `what_would_change_the_picture` | `attribution` | "…anchor the $23.1M raised figure [C1, S3]…" | "…the $23.1M raised figure **(per Pitch Deck Hunt)** [C1, S3]…" |
| `upside_scenario` | `attribution` | "…confirmation that the $23.1M raised [S3] was deployed…" | "…the $23.1M raised **(per Pitch Deck Hunt)** [S3]…" |
| `questions_for_management` | `attribution` | "…a breakdown of the $23.1M raised [S3] — by round…" | "…the $23.1M raised **(per Pitch Deck Hunt)** [S3]…" |

**The narrator-provenance rule (`provenance:*`, the #281 fix) did not fire.** The model did not write the FF-405 shape. `zelda_advantage` reads: "the $23.1M raised figure [C1] is narrated by Pitch Deck Hunt rather than stated directly by the company … the traction figures [C2, C3] were status-tagged INSUFFICIENT…". So FF-405 **did not recur**; this run did not show the rule correcting it. The rule's correcting behaviour stays evidenced by the deterministic regressions and mutations in `narrator-provenance-review2-d246e36/`, not by this memo. No supplementary probe was run here, and no adversarial wording was injected.

**First live exercise of two guard paths.** `raise_premise` and `profile_undated` were exercised and corrected live for the first time in these ManyChat runs. Both outputs are grammatical, and both keep their citations.

## Focused checks (all surfaces: stored, memo API ×4 principals, HTTP-rendered pages, Chrome)

| Check | Result |
|---|---|
| Funding provenance | **PASS.** Pitch Deck Hunt appears on every sentence stating $23.1M: 48/48 across 51 HTTP-captured surfaces ([09f](09f_section_scan.txt)). Chrome: owner Lite memo 3/3, Lite and paid overview 1/1, staff memo 9/9, Markdown 9/9. Pitch Deck Hunt is never credited with bots or messages: every co-occurrence puts it on the [C1, S3] funding clause, and S1/S2 stay the company's. There is **no invented independent validation**: every "independent / confirm / validat / corroborat" sentence is negative ("not independently verified", "could not be confirmed or refuted") |
| Equality wording | **PASS (not exercised).** There are zero "same figures / identical / narrator of" sentences on any surface. The `zelda_advantage` shared-credit wording is legitimate ([C1] Pitch Deck Hunt; [C2, C3] the company's traction) |
| Periods | **PASS.** No current or cumulative total on funding ("to date", "so far", "in total": 0). 2015 never appears beside the funding (0). Financial analysis: "The date as of which this figure applies is not stated." Traction is "contextually dated 'Traction by Apr-16'", never stated as current (0 present-tense hits). The FF-406 shape "as of April 2016" did not recur |
| Funding vs live raise | **PASS (guard exercised once).** The model's "remaining capacity for this round" was rewritten. What remains is "Use of proceeds: Not found", "capacity for a new round are unknown", and the conditional question "Is a new funding round currently planned or in progress, and if so…". See NP-508 for the upside sentence |
| Funding vs cash | **PASS.** Runway appears only as a gap ("Runway cannot be calculated — no dated cash balance or burn rate is available"), as evidence to supply ("a current cash balance with burn rate, to allow … calculation of runway"), and as a question to management. There is no available-cash or remaining-runway premise |
| Natural wording, lists, counts, citations | **PASS.** Lists render in HTML (owner Lite 2 and 4 items; staff 2, 4, 8 and 5) and in Markdown (19 `- ` items, 18 `•` lines), with no list repr. The counts are 3 / 0 / 3, "(of 3)" and "none of the 3 claims" on every page. Citations are unchanged by every guard edit |
| Markdown (FF-411, live) | **PASS.** `Content-Type: text/markdown; charset=utf-8`; 12,177 bytes, with 18 `•` and 26 `—` present as UTF-8 byte sequences. `requests` (a normal reader that honours the charset) decodes identically to strict UTF-8, with no mojibake and no U+FFFD. Chrome agrees (in-page fetch: 18 `•`, 26 `—`, no mojibake). A Latin-1 decode would still mojibake, which is why the charset matters ([14](14_markdown_utf8.json), [14_ic_memo_export.md](14_ic_memo_export.md)) |
| Privacy and authorization | **PASS, identical to the 9b6d215 run on all 90 principal × surface rows** (status, owner panel, canary, redirect). The canary appears only on the owner's and staff's profile page; it is never in the model input or any memo surface. The reconciliation panel is owner-only, staff included (Chrome: owner yes; Lite, paid and staff no). B-2: owner `not_comparable / profile_currency_unknown`; Lite, paid, staff and anonymous `[]` ([11b](11b_reconciliation_by_principal.json)) |

## Grades against the key (run's reading; owner grading pending)

| ID | Observation | Grade |
|---|---|---|
| M1 $23.1M | Claim 2366, `funding_raised`, ownership `named`, narrator Pitch Deck Hunt, no currency, no period; INSUFFICIENT; Pitch Deck Hunt on every surface; undated; never current; 2015 not used as its date | INSUFFICIENT, no STALENESS ERROR; attribution PASS |
| M2–M4 | Not extracted; no platform user count anywhere (0) | No ATTRIBUTION ERROR |
| M5 | Claim 2368: 140,000 bots, INSUFFICIENT, slide context "Traction by Apr-16" | INSUFFICIENT, dated by context |
| M6 / I1 | Slide 12 "/month" not extracted; the memo does not flag the cumulative-vs-monthly conflict | I1 missed (RA-109, unchanged) |
| M7 / M8 | Not extracted | Allowed |
| E1–E3 | Entity Integrity 38: `sec_filer` `not_found` ("Most private companies never file with the SEC"); the rest `not_applicable`; no CIK, Form D or incorporation | PASS |
| §E B-2 | 163M vs 23.1M: `not_comparable / profile_currency_unknown`, owner only | As the currency erratum (RA-105) |
| Q1–Q7 | Owner search and RAG 200; near-uniform relevance; `no_relevant_evidence` false; `/ask/` returns marketplace query extraction for all seven ([10](10_retrieval_ask_q1_q7.json)) | As before (RA-114, the prior Ask Zelda limitation) |

## Authorization matrix ([11](11_authorization_matrix.json); Chrome [15](15_browser_walks.json))

| Surface | Owner | Lite | Paid | Staff | Anon |
|---|---|---|---|---|---|
| Overview `/matchmaking/memo/profile/50/` | 403 (by design) | 200 Lite | 200 Lite | 200 Full | 302 |
| IC memo / Markdown | 200 Lite / 302 | 404 / 404 | 404 / 404 | 200 Full / 200 `charset=utf-8` | 302 / 302 |
| Truth Delta page | 200 + owner panel | 200 | 200 | 200 (Chrome direct navigation after login and MFA) | 302 |
| Memo API | 200 | 200 `lite_sections` | 200 `lite_sections` | 200 full | 403 |
| Search / RAG | 200 | 403 | 403 | 200 | 403 |
| Profile (canary) | 200, canary | 200, no canary | 200, no canary | 200, canary | 302 |

HTTP logout per principal returns 302 to `/home/`, after which the protected URL redirects to login. In Chrome, every signed-in walk ended with the nav **Sign Out** (POST), confirmed by a protected URL redirecting to login. Anonymous: Truth Delta and the profile redirect to login; the positive-control home page loads.

## Ledger

| ID | Layer | Principal | Observation | Key ref | Grade | Bucket | Sev | Blocking |
|---|---|---|---|---|---|---|---|---|
| NP-501 | 9 | all memo readers | Pitch Deck Hunt on every $23.1M sentence (48/48 captured; Chrome 3/3, 1/1, 9/9, Markdown 9/9). The model supplied it in 6 sections and the guard in 3 | M1 | PASS | — | — | No |
| NP-502 | 9 | staff (full memo, Markdown) | **FF-405 did not recur.** `zelda_advantage` credits only [C1] to Pitch Deck Hunt and calls [C2, C3] the traction figures. There is no "same figures", "identical" or "narrator of" wording on any surface. The #281 rule was **not exercised** live (no `provenance:` change) | M1, M5 | PASS (did not recur; not exercised) | PHASE1-GROUNDING | — | No |
| NP-503 | 9 | staff | `raise_premise` **exercised live**: "remaining capacity for this round" → "for any current or planned raise". The company has no raise in the evidence (`raise_supported` false, profile `raising_amount=0` not in the input) | M1 | PASS (guard corrected) | — | — | No |
| NP-504 | 9 | staff | `profile_undated` **exercised live**: "The sector is listed as Software [P2] (current profile, undated)". Accurate; the label lands on a non-financial field (sector), where "undated" adds little. Wording note only | §E | PASS; wording note | PRODUCT-UI | P3 | No |
| NP-505 | 9 | all | Periods: no current total, no 2015-as-date, "date … is not stated"; traction "contextually dated 'Traction by Apr-16'". FF-406 ("as of April 2016") did not recur | M1, M5 | PASS | — | — | No |
| NP-506 | 9 | all | Cash and runway: gap, evidence request and question only; no premise | M1 | PASS | — | — | No |
| NP-507 | 9 | all | FF-407 did not recur: "profiled as a Series A company [P1, P2]", "Stage: Series A per profile [P1]" | §E | PASS | — | — | No |
| NP-508 | 9 | staff | `upside_scenario`: "confirmation that the $23.1M raised (per Pitch Deck Hunt) [S3] was deployed against a clear product roadmap". It is conditional ("would require confirmation") and narrated, but it presupposes that the funding was received and deployed by the company. For the owner | M1 | Borderline; for owner | INTEL-QUALITY | P3 | No |
| NP-509 | 9 | Lite (`information_readiness`) and staff (`downside_scenario`) | Two funding references **without the amount** carry no narrator: "Funding raised figure [C1] — no external confirmation found" and "the unverified funding figure [C1]". Neither credits anyone else; the same section's "Present" list names Pitch Deck Hunt. The guard attaches narrators only to sentences stating the figure | M1 | Observation; for owner | INTEL-QUALITY | P3 | No |
| NP-510 | 9 | staff | RA-108 is unchanged in kind. `zelda_advantage` still credits the system ("a distinction a plain AI summary would likely present as a straightforward company disclosure"). Its content is now accurate | — | Open, not graded fixed | INTEL-QUALITY | — | No |
| NP-511 | 5, 9 | all | Counts 3/0/3 and "(of 3)", lists rendered, citations kept through all 5 guard edits, replay/order/idempotence checks all true | — | PASS | — | — | No |
| NP-512 | 9 | staff | FF-411 live: Markdown served with `charset=utf-8`; the UTF-8 survives in the bytes, in `requests` and in Chrome | — | PASS (live) | — | — | No |
| NP-513 | 10 | all | Privacy and tier boundaries hold; the matrix is identical to memo 96's run; reconciliation is owner-only, including for staff; no canary or fixture amount in the model input or any memo surface | — | PASS | — | — | No |
| NP-514 | 10 | staff (and anyone navigating directly) | FF-413 is unchanged: the Truth Delta page is a doctype-less, unstyled fragment ([screenshot](browser/staff_truth_delta_direct.jpg)). Content, counts and privacy are correct | — | Open | PRODUCT-UI | P3 | No |
| NP-515 | 5–9 | — | Unchanged open items, **not graded fixed by this run**: FF-406 and FF-407 (did not recur this time, which is not a fix), PF-206/FF-311 (Section Coverage 31.2% owner Lite vs 100.0% full), RA-109/I1, RA-103 (claim 2366 comes from the audit-framing slide 2, ownership `named`), RA-114 (`/ask/`), RA-105 (B-2 `not_comparable` with a blank currency), RA-108 (NP-510), FF-413 (NP-514) | — | As before | — | — | No |

No defect was repaired during the run. No data-corruption or isolation problem occurred.

## Summary

On one live generation from merged main (`b9cddec`, memo 97):
- Every $23.1M sentence names Pitch Deck Hunt on every surface and tier.
- Pitch Deck Hunt is never credited with the company's traction, and nothing equates bots or messages with the funding.
- No current total, 2015-as-date, active-raise, cash or runway premise survives.
- Lists, citations, counts, Markdown UTF-8, privacy and tier boundaries hold, and the authorization matrix is unchanged.

**FF-405 did not recur, but the narrator-provenance rule did not act.** The model wrote the attribution correctly by itself. This run shows the defect absent in one sample, not the fix correcting it.

Two other guard paths (`raise_premise`, `profile_undated`) corrected live output for the first time. Two new P3 notes are left for the owner (NP-508, NP-509).

**RA-106, RA-108 and Zelda hardening stay pending until this run is independently graded.**

## Artifacts

- [00](00_setup.json): setup, gates from both processes, isolation, ID sequences, Redis before/after, source-DB hashes, preservation, frozen-artifact checks.
- [01](01_extraction.json)–[09](09_memo.json): pipeline rows (extraction, chunks, insights, claims with provenance/period/currency, observations, Truth Delta, Entity Integrity, memo).
- Memo input/output:
  - [09a](09a_grounded_context_rebuilt.json): rebuilt input.
  - [09b](09b_model_call.json): the memo call, request and raw reply.
  - [09c](09c_all_model_calls.json): all 8 calls.
  - [09d](09d_memo_input_output_check.json): equality, replay, order, idempotence and citations.
  - [09e](09e_guard_changes.txt): guard edits.
  - [09f](09f_section_scan.txt): sentence scan.
- HTTP probe:
  - [10](10_retrieval_ask_q1_q7.json): Q1–Q7.
  - [11](11_authorization_matrix.json): matrix, logouts and content types.
  - [11b](11b_reconciliation_by_principal.json): B-2 per principal.
  - [12](12_api_payloads.json) and [13](13_rendered_reports_text.json): API payloads and rendered text.
- Markdown: [14](14_markdown_utf8.json) and the exported bytes [14_ic_memo_export.md](14_ic_memo_export.md).
- Chrome: [15](15_browser_walks.json) and [browser/](browser/).
- Probes: [16](16_probes.json), the numeric-parse probes carried from earlier runs.
- [process/](process/): server, worker and memwatch logs. [scripts/](scripts/): every run script, as `.txt`. [snapshots/](snapshots/): read-only before/after snapshots, DB hashes and Redis key counts.
