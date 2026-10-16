# ManyChat — output-fidelity Pass A ledger at `64f9db5`

**A new, separate live run after PR #284.** It edits or replaces no earlier record:
- earlier runs: documents 3129, 3133, 3136–3140 and memos 91, 94–98;
- the memo-97 grading (`narrator-provenance-b9cddec/pass-a/`);
- the memo-98 run and grading (`usage-basis-d276918/pass-a/` at `feeb0c7` on `docs/manychat-usage-basis-d276918`);
- the output-fidelity review evidence (`three-deck-audit/output-*`);
- the frozen answer key and protocols, unchanged ([00](00_setup.json) `frozen_artifacts`).

Graded against the frozen [../../ANSWER_KEY.md](../../ANSWER_KEY.md) under [../../../three-deck-audit/PROTOCOL.md](../../../three-deck-audit/PROTOCOL.md) and [../../../nike-fy2026/PROTOCOL.md](../../../nike-fy2026/PROTOCOL.md). The key was used for grading only; none of its text, nor any fixture, review-finding or guard-output text, reached the model ([09d](09d_memo_input_output_check.json) `absent_from_model_input`).

**Status: ungraded.** These are the run's own readings, for independent grading.
- **RA-109:** live output acceptance stays **pending** until that grading.
- **RA-106:** its scoped acceptance (memo-97 grading) is unchanged.
- **Still open:** RA-108 and overall Zelda hardening.
- **Not done:** nothing was deployed, paid-source Pass B was not run, and no application code was changed.

## Key interpretations carried forward (additive; the key is not edited)

- **M6 / I1 (messages basis):** page 10 states **500M messages with no explicit interval**; page 12 states **500M messages/month**. The expected behaviour is to keep both, ask for clarification, and not label page 10 cumulative, annualise, or declare an error or contradiction from equal numbers alone.
- **Currency erratum:** a blank reporting currency gives owner reconciliation `not_comparable / profile_currency_unknown`, not the key's `differs`.
- **RA-106:** memo 97's scoped acceptance stands. Memo 98 was a partial pass (UB-604, NP-603 and the funding-as-runway part of NP-604 required correction); those grades are not reset here.

**State mapping (unchanged):** `no_data` → INSUFFICIENT; `verified` → VERIFIED; `contradicted` → CONTRADICTED. The basis note is not a state.

## Run record

| Item | Value |
|---|---|
| Date | 2026-10-16 local (UTC−7). Upload 09:26:55 UTC |
| Code | **`64f9db5286213e9d7f38dce6aab170bd26a15cc2`**, "Merge pull request #284 …". Parents: d276918 and the final PR head 6234627; **0 files differ from 6234627**. origin/main was exactly 64f9db5 when fetched. No migrations since d276918. Worktree `KCV-mc-of`, branch `docs/manychat-output-fidelity-64f9db5`. Server and worker each print `non_pyc_files_differing_from_64f9db5=0` |
| Deck | `manychat_series_a_audit_deck.pptx`, **175,622 bytes, SHA-256 `be7a7171…3ef1`**, matching the key. **One upload** (ingest API, D-1) |
| IDs (all new) | **Document 3141** (`analyzed`, `complete`)<br>Chunks: 12<br>Insights: 5185–5188<br>**Claims 2373–2376**<br>Entity Integrity **40**; Truth Delta **93**; **memo 99** |
| Database | A new SQLite backup copy, `scratchpad/of/db_of_copy.sqlite3`, made with the backup API from the original opened `mode=ro`; `integrity_check` ok. The gate refused it at `pending=1` (`zelda_api.0044`); the migration was applied to the copy only.<br>The run wrapper refuses the original and all five earlier run copies (memos 94–98).<br>ID sequences were advanced in the copy only, to the memo-98 copy's maxima (read `mode=ro`): document 3140, memo 98, claim 2372, TD 92, EI 39 ([snapshots/sequences.txt](snapshots/sequences.txt)) |
| Broker / cache | Local Memurai db **1** (broker), **4** (results), **7** (cache). Each was empty with no clients before the fixtures. Db 7 had been the memo-97 run's result backend; dbs 1 and 4 were unused by earlier runs. Worker `mcof@inventoroftues`, queue `celery`, solo, concurrency 1. Every other Redis db is unchanged; nothing was purged |
| Gates (inside both processes) | Server pid 9100 and worker pid 4044 each report:<br>• six paid keys `False`: `FILED_API_KEY`, `COMPANYENRICH_API_KEY`, `NEWS_API_KEY`, `DATA4B2B_API_KEY`, `USPTO_ODP_API_KEY` (read by no code at 64f9db5; blanked anyway), `CRUNCHBASE_API_KEY`;<br>• `ANTHROPIC_API_KEY` `True`;<br>• broker local on db 1/1/4/7;<br>• `DB-CHECK is_copy=True is_original=False is_historical_copy=False`;<br>• `SCHEMA-CHECK pending=0`, heads zelda_api 0044, matchmaking 0095, accounts 0017, billing 0007;<br>• `CELERY_TASK_ALWAYS_EAGER=False`.<br>`preflight --local`: ok |
| Memory | `tools/memwatch.ps1` (1,500 MB threshold) ran throughout; nothing crossed it. Free RAM was about 1.5 GB, so every step ran serially. No tests or mutations ran alongside the live run |
| Task order ([06](06_worker_chain.txt)) | 1. 3 fixture match refreshes.<br>2. `process_document_pipeline` (12 chunks, 4 insights).<br>3. `extract_claims_from_insights` (**4**).<br>4. `verify_entity_integrity` (40).<br>5. `verify_document_truth_delta` (93).<br>6. `generate_intelligence_memo` (**99**, 52.9 s).<br>7. `notify_document_processed` |
| Model calls | **8 in all** ([09c](09c_all_model_calls.json) `order`):<br>• **1 memo call** (worker, call 1, `msg_011Cg5gF…`): `claude-sonnet-4-6`, `max_tokens` 4000, `end_turn`, 3,771 in / 2,516 out tokens;<br>• **7 `/ask/` query-extraction calls** (server, calls 2–8) from the Q1–Q7 probe.<br>No retry and no second generation. The browser walks made no model call |
| Principals | `ofmc_owner` (321, Application 50); `ofmc_lite` (322); `ofmc_paid` (323, Premium plus an active local `INVESTOR_PREMIUM` subscription 9 with fake Stripe IDs `cus_of_local_mc` / `sub_of_local_mc`, no payment action); `ofmc_staff` (324, real staff-MFA setup by the probe, real verify in the probe, the Markdown check and Chrome); anonymous |
| Profile fixture | ManyChat; `prior_amount_raised=163000000`, `raising_amount=0`, revenue blank, reporting currency blank. Canary `CANARY-MANYCHAT-4417` in PRIVATE `reason_for_capital` |
| Preserved | Read-only snapshots (`PRAGMA query_only`) of memos 90/91 (with documents 3132/3133) in the original, 94, 95, 96, 97 and **98** (with document 3140, from the memo-98 run copy) are **byte-identical** before and after. All six source DB hashes and the deck hash are unchanged; no source DB has a sidecar.<br>The original/94/95/96/97 before-snapshots equal the memo-98 run's committed after-snapshots (`0dd8e91`) once carriage returns and lines starting `Invalid line` (a startup `.env` warning) are removed.<br>Memo 97's 24 stored fields equal its committed `09_memo.json` (`ea3ab13`), and memo 98's 24 equal its committed `09_memo.json` (`0dd8e91`), before and after |

### Deviations

- **D-1: ingest API upload.** As before; the only UI intake leads to Stripe checkout or credit redemption.
- **D-2: repeated ID numbers.** User IDs 321–324, Application 50 and subscription 9 repeat earlier runs' numbers, as separate rows in a separate DB.
- **D-3: instrumentation.** In-process recording of `Messages.create` in the run wrapper; no repo change, no credentials recorded.
- **D-4: Chrome mechanics.** As before: fields set on `form.elements`, then `requestSubmit()`; logout by the nav form's button. The staff TOTP was computed for the next 30-second window and submitted after it began. The Truth Delta page has no site nav (FF-413), so logout went through `/`. The anonymous checks of three URLs were in-page `fetch` with `redirect: manual`. The Lite login landed on the owner profile first (the login `next=` redirect overtook the scripted navigation) ([15](15_browser_walks.json)).
- **D-5: process stop.** Server and worker were stopped by exact PID; the background shells report exit 1 because of that stop.
- **D-6: scan ref sets.** The inherited sentence scan hard-coded the memo-97 ref mapping; this run's [scan_of.py](scripts/scan_of.py.txt) reads the usage refs (C2, C3, C4, S1–S3) and funding refs (C1, S4) from the sent payload. Checks were added for this run's shapes. Scan hits are candidates, not grades.
- **D-7: replay harness.** The inherited replay omitted the basis guard. [analyze_of.py](scripts/analyze_of.py.txt) (derived by [make_scripts2.py](scripts/make_scripts2.py.txt)) replays all four steps in the merged order, with funding facts and per-pair basis facts built from the actual context.

## Primary checks

### 1. Source facts and normalized input ([02](02_chunks.json)–[04](04_claims.json), [09a](09a_grounded_context_rebuilt.json), [09d](09d_memo_input_output_check.json))

| Source | Claim | Value | Unit | Ownership / narrator | Period fields | Context | Chunk |
|---|---|---|---|---|---|---|---|
| p2 | `$23.1M raised` (2373) | 23,100,000 | (none), currency blank | named / **Pitch Deck Hunt** | none | — | `c80948f9…` |
| p10 | `140 000+ bots` (2376) | 140,000 | `bots` | implied / none | none | `Traction by Apr-16` | `4981cd72…` |
| p10 | `500M messages` (2375) | 500,000,000 | `messages` | implied / none | **none** | `Traction by Apr-16` | `4981cd72…` |
| p12 | `500M messages/month` (2374) | 500,000,000 | **`messages/month`** | implied / none | `period_kind` monthly, `time_period` `/month`, **no `period_end`, no fiscal year** | none | `a6ff6361…` |

**PASS:**
- **The expected set:** four claims, with values, units and chunk hashes identical to the memo-98 run.
- **Bots:** the repeated count dedupes.
- **The two 500M figures:** the count and the rate stay distinct.
- **No unwanted rows:** no platform-user claim, and no invented period end on the monthly rate.

**Payload:** the sent request equals both the dump's rebuild and a fresh `GroundedContext.build` for the generation principal (owner 321, `ORIGIN_TASK`). The refs are the same as the memo-98 run:

| Ref | Item |
|---|---|
| C1 | funding, Pitch Deck Hunt, `dates_not_as_of ["2015"]` |
| C2 | `500M messages/month`, p12, no context |
| C3 | `500M messages`, p10, `Traction by Apr-16` |
| C4 | `140 000+ bots`, p10 |
| S1 | bots |
| S2 | `500M messages` |
| S3 | `500M messages/month` (no context) |
| S4 | funding, Pitch Deck Hunt |
| P1, P2 | profile stage and sector |

- **`consistency_notes`**, identical in the request and the rebuild: `measurement_basis`, refs **C3, C2**, "Page 10 states 500M messages without an explicit interval; page 12 states 500M messages/month. These use different measurement bases and need clarification before comparison."
- **Prompt:** rule 11 is present and the user prompt points to it; rule 10 and the dated-runway rule are present. `time_wording_allowed` is empty for every dated item.
- **Absent from the input:** the canary; 163,000,000; Bessemer, TechCrunch and Summit Partners; 2019, $18M and $140M; the founders; the key's wording; the fixture names; the review IDs; and the guards' output phrases.
- **Basis facts** built from this context: one pair, refs C3/C2, members C2, C3, S2, S3, noun `messages`, no cumulative fact. They are identical when built from the reversed item list.

### 2. Measurement-basis output (UB-604)

**The former shape did not recur, so the guard was not exercised.** In the raw reply, the stored memo and every captured surface, there is no "the cumulative figure", no "overstated", no annualisation and no merged or verified 500M ([09f](09f_section_scan.txt): `ra109_cumulative_asserted` 0, `ra109_annualised_or_converted` 0; staff Chrome 0 and 0). The basis guard made **0 edits**, both live ([06](06_worker_chain.txt)) and on replay.

| Section | Text (stored = raw reply) | Reading |
|---|---|---|
| `risk_assessment` 1 | "the deck presents '500M messages' without an explicit interval on page 10 (slide headed 'Traction by Apr-16') [C3, S2] and '500M messages/month' on page 12 [C2, S3]. These use different measurement bases; until clarified, the headline usage figure cannot be read with confidence." | Both bases, correct pages and refs, clarification; no label, no judgment |
| `executive_summary` | "… 140,000+ bots and 500M messages … [S1, S2], though the measurement basis for the messages figure requires clarification (see open concerns)." | Flags the basis |
| `open_concerns` 1 | "**Measurement-basis contradiction** in the headline usage metric: the deck states '500M messages' without an interval on page 10 and '500M messages/month' on page 12 [C2, C3]. These are not necessarily the same figure; until management clarifies whether 500M is a cumulative total or a monthly rate, …" | Correct facts and a clarification request, under an unsupported "contradiction" label (**OF-704**) |
| `supported_points` 2 | "… a messages figure of either 500M total or 500M/month (measurement basis unresolved; see open concerns) **on the same traction slide [S2, S3]** …" | S3 is page 12, not the traction slide (**OF-705**); "500M total" is offered as one alternative |
| `business_model_analysis` | "… 140,000+ bots and 500M messages (measurement basis questioned; see open concerns) on a slide headed 'Traction by Apr-16' **[S1, S2, S3]** …" | Cites S3 for the page-10 slide (**OF-705**) |
| `information_readiness` | "A second messages figure of 500M/month stated elsewhere in the deck [S3]"; "Measurement basis of the 500M messages figure (total vs. per month) [C2, C3]" | Correct location; "total" P3 |
| `upside` / `downside_scenario` | "If the 500M figure is confirmed as a monthly message rate [S3] rather than a cumulative total …"; "If the 500M messages figure is a cumulative total rather than a monthly rate [C2, C3] …" | Conditional both ways; preserved |
| `questions_for_management` 1 | "Is the '500M messages' figure on the traction slide a cumulative total or a monthly rate? Please reconcile with the '500M messages/month' figure stated elsewhere in the deck [C2, C3]." | A proper question, correct locations |
| `zelda_advantage` | "The **structured extraction** identified a specific **internal inconsistency** between two uses of the same metric … a measurement-basis ambiguity that a plain AI summary would likely present as a single confirmed figure …" | RA-108 self-comparison recurs; credits extraction, not verification (**OF-711**) |

**Guard safety on this reply:**
- **No foreign citation:** the guard never attached another pair's facts or citations; there is only one pair.
- **No unrelated metric rewritten:** zero basis edits.
- **No synthetic sentences injected:** that coverage stays with the accepted deterministic regressions.

### 3. Funding narrative and total (NP-603)

- **Narrator on every amount sentence:** all **49 sentences stating $23.1M across 51 surfaces** name Pitch Deck Hunt (`funding_sentence_missing_narrator` 0); the staff Chrome memo has 10 of 10.
- **Wording:** no "total amount raised", and no "fundraising narrative the company has put forward".
- **Pitch Deck Hunt:** never credited with bots or messages (the `narrator_with_traction_*` hits are sentences that list both items with their own subjects: "the company states 140,000+ bots … and $23.1M raised as listed by Pitch Deck Hunt").
- **The model's own provenance sentence:** "the $23.1M figure originates from Pitch Deck Hunt as narrator rather than from the company's own slide text [C1, S4]" is accurate.
- **Remaining clauses, for grading (OF-706):**
  - **`questions_for_management`:** "The deck is listed with $23.1M raised (per Pitch Deck Hunt) [S4]: what rounds make up **this total** …". The question presupposes an aggregate. The `unsupported_total` rule handles statements of "the total amount raised", and questions are skipped by design.
  - **`what_would_change_the_picture`** (after the guard): "since **its reported funding** is historical funding, not cash on hand [S4]". The possessive names no narrator in that clause.
  - **Guard insertions:** "$23.1M raised (per Pitch Deck Hunt) (undated, unverified [C1])" in `downside_scenario` doubles a parenthetical. "(per Pitch Deck Hunt)" repeats the narrator after "listed" in the question.

### 4. Funding is not operating cash (NP-604)

**The guard was exercised and corrected the raw reply twice** ([09e](09e_guard_changes.txt)):

| Section | Raw reply | Stored |
|---|---|---|
| `risk_assessment` 5 (`cash_premise`) | "… leaving capital structure and **remaining runway** unknown." | "… leaving capital structure and runway (which needs a dated cash balance and burn rate; neither is in the evidence) unknown." |
| `what_would_change_the_picture` (`funding_not_runway`) | "… and how long the company can operate **on its reported funding [S4]**." | "… and how long the company can operate — from the dated cash and burn alone, since its reported funding is historical funding, not cash on hand [S4]." |

**Other mentions:**
- **Stored text:** no funding amount is a cash or runway denominator anywhere in it (`runway_or_cash_premise` 0).
- **Financial analysis:** "Runway: Cannot be calculated — no dated cash balance or burn rate".
- **Questions:** they ask for "the current monthly cash burn, and … the dated cash balance on hand", and separately what rounds and when.
- **`open_concerns` 3:** "how long the company can operate without additional funding" uses no denominator.
- **P3, missing-information shape (as in memo 98):** `downside_scenario`'s conditional "the $23.1M raised … may have been deployed largely to acquire a large free-user base".

### 5. Full transformation replay ([09d](09d_memo_input_output_check.json), [09e](09e_guard_changes.txt))

All **17 stored fields equal the replay of the raw reply** through the merged order: list normalisation, then the time guard (with the recorded `time_wording_allowed`, all empty), then the funding guard, then the basis guard. Funding facts and per-pair basis facts were built from the actual context.

| Check | Result |
|---|---|
| Reversed item order (facts and basis facts) | Same output for every field |
| Second pass over the stored text | No change and no rule fired |
| Citations | Same refs in the same order in every field |
| Time guard | Removed nothing |
| Funding guard | 5 edits: `cash_premise` (risk), `funding_not_runway` (`what_would_change_the_picture`), `attribution:Pitch Deck Hunt` ×3 (`information_readiness`, `downside_scenario`, `questions_for_management`) |
| Narrator-provenance rule, unsupported-total rule, basis guard | Did not fire |

**Did not recur** (the raw reply already avoided the shape):
- UB-604's cumulative label and overstatement;
- NP-603's "total amount raised" and company-narrative wording.

**Guard exercised and corrected:**
- NP-604's funding-as-runway clause and "remaining runway";
- three missing-narrator insertions.

## Verification, surfaces and regression boundaries

| Check | Result |
|---|---|
| Truth Delta ([07](07_truth_delta_reports.json), [05](05_observations.json)) | 0 observations; all four claims `no_data` (INSUFFICIENT); 0 verified, 0 contradicted; `overall_truth_score` None ("N/A", "NOT SCORED · LIMITED PUBLIC EVIDENCE"). The note manufactured no state and no score. `provider_outcomes` `dataforb2b: unconfigured` (keyless); SEC `not_found` |
| Entity Integrity 40 ([08](08_entity_integrity.json)) | Website/domain/founder/founding-year checks "Not applicable" (no website on the profile); SEC EDGAR "Not found". No non-EDGAR provider returned data |
| Note visibility | Truth Delta page, "Measurement basis to clarify" block with "This is not a verification result and doesn't affect the score." for **owner, Lite, paid and staff**. Staff reached it by direct navigation after real login and MFA. Anonymous: redirected |
| IC memo | Owner (Lite sections): distinction in `business_model_analysis`, `information_readiness`, `supported_points`, `open_concerns`, `what_would_change_the_picture`. Staff (full) and Markdown: the full memo. Lite/paid: 404, as before |
| Memo API | Lite, paid, staff carry the distinction (`messages/month`, `cumulative`, `monthly`); owner `locked`, as before |
| Company overview | **Lite and paid now carry a basis flag** ("the measurement basis for the messages figure requires clarification (see open concerns)"). They do not carry the monthly figure, and "open concerns" is not on that surface (UB-606 partly changed; **OF-709**). Staff overview, "Worth investigating" panel: quotes "Measurement-basis contradiction in the headline usage metric …" beside the Truth Delta counts (**OF-704**) |
| Counts, lists, citations | "(of 4)", "none of the 4 claims", 4/0/4; lists render; citations unchanged by the guard edits |
| Markdown ([14](14_markdown_utf8.json)) | `text/markdown; charset=utf-8`; **11,755 bytes; SHA-256 `58e596bf121955c9a14179970213485cbd50dd19c5c3ec0c6143dd95a99194b5`**; strict UTF-8; 20 `•`, 22 `—`; the reader's text equals the strict decode; no mojibake or replacement characters |
| Q1–Q7 ([10](10_retrieval_ask_q1_q7.json)) | Owner search/RAG 200 with near-uniform relevance; Q3's top pages are 10 and 12; `/ask/` returns the marketplace query-extraction message for all seven (**RA-114 unchanged**) |
| Authorization ([11](11_authorization_matrix.json)) | **All 90 principal × surface rows identical to the memo-98 run** (status, redirect, owner panel, canary). Logout POST 302 for every signed-in principal; the protected profile then redirects to login |
| Reconciliation ([11b](11b_reconciliation_by_principal.json)) | Owner only (staff `[]`): `not_comparable / profile_currency_unknown` |
| Canary | Only on the owner's and staff's profile page (`A_profile`); never in model input, memo, reports or other surfaces. The Lite view of the profile shows "Private" |
| Historical context | "Traction by Apr-16" is kept as slide context. Funding is undated ("no date is stated"). No current total, live raise, cash balance or "as of April 2016" assertion. The questions ask whether a new round is being raised; they do not assert one |
| Browser walks ([15](15_browser_walks.json), [browser/](browser/)) | Real Chrome for owner, Lite, paid, staff and anonymous. Each navigation is in the server log; nav logout POST 302; protected routes refused afterwards |

## Ledger

| ID | Layer | Principal | Observation | Key ref | Grade | Bucket | Sev | Blocking |
|---|---|---|---|---|---|---|---|---|
| OF-701 | 3–5 | all | Four expected claims: values, units, pages and chunk hashes identical to the memo-98 run; count and rate distinct; bots deduped; no platform counts; no invented period end | M2–M6 | PASS | — | — | No |
| OF-702 | 9 | model input | Request = dump rebuild = fresh build. Basis note C3/C2 with the real refs; rules 10/11 and the dated-runway rule present; no key, fixture, review or canary text. Basis facts: one pair, members C2/C3/S2/S3 | M6 / I1 | PASS | — | — | No |
| OF-703 | 9 | all memo readers | **UB-604 did not recur.** `risk_assessment` states both bases with correct refs and asks for clarification; no cumulative label, overstatement, annualisation or merge anywhere; conditional scenarios and the management question preserved. Basis guard: 0 edits (not exercised) | M6 / UB-604 | PASS on recurrence (for grader); the guard's live correction is not shown by this sample | — | — | No |
| OF-704 | 9–10 | Lite (memo sections), staff (memo, overview), Markdown | `open_concerns` 1 heads the basis question "**Measurement-basis contradiction** in the headline usage metric", although its next sentence says "not necessarily the same figure" and asks for clarification. Rule 11 says equal numbers on different bases are not a contradiction. The staff overview's "Worth investigating" panel repeats it beside "Contradicted — 0". `zelda_advantage` says "internal inconsistency". The basis guard's judgment vocabulary does not cover "contradiction" (lexical scope) | M6 | Unsupported label; for grader | INTEL-QUALITY | P2 (provisional) / P3 | No |
| OF-705 | 9 | all memo readers | `supported_points` 2 places both figures "**on the same traction slide [S2, S3]**", and `business_model_analysis` cites S3 for the slide headed 'Traction by Apr-16'. S3 / C2 (500M messages/month) is on page 12 with no slide context, and the payload states that. Other sections place it correctly ("stated elsewhere in the deck", "page 12") | M6 | Source-location error; for grader | PHASE1-GROUNDING | P2 (provisional) / P3 | No |
| OF-706 | 9 | staff, Lite (`what_would_change_the_picture`) | NP-603 shapes absent from statements: Pitch Deck Hunt names all 49 $23.1M sentences across 51 surfaces; no "total amount raised" or company-credited narrative. Remaining: a management question asks "what rounds make up **this total**" (presupposes an aggregate; the rule skips questions); "**its reported funding**" (possessive, no narrator in the clause) in the guard-corrected sentence; doubled parentheticals from guard insertions | M1 / NP-603 | PASS on statements; question/possessive wording for grader | INTEL-QUALITY | P3 (provisional) | No |
| OF-707 | 9 | Lite, staff | **NP-604 recurred in the raw reply and the guard corrected it**: "how long the company can operate on its reported funding [S4]" → `funding_not_runway`; "remaining runway" → `cash_premise`. The stored memo uses no funding amount as a cash or runway denominator; questions ask for dated cash and burn. `downside_scenario`'s conditional "may have been deployed" stays a missing-information shape | M1 / NP-604 | PASS (guard exercised); deployment wording P3 | — | P3 | No |
| OF-708 | 10 | all | Truth Delta: 0 observations, 4 INSUFFICIENT, score N/A; the note is visible to owner/Lite/paid/staff with its "not a verification result" text and changes no state or score | — | PASS | — | — | No |
| OF-709 | 10 | Lite, paid | The company overview now carries "the measurement basis for the messages figure requires clarification (see open concerns)". It does not show the monthly figure, and its "see open concerns" points to a section that surface does not show (Investment analysis is locked) | M6 / UB-606 | Surface coverage, improved; observation | PRODUCT-UI | P3 | No |
| OF-710 | 9–10 | all | Counts, lists, citations, UTF-8 Markdown, the 90-row authorization matrix (identical to memo 98), owner-only reconciliation, canary boundaries and Q1–Q7 all hold | M1 | PASS | — | — | No |
| OF-711 | 9 | staff | `zelda_advantage` again compares itself with an unmeasured "plain AI summary". This time it credits "the structured extraction", not a verification process | — | RA-108 recurrence (wording more accurate) | INTEL-QUALITY | P3 | No |
| OF-712 | 9 | all | UB-607 ("deployed"/"processed") and UB-608 (Facebook Messenger) did not recur. `executive_summary` states the company is "operating in the chatbot/messaging automation space", which `problem_solution` marks as inferred from the metrics | — | Observation | PHASE1-GROUNDING | P3 | No |
| OF-713 | — | — | Unchanged and **not closed by this run**: RA-108 (OF-711), RA-103 (funding claim from the audit-framing slide 2), FF-413 (unstyled Truth Delta page, no site nav), RA-114 (`/ask/`), RA-105 (currency), PF-206/FF-311 (Section Coverage 31.2% vs 100%), NP-508/509, P3 basis-note rounding | — | Open | — | — | No |

No defect was repaired during the run, and no isolation or data-integrity problem occurred.

## Summary

At merged `64f9db5`, one live generation (**memo 99**, document 3141):
- **Extraction and normalised input:** identical to the accepted memo-98 run, including the C3/C2 basis note.
- **Measurement basis:** the model kept the two bases distinct and asked for clarification, without the former "cumulative figure … materially overstated" shape. The basis guard had nothing to correct, so this sample shows **non-recurrence, not a live guard correction**.
- **Funding as cash:** the raw reply did reuse the funding as the runway basis ("operate on its reported funding"), and the merged funding guard **corrected it**, as well as an unsupported "remaining runway".
- **Funding narrator:** every funding amount keeps its narrator.

**For grading:**
- **OF-704:** a new unsupported "Measurement-basis contradiction" label, on staff and Lite-section surfaces.
- **OF-705:** a page-12 figure placed on the page-10 traction slide.
- **Residual funding wording:** a question's "this total" and the possessive "its reported funding" (OF-706).
- **Lite/paid overview:** now carries a basis flag, but not the monthly figure (OF-709).

**RA-109 live output acceptance stays pending until independent grading.** RA-106's scoped acceptance is unchanged; RA-108 and overall hardening stay open.

## Artifacts

- [00](00_setup.json): setup, gates from both processes, isolation, sequences, Redis, DB hashes, preservation, frozen-artifact checks, model-call order.
- [01](01_extraction.json)–[09](09_memo.json): pipeline rows.
- [09a](09a_grounded_context_rebuilt.json)–[09f](09f_section_scan.txt): rebuild, memo model call, all 8 calls, input/output and four-step replay, guard edits, sentence scan (hits are candidates, not grades).
- HTTP probe:
  - [10](10_retrieval_ask_q1_q7.json): Q1–Q7.
  - [11](11_authorization_matrix.json): matrix, logouts, staff MFA, content types.
  - [11b](11b_reconciliation_by_principal.json): reconciliation per principal.
  - [12](12_api_payloads.json) and [13](13_rendered_reports_text.json): API payloads and rendered text.
- Markdown: [14](14_markdown_utf8.json) and the exported bytes [14_ic_memo_export.md](14_ic_memo_export.md).
- Chrome: [15](15_browser_walks.json) and [browser/](browser/) (four screenshots and the server-log lines for the walks).
- [16](16_probes.json): numeric-parse probes carried from earlier runs.
- [process/](process/): server, worker, memwatch, probe, Markdown-check, analysis and dump output.
- [scripts/](scripts/): every run script, plus the derivation scripts that list each change from the memo-98 harness.
- [snapshots/](snapshots/): before/after snapshots, DB hashes, Redis, gate refusal, migration, sequences, memo-97 and memo-98 field comparisons.
