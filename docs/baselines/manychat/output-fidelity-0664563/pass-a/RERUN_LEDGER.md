# ManyChat — Pass A ledger at `0664563` (after PR #286)

**A new, separate live run after PR #286.** It edits or replaces no earlier record:
- **Earlier runs:** documents 3129, 3133 and 3136–3142, and memos 91 and 94–100.
- **Memo 100:** its run and grade (`output-fidelity-f34e3a3/pass-a/` at `f17db5c` on `docs/manychat-output-fidelity-f34e3a3`).
- **PR #286's correction evidence:** `three-deck-audit/output-grounding-of805-807-1801ec5/` and `output-review-1801ec5-2ed9235/`.
- **Frozen artifacts:** the answer key and protocols are unchanged ([00](00_setup.json) `frozen_artifacts`).

Graded against the frozen [../../ANSWER_KEY.md](../../ANSWER_KEY.md) under [../../../three-deck-audit/PROTOCOL.md](../../../three-deck-audit/PROTOCOL.md) and [../../../nike-fy2026/PROTOCOL.md](../../../nike-fy2026/PROTOCOL.md), with the carried interpretations below. The key was used for grading only; none of its text, nor any fixture, review-finding or guard-output text, reached the model ([09d](09d_memo_input_output_check.json) `absent_from_model_input`).

**Status: the run's own readings and grades, for independent review.** RA-109 live output acceptance is **pending that review**; this ledger does not declare it. RA-108, RA-114 and overall hardening remain open. Nothing was deployed, no paid-source Pass B or other deck was run, and no application code was changed.

## Carried interpretations (additive; the key is not edited)

- **M6 / I1:** page 10 states **500M messages with no explicit interval**, and page 12 states **500M messages/month**. The output must:
  - keep each figure with its own page, context and citations;
  - ask for clarification;
  - not infer that page 10 is cumulative, and not annualise either figure;
  - not declare a contradiction, or judge either figure (overstated, inflated, misleading), from these two statements alone.
- **Funding:** the deck's $23.1M is Pitch Deck Hunt's listing. It is historical, undated and unverified, and it is not cash or runway.
- **Currency erratum:** a blank reporting currency gives owner reconciliation `not_comparable / profile_currency_unknown`.
- **Graded classes carried from memo 100 (`f17db5c`):**
  - OF-805: a page-12 source placed under page 10's context;
  - OF-806: a judgment from measurement ambiguity alone;
  - OF-807: analyst conditions attributed to the company.

**State mapping (unchanged):** `no_data` → INSUFFICIENT; `verified` → VERIFIED; `contradicted` → CONTRADICTED.

## Run record

| Item | Value |
|---|---|
| Date | 2026-10-18 local (UTC−7). Upload **04:46:32 UTC** (2026-10-19) |
| Code | **`066456341935d5ace32760a00788f78ec61a047a`**, "Merge pull request #286 …". Parents: `f34e3a3` and the final PR head `5937e51`; **0 files differ from `5937e51`**. `origin/main` was exactly `0664563` when fetched (no newer commits). No migrations since `f34e3a3`. Worktree `KCV-mc-066`, branch `docs/manychat-output-fidelity-0664563`, created clean. Server and worker each print `non_pyc_files_differing_from_0664563=0` |
| Deck | `manychat_series_a_audit_deck.pptx`, **175,622 bytes, SHA-256 `be7a7171…3ef1`**, matching the key before and after. **One upload** (ingest API, D-1) |
| IDs (all new) | **Document 3143**<br>Chunks: 12<br>Insights: 5193–5196<br>**Claims 2381–2384**<br>Entity Integrity **42**; Truth Delta **95**; **memo 101** |
| Database | A new SQLite backup copy, `scratchpad/r066/db_r066_copy.sqlite3`, from the original opened `mode=ro`; `integrity_check` ok. The gate refused it at `pending=1` (`zelda_api.0044`), and the migration was applied to the copy only. The wrapper refuses the original and all seven earlier run copies (memos 94–100). Sequences were advanced in the copy only, to the memo-100 copy's maxima (document 3142, memo 100, claim 2380, TD 94, EI 41) |
| Broker / cache | Local Memurai db **1** (broker), db **3** (results and cache). See D-8. Worker `mc066@inventoroftues`, queue `celery`, solo, concurrency 1. Every other Redis db is unchanged; nothing was purged |
| Gates (inside both processes) | Server pid 12564 and worker pid 21140 each report:<br>• the six paid keys `False`; `ANTHROPIC_API_KEY` `True`;<br>• broker local on db 1/1/3/3;<br>• `DB-CHECK is_copy=True is_original=False is_historical_copy=False`;<br>• `SCHEMA-CHECK pending=0` (zelda_api 0044, matchmaking 0095, accounts 0017, billing 0007);<br>• `CELERY_TASK_ALWAYS_EAGER=False`.<br>`preflight --local`: ok |
| Memory | `tools/memwatch.ps1` (1,500 MB threshold) **ran throughout**, started and verified before the first step; nothing crossed it. Free RAM was 1.6–2.0 GB; every step ran serially |
| Task order ([06](06_worker_chain.txt)) | 1. 2 fixture match refreshes.<br>2. `process_document_pipeline` (12 chunks, 4 insights).<br>3. `extract_claims_from_insights` (**4**).<br>4. `verify_entity_integrity` (42).<br>5. `verify_document_truth_delta` (95).<br>6. `generate_intelligence_memo` (**101**, 51.3 s).<br>7. `notify_document_processed` |
| Model calls | **8 in all**, all successful ([09c](09c_all_model_calls.json)):<br>• **1 memo generation** (worker, 04:46:38 UTC, `msg_011CgAzJTbee4vwx4LZDstnV`): `claude-sonnet-4-6`, `max_tokens` 4000, `end_turn`, 3,771 in / 2,398 out tokens;<br>• **7 `/ask/` query-extraction calls** (server), from Q1–Q7 run **once**.<br>No retry and no second generation. The browser walks made no call |
| Principals | `r66mc_owner` (321, Application 50); `r66mc_lite` (322); `r66mc_paid` (323, Premium plus an active local `INVESTOR_PREMIUM` subscription 9 with fake Stripe IDs, no payment action); `r66mc_staff` (324, real MFA setup in the probe and real verify in the Markdown check and Chrome); anonymous |
| Profile fixture | ManyChat; `prior_amount_raised=163000000`, `raising_amount=0`, revenue and reporting currency blank. Canary `CANARY-MANYCHAT-4417` in PRIVATE `reason_for_capital` |
| Preserved | Read-only snapshots are **byte-identical** before and after: memos 90/91 (with documents 3132/3133) in the original, and memos 94–99 and **100** (with document 3142) from their run copies. All eight source DB hashes and the deck hash are unchanged, with no sidecars. The original and 94–99 before-snapshots equal the memo-100 run's committed after-snapshots (`d8b224c`) after normalisation. The stored fields of memos 97, 98, 99 and **100** (24 each) equal their committed `09_memo.json` (`ea3ab13`, `0dd8e91`, `d821cca`, `d8b224c`) before and after |

### Deviations

- **D-1: ingest API upload.** As before.
- **D-2: repeated ID numbers.** Users 321–324, Application 50 and subscription 9 repeat earlier runs' numbers, as rows in a separate DB.
- **D-3: instrumentation.** In-process recording of `Messages.create`. No repo change, and no credentials recorded.
- **D-4: Chrome mechanics.** As before: `form.elements`, `requestSubmit()`, nav logout, and the next-window TOTP. The paid logout went through `/` (FF-413). The anonymous checks used in-page `fetch` with `redirect: manual`.
- **D-5: process stop.** Server and worker were stopped by exact PID; their shells report exit 1 because of that stop.
- **D-6: scan.** [scan_r066.py](scripts/scan_r066.py.txt) is the memo-100 scan plus four checks for this reply's shapes.
  - A first derivation turned `\b` into a backspace character in one new check, so it matched nothing. It was fixed and the scan rerun before any reading.
  - Scan hits are candidates for reading, not grades.
- **D-8: Redis databases.** **No Memurai db was empty** before this run, and none was purged.
  - **Used:** dbs 1 and 3 held only the three static `_kombu.binding.*` sets any Celery worker declares, with empty queues and no result or cache keys ([snapshots/redis_run_dbs_keys_before.txt](snapshots/redis_run_dbs_keys_before.txt)).
  - **Not used:** the cache dbs (7, 10, 12, 14, 15) held cached values, including `sec_identity_v3:manychat`, which could have short-circuited the EDGAR identity lookup.
  - **Sharing:** results and cache share db 3; their key prefixes cannot collide.
- **D-9: Chrome unreachable at first.** 21:51–21:53 local, the connected browser returned "connection refused" for the run server, as at the start of the memo-100 run. The run paused, the owner re-selected the browser (`/chrome`), and the walks then ran 21:55–21:58.
- **D-11: fixture tasks.** Two match-refresh tasks, as in the memo-100 run.

## Primary checks

### 1. Source facts and model input ([04](04_claims.json), [09a](09a_grounded_context_rebuilt.json), [09d](09d_memo_input_output_check.json))

The four claims are identical to the memo-100 and memo-99 runs:

| Claim | Page | Value | Notes | Chunk |
|---|---|---|---|---|
| `$23.1M raised` (2381) | p2 | — | narrator Pitch Deck Hunt | `c80948f9` |
| `500M messages/month` (2382) | p12 | — | monthly, `/month`, no period end, no context | `a6ff6361` |
| `500M messages` (2383) | p10 | — | no interval, `Traction by Apr-16` | `4981cd72` |
| `140 000+ bots` (2384) | p10 | — | `Traction by Apr-16` | `4981cd72` |

The sent payload equals the dump's rebuild and a fresh build, and equals memo 100's payload once document IDs are masked:
- **Basis note:** C3/C2.
- **Prompt rules:** 10 and 11 and the dated-runway rule are present.
- **Absent from the input:** the canary, the key's wording, fixture names and every review ID (UB-604, NP-603/604, OF-704/705, OF-805/806/807). The guards' output phrases are absent too.

### 2. What the guards did on the live reply

**PR #286's rules made no edit, and neither did the basis guard.** The single guard edit was a funding narrator insertion in a question ([09e](09e_guard_changes.txt)):

> "What is the intended use of the $23.1M listed **(per Pitch Deck Hunt)** as raised [S4], and when was this capital raised?"

All **17 stored fields equal the replay of the raw reply** through list normalisation, time, funding and basis. The replay is order-stable and idempotent, and citations stay in order.

**So the stored memo is the model's reply.** The defects below reached readers because their wordings are outside the merged rules' lexical scope, not because a rule misfired.

### 3. Grading against the frozen criteria

| Criterion | Reading | Evidence (stored = raw) |
|---|---|---|
| Page 10 no interval / page 12 monthly, each kept separate | **Mixed** | Correct in `risk_assessment` 1 ("page 10 (contextually within a 'Traction by Apr-16' slide heading) without an explicit time interval, and '500M messages/month' on page 12"), `open_concerns` 1, `information_readiness` ("500M messages [S2] within a 'Traction by Apr-16' slide context" / "500M messages/month [S3]") and `questions_for_management` 1. **Failed** in `business_model_analysis`, `upside_scenario`, `base_scenario` (OF-903, OF-904) |
| Page 10 not inferred cumulative | **Failed once** | `downside_scenario`: "the inconsistency between **the cumulative and monthly presentations** of the 500M messages figure" (OF-906). The other "cumulative" mentions are questions or alternatives ("a cumulative total or a monthly rate") |
| No contradiction or judgment from the two statements alone | **Failed once** | `risk_assessment` 1: "These figures carry different measurement bases and cannot be directly compared without clarification — **raising the possibility of metric inflation** or imprecise reporting" (OF-905). The headings say "inconsistency", not "contradiction" (OF-910) |
| No annualisation | **Pass** | none (`ra109_annualised_or_converted` 0) |
| Clarification sought | **Pass** | `questions_for_management` 1; `open_concerns` 1; `information_readiness` "Clarification of whether 500M messages is a cumulative total or a monthly rate" |
| OF-807: conditions not attributed to the company | **Pass** (did not recur) | `upside_scenario` keeps its conditions as "if"s and ends "Verification of these figures and disclosure of even a modest revenue base would substantially strengthen this reading"; `business_model_analysis`: "Whether these metrics reflect paying customers, free users, or a mix is not stated" |
| Facts, qualifications, conditions, questions and narrator preserved | **Pass** | the one guard edit adds a narrator; nothing was removed |
| April-2016 traction historical | **Pass** | "by that reference point"; "by the period referenced"; questions ask for current figures |
| $23.1M attributed, not current or verified | **Pass** | **32/32** sentences stating $23.1M across 51 surfaces name Pitch Deck Hunt; "no date is stated"; "not independently confirmed"; no cash or runway premise (`runway_or_cash_premise` 0) |
| Platform counts not user counts | **Pass** | no 900M/275M/100M anywhere |
| No SEC identity, revenue, external verification or advice | **Pass, with an RA-108 note** | Entity Integrity: SEC not found; revenue "not found"; no advice (the only `advice_words` hits are "Buy 3 Truth Delta credits" product copy). `zelda_advantage` says "**The verification process** identified …" (RA-108, OF-910) |
| Raw vs persisted | Shown | They are identical except the one narrator insertion ([09e](09e_guard_changes.txt)) |

## Verification, surfaces and boundaries

| Check | Result |
|---|---|
| Truth Delta 95 | 0 observations; all four claims "No external data found" (`no_data` → INSUFFICIENT); score None ("NOT SCORED · LIMITED PUBLIC EVIDENCE"); `dataforb2b: unconfigured` |
| Entity Integrity 42 | Website/domain/founder/founding-year "Not applicable"; SEC EDGAR "Not found". No identity invented |
| Note visibility | "Measurement basis to clarify" with "not a verification result" for owner, Lite, paid and staff (HTTP probe; paid and staff in Chrome). Anonymous: redirected |
| Authorization ([11](11_authorization_matrix.json)) | **All 90 principal × surface rows identical to the memo-100 run.** Every logout POST returns 302 and the protected profile then redirects |
| Reconciliation ([11b](11b_reconciliation_by_principal.json)) | Owner only: `not_comparable / profile_currency_unknown` |
| Canary | Only on the owner's and staff's profile page; never in model input, memo, reports or Chrome-read pages |
| Markdown ([14](14_markdown_utf8.json)) | `text/markdown; charset=utf-8`; **11,832 bytes; SHA-256 `3bf7a7ce0fd8880d2c2c7da894d75caf712f3cc52f48e1cf1a0bc8a4afe900dd`**; strict UTF-8; 24 `•`, 28 `—`; no mojibake |
| Q1–Q7 ([10](10_retrieval_ask_q1_q7.json)) | Run **once**. Owner search and RAG 200, near-uniform relevance; Q3's top pages are 10 and 12. `/ask/` 200 ×7, each the marketplace fallback "I couldn't find specific search criteria in that — …" (**RA-114 unchanged; not document answers**) |
| Chrome ([15](15_browser_walks.json), [browser/](browser/)) | Owner, Lite, paid, staff (real MFA) and anonymous, each with a positive control; nav logout, then refusal. The staff full memo shows OF-905, OF-906 and OF-904; the owner's memo shows OF-903 |

## Ledger

| ID | Layer | Principal | Observation | Key ref | Grade | Bucket | Sev | Blocking |
|---|---|---|---|---|---|---|---|---|
| OF-901 | 3–5 | all | Four expected claims identical to the memo-100 run; count and rate distinct; no platform counts; no invented period end | M2–M6 | PASS | — | — | No |
| OF-902 | 9 | model input | Request = rebuild = fresh build = memo-100 payload (doc IDs masked). Note C3/C2; rules present; no key, review, guard or canary text | M6 / I1 | PASS | — | — | No |
| OF-903 | 9 | all memo readers (owner Lite sections, staff, Markdown) | `business_model_analysis`: "the company states 140,000+ bots [S1] and 500M messages (with an ambiguity in measurement basis between a cumulative total and a monthly rate **[S2, S3]**) **in a slide context headed 'Traction by Apr-16'**". The page-12 monthly source is placed under page 10's context, and both sources fold into one "500M messages". PR #286's context rule acts only on a *parenthesised* context aside after the citations, so this wording (S3 inside the ambiguity parenthesis, the context unparenthesised) is outside it. No guard edit | M6 / OF-805 | **FAIL: OF-805 class recurred in new wording** | PHASE1-GROUNDING | P2 (provisional) | Yes for RA-109 |
| OF-904 | 9 | staff, Markdown | `upside_scenario`: "If the self-reported figure of 500M messages/month [S3] reflects a monthly run-rate **as of the 'Traction by Apr-16' slide context**". `base_scenario`: "Taking the self-reported traction metrics at face value **[S1, S2, S3]**, ManyChat had built … **by the period referenced in the 'Traction by Apr-16' slide context**". The page-12 figure is given page 10's date context (in a condition in the upside, asserted in the base) | M6 / OF-805 | **FAIL: OF-805 class** (base asserted; upside conditional) | PHASE1-GROUNDING | P2 (provisional; upside P2/P3) | Yes for RA-109 |
| OF-905 | 9 | staff, Markdown | `risk_assessment` 1: "These figures carry different measurement bases and cannot be directly compared without clarification — **raising the possibility of metric inflation or imprecise reporting**." A judgment (inflation) from measurement ambiguity alone. "These figures" is not one of the referents the OF-806 rule resolves ("one or both figures", "the figures"), so the sentence resolves to no pair and no judgment rule acts | M6 / OF-806 | **FAIL: OF-806 class recurred in new wording** | INTEL-QUALITY | P2 (provisional) | Yes for RA-109 |
| OF-906 | 9 | staff, Markdown | `downside_scenario`: "If the inconsistency between **the cumulative and monthly presentations** of the 500M messages figure [C2, C3] reflects imprecise metric reporting …". The noun phrase presupposes that page 10 is a cumulative presentation, which nothing admitted supports. The basis guard's referent rule matches "the cumulative figure/total/count/…", not this phrase | M6 / UB-604 | **FAIL: UB-604 class (cumulative presupposed)** | PHASE1-GROUNDING | P2 (provisional) | Yes for RA-109 |
| OF-907 | 9 | Lite (overview), staff | `executive_summary`: "140,000+ bots and 500M messages, both as self-reported and as yet externally unverified **[S1, S2, S3]**". `risk_assessment` 5: "the 500M messages figure **[S2, S3]**". Both message sources are cited for one "500M messages" with no place claimed. Less severe than OF-903: no context or date is misattached | M6 | Merged citation; for grader | PHASE1-GROUNDING | P3 (provisional) | No |
| OF-908 | 9 | staff | **OF-807 did not recur.** The upside conditions ("if a meaningful share of the 140,000+ bots [S1] belong to paying businesses") stay hypotheses, with no company attribution; `business_model_analysis` states that paying status is not stated | M5 / OF-807 | PASS (non-recurrence; the rule was not exercised) | — | — | No |
| OF-909 | 9 | all | Funding: 32/32 $23.1M sentences name Pitch Deck Hunt; undated, unverified; no total, possessive or cash premise; one guard narrator insertion. **P3:** a question asks the "intended use of the $23.1M … raised", presupposing it is deployable capital | M1 / NP-603, NP-604 | PASS; question wording P3 | INTEL-QUALITY | P3 | No |
| OF-910 | 9 | staff | Wording: "**Measurement inconsistency** on a key traction metric" (`risk_assessment` 1) and "this **inconsistency**" (`open_concerns` 1), less precise than ambiguity. `supported_points`: "500M messages **delivered**" (UB-607 shape). `zelda_advantage`: "**The verification process** identified …" (RA-108 recurrence; credits verification) | M6 | Observations | INTEL-QUALITY | P3 | No |
| OF-911 | 10 | all | Truth Delta: 0 observations, 4 INSUFFICIENT, score N/A. The note is visible to owner, Lite, paid and staff with "not a verification result". Entity Integrity: SEC not found | E1, M1–M6 | PASS | — | — | No |
| OF-912 | 9–10 | all | 90-row matrix identical to memo 100; owner-only reconciliation; canary boundaries; UTF-8 Markdown; Chrome walks with positive controls and logouts | M1 | PASS | — | — | No |
| OF-913 | 9 | owner | `/ask/` 200 ×7 marketplace fallbacks: not document answers | Q1–Q7 | RA-114 open | PRODUCT-UI | — | No (separate) |
| OF-914 | 9 | — | Guard coverage: PR #286's rules (context split, referent judgment, condition attribution) and the earlier basis rules made **0 edits** on this reply. Each failing shape is a new wording outside a lexical rule. `basis_facts` built from reversed items is again not equal as an object; the output is identical (OF-815 carried) | — | Observation | CORRECTNESS | P3 | No |
| OF-915 | — | — | Unchanged and **not closed by this run**: RA-108 (OF-910), RA-114 (OF-913), RA-103, FF-413, RA-105, PF-206/FF-311, NP-508/509, P3 basis-note rounding; slash citations not recognised by `_REF` | — | Open | — | — | No |

No defect was repaired during the run, and no isolation or data-integrity problem occurred.

## Summary

At merged `0664563`, one live generation (**memo 101**, document 3143):
- **Input:** identical to memo 100's.
- **Held:** OF-807 did not recur, and the funding, historical-date, platform-count, identity, advice, verification-state and authorization criteria all hold.
- **Measurement basis failed in new wordings:** none was corrected, because the merged rules are lexical and these shapes are outside them.
  - **OF-903, OF-904:** the page-12 monthly source is placed under or dated by page 10's "Traction by Apr-16" context.
  - **OF-905:** "raising the possibility of metric inflation".
  - **OF-906:** "the cumulative and monthly presentations".
- **Run's reading:** this sample does **not** meet the RA-109 output criteria. Acceptance remains pending independent review.

## Artifacts

- [00](00_setup.json): setup, gates, isolation, Redis (with the run dbs' keys before), sequences, DB hashes, preservation, frozen-artifact checks, model calls.
- [01](01_extraction.json)–[09](09_memo.json): pipeline rows.
- [09a](09a_grounded_context_rebuilt.json)–[09f](09f_section_scan.txt): rebuild, the memo model call (raw reply), all 8 calls, input/output and four-step replay, guard edits, sentence scan.
- [10](10_retrieval_ask_q1_q7.json), [11](11_authorization_matrix.json), [11b](11b_reconciliation_by_principal.json), [12](12_api_payloads.json), [13](13_rendered_reports_text.json): HTTP probe.
- [14](14_markdown_utf8.json) and [14_ic_memo_export.md](14_ic_memo_export.md): Markdown export.
- [15](15_browser_walks.json) and [browser/](browser/): Chrome.
- [16](16_probes.json): numeric-parse probes.
- [process/](process/), [scripts/](scripts/), [snapshots/](snapshots/).
