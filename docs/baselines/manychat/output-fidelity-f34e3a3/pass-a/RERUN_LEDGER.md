# ManyChat — Pass A ledger at `f34e3a3` (after PR #285)

**A new, separate live run after PR #285.** It edits or replaces no earlier record:
- earlier runs: documents 3129, 3133, 3136–3141 and memos 91, 94–99;
- the memo-99 run and its grade (`output-fidelity-64f9db5/pass-a/` at `2e3b624` on `docs/manychat-output-fidelity-64f9db5`);
- the merged PR #285 evidence (`three-deck-audit/output-figure-form-9d24d97/`, `output-p34-correction-424dd36/`, `output-p29-behaviour-ffc408f/`);
- the frozen answer key and protocols, unchanged ([00](00_setup.json) `frozen_artifacts`).

Graded against the frozen [../../ANSWER_KEY.md](../../ANSWER_KEY.md) under [../../../three-deck-audit/PROTOCOL.md](../../../three-deck-audit/PROTOCOL.md) and [../../../nike-fy2026/PROTOCOL.md](../../../nike-fy2026/PROTOCOL.md). The key was used for grading only; none of its text, nor any fixture, review-finding or guard-output text, reached the model ([09d](09d_memo_input_output_check.json) `absent_from_model_input`).

**Status: ungraded.** These are the run's own readings, for independent grading.
- **RA-109:** live output acceptance stays **pending** until that grading.
- **Still open:** RA-108 and overall Zelda hardening.
- **Not done:** nothing was deployed, paid-source Pass B was not run, no other deck was run, and no application code was changed.

## Key interpretations carried forward (additive; the key is not edited)

- **M6 / I1 (messages basis):** page 10 states **500M messages with no explicit interval**; page 12 states **500M messages/month**. The expected behaviour is to keep both, each with its own page, context and citations, ask for clarification, and not label page 10 cumulative, annualise either, or declare an error or contradiction from those two statements alone. The key's "cumulative by context" is not used.
- **Currency erratum:** a blank reporting currency gives owner reconciliation `not_comparable / profile_currency_unknown`, not the key's `differs`.
- **Grades carried:** memo 99's PARTIAL PASS (OF-704, OF-705 open) and memo 97's RA-106 scoped acceptance are not reset here.

**State mapping (unchanged):** `no_data` → INSUFFICIENT; `verified` → VERIFIED; `contradicted` → CONTRADICTED. The basis note is not a state.

## Run record

| Item | Value |
|---|---|
| Date | 2026-10-18 local (UTC−7). Upload **01:36:48 UTC** (2026-10-19) |
| Code | **`f34e3a399349a2d7401f66d9b60b10834047e57a`**, "Merge pull request #285 …". Parents: 64f9db5 and the final PR head 2bd9056; **0 files differ from 2bd9056**. origin/main was exactly f34e3a3 when fetched. No migrations since 64f9db5. Worktree `KCV-mc-f34`, branch `docs/manychat-output-fidelity-f34e3a3`, created clean at f34e3a3. Server and worker each print `non_pyc_files_differing_from_f34e3a3=0` |
| Deck | `manychat_series_a_audit_deck.pptx`, **175,622 bytes, SHA-256 `be7a7171bbc84b9895a45adfbc41f2533f3d23b3a4a561c82a8d9de6b94f3ef1`**, matching the key, before and after. **One upload** (ingest API, D-1) |
| IDs (all new) | **Document 3142** (`analyzed`, `complete`)<br>Chunks: 12<br>Insights: 5189–5192<br>**Claims 2377–2380**<br>Entity Integrity **41**; Truth Delta **94**; **memo 100** |
| Database | A new SQLite backup copy, `scratchpad/f34/db_f34_copy.sqlite3`, made with the backup API from the original opened `mode=ro`; `integrity_check` ok. The gate refused it at `pending=1` (`zelda_api.0044`); the migration was applied to the copy only.<br>The run wrapper refuses the original and all six earlier run copies (memos 94–99).<br>ID sequences were advanced in the copy only, to the memo-99 copy's maxima (read `mode=ro`): document 3141, memo 99, claim 2376, TD 93, EI 40 ([snapshots/sequences.txt](snapshots/sequences.txt)) |
| Broker / cache | Local Memurai db **4** (broker) and **12** (results and cache). Only dbs 4 and 12 were empty before the run, with no clients (D-8). Worker `mcf34@inventoroftues`, queue `celery`, solo, concurrency 1. Every other Redis db is unchanged; nothing was purged |
| Gates (inside both processes) | Server pid 10492 and worker pid 20100 each report:<br>• six paid keys `False`: `FILED_API_KEY`, `COMPANYENRICH_API_KEY`, `NEWS_API_KEY`, `DATA4B2B_API_KEY`, `USPTO_ODP_API_KEY` (read by no code at f34e3a3; blanked anyway), `CRUNCHBASE_API_KEY`;<br>• `ANTHROPIC_API_KEY` `True`;<br>• broker local on db 4/4/12/12;<br>• `DB-CHECK is_copy=True is_original=False is_historical_copy=False`;<br>• `SCHEMA-CHECK pending=0`, heads zelda_api 0044, matchmaking 0095, accounts 0017, billing 0007;<br>• `CELERY_TASK_ALWAYS_EAGER=False`.<br>`preflight --local`: ok |
| Memory | `tools/memwatch.ps1` (1,500 MB threshold) ran throughout; nothing crossed it. Free RAM was 1.4–2.1 GB; every step ran serially. No tests or mutations ran alongside the run |
| Task order ([06](06_worker_chain.txt)) | 1. 2 fixture match refreshes (D-11).<br>2. `process_document_pipeline` (12 chunks, 4 insights).<br>3. `extract_claims_from_insights` (**4**).<br>4. `verify_entity_integrity` (41).<br>5. `verify_document_truth_delta` (94).<br>6. `generate_intelligence_memo` (**100**, 45.3 s).<br>7. `notify_document_processed` |
| Model calls | **8 successful** ([09c](09c_all_model_calls.json) `order`):<br>• **1 memo call** (worker, 01:36:54 UTC, `msg_011CgAjqEXx9w6jVYHFirADz`): `claude-sonnet-4-6`, `max_tokens` 4000, `end_turn`, 3,771 in / 2,039 out tokens;<br>• **7 `/ask/` query-extraction calls** (server, 01:44:30–01:44:41 UTC) from the **second** Q1–Q7 attempt.<br>**Plus 5 rejected calls** in the first Q1–Q7 attempt (01:38:57–01:39:02 UTC): HTTP 400 "credit balance is too low", not in the wrapper log, which records successful responses only (D-3, D-10). No memo retry and no second generation. The browser walks made no model call |
| Principals | `f34mc_owner` (321, Application 50); `f34mc_lite` (322); `f34mc_paid` (323, Premium plus an active local `INVESTOR_PREMIUM` subscription 9 with fake Stripe IDs `cus_f34_local_mc` / `sub_f34_local_mc`, no payment action); `f34mc_staff` (324, real staff-MFA setup by the probe, real verify in the Markdown check and Chrome); anonymous |
| Profile fixture | ManyChat; `prior_amount_raised=163000000`, `raising_amount=0`, revenue blank, reporting currency blank. Canary `CANARY-MANYCHAT-4417` in PRIVATE `reason_for_capital` |
| Preserved | Read-only snapshots (`PRAGMA query_only`) of memos 90/91 (with documents 3132/3133) in the original, 94, 95, 96, 97, 98 and **99** (with document 3141, from the memo-99 run copy) are **byte-identical** before and after. All seven source DB hashes and the deck hash are unchanged; no source DB has a sidecar.<br>The original/94–98 before-snapshots equal the memo-99 run's committed after-snapshots (`d821cca`) once carriage returns and lines starting `Invalid line` are removed.<br>Memo 97's, 98's and **99's** 24 stored fields equal their committed `09_memo.json` (`ea3ab13`, `0dd8e91`, `d821cca`), before and after |

### Deviations

- **D-1: ingest API upload.** As before; the only UI intake leads to Stripe checkout or credit redemption.
- **D-2: repeated ID numbers.** User IDs 321–324, Application 50 and subscription 9 repeat earlier runs' numbers, as separate rows in a separate DB.
- **D-3: instrumentation.** In-process recording of `Messages.create` in the run wrapper; no repo change, no credentials recorded. It logs **successful** responses only, so the first attempt's rejected calls are evidenced by the server log, not `model_calls.jsonl`.
- **D-4: Chrome mechanics.** As before: fields set on `form.elements`, then `requestSubmit()`; logout by the nav form. The staff TOTP was computed for the next 30-second window. The Truth Delta page has no site nav (FF-413), so the paid logout went through `/`. The anonymous checks were in-page `fetch` with `redirect: manual`. The Lite login landed on the owner profile first (the login `next=` redirect).
- **D-5: process stop.** Server and worker were stopped by exact PID; the background shells report exit 1 because of that stop.
- **D-6/D-7: scan and replay harnesses.** Derived from the memo-99 run's by listed substitutions ([make_scan.py](scripts/make_scan.py.txt), [make_scripts2.py](scripts/make_scripts2.py.txt)); scan checks added for this reply's shapes. Scan hits are candidates, not grades.
- **D-8: Redis databases.** The established pattern uses three empty dbs. Only dbs 4 and 12 were empty, and purging another run's db was not acceptable, so results and cache share db 12 (Celery `celery-task-meta-*` and Django `:1:*` keys cannot collide). Both processes checked it.
- **D-9: Chrome unreachable at first.** 18:41–18:45 local, the connected browser returned "connection refused" for `127.0.0.1:8000` and `localhost:8000` (three attempts) while the server answered local HTTP. The run paused for the owner; after the owner re-selected the browser, the walks ran 18:51–18:55 ([15](15_browser_walks.json)).
- **D-10: Ask Zelda second attempt.** The first Q1–Q7 attempt ([10](10_retrieval_ask_q1_q7.json)) hit an Anthropic billing failure: `/ask/` returned **500 for Q1–Q5** (API HTTP 400, "Your credit balance is too low …"; request IDs in [process/server.log.txt](process/server.log.txt)) and **503 for Q6–Q7** (no outbound request). The run paused; the owner reloaded credits; the same server process then ran Q1–Q7 **once** more ([10b](10b_retrieval_ask_q1_q7_second_attempt.json), [ask_second.py](scripts/ask_second.py.txt), which refuses a repeat). Nothing else changed between the attempts. No answer was regenerated to pass.
- **D-11: fixture tasks.** Two match-refresh tasks ran at fixture time (the memo-99 run recorded three). Both succeeded; the queue was empty before the upload.

## Primary checks

### 1. Source facts and normalized input ([02](02_chunks.json)–[04](04_claims.json), [09a](09a_grounded_context_rebuilt.json), [09d](09d_memo_input_output_check.json))

| Source | Claim | Value | Unit | Ownership / narrator | Period fields | Context | Chunk |
|---|---|---|---|---|---|---|---|
| p2 | `$23.1M raised` (2377) | 23,100,000 | (none), currency blank | named / **Pitch Deck Hunt** | none | — | `c80948f9…` |
| p10 | `140 000+ bots` (2380) | 140,000 | `bots` | implied / none | none | `Traction by Apr-16` | `4981cd72…` |
| p10 | `500M messages` (2379) | 500,000,000 | `messages` | implied / none | **none** | `Traction by Apr-16` | `4981cd72…` |
| p12 | `500M messages/month` (2378) | 500,000,000 | **`messages/month`** | implied / none | `period_kind` monthly, `time_period` `/month`, **no `period_end`** | none | `a6ff6361…` |

**PASS:** four claims, with values, units, pages, narrator, context and chunk hashes identical to the memo-99 run; count and rate distinct; bots deduped; no platform-user claim; no invented period end.

**Payload:** the sent request equals both the dump's rebuild and a fresh `GroundedContext.build` for the generation principal (owner 321, `ORIGIN_TASK`), and equals the memo-99 run's payload once document IDs are masked. Refs: C1 funding (Pitch Deck Hunt, `dates_not_as_of ["2015"]`); C2 `500M messages/month` p12; C3 `500M messages` p10 `Traction by Apr-16`; C4 bots; S1 bots; S2 `500M messages`; S3 `500M messages/month`; S4 funding; P1, P2 profile stage and sector.
- **`consistency_notes`:** `measurement_basis`, refs **C3, C2**, "Page 10 states 500M messages without an explicit interval; page 12 states 500M messages/month. These use different measurement bases and need clarification before comparison."
- **Prompt:** rules 10 and 11 and the dated-runway rule are present; the user prompt points to rule 11. `time_wording_allowed` is empty for every dated item.
- **Absent from the input:** the canary; 163,000,000; Bessemer, TechCrunch, Summit Partners; 2019, $18M, $140M; the founders; the key's wording; the fixture names; the review IDs (UB-604, NP-603, NP-604, OF-704, OF-705); and the guards' output phrases.
- **Basis facts:** one pair, refs C3/C2, members C2, C3, S2, S3, noun `messages`, no cumulative fact. **Built from the reversed item list, the basis-facts object is not equal** (OF-815); the guard output is identical either way.

### 2. Measurement-basis output: the merged guard corrected the live reply

**Unlike memo 99, the raw reply recurred with both reviewed shapes, and the basis guard corrected both live** ([09e](09e_guard_changes.txt), [06](06_worker_chain.txt): `basis_overstatement`, `basis_contradiction_label`). Both edits replay exactly.

| Section | Raw reply | Stored |
|---|---|---|
| `risk_assessment` 1 | "… These use different measurement bases. **If the cumulative figure was restated as a monthly figure, the implied monthly activity would be materially overstated.** Clarification is required …" | "… These use different measurement bases. **How the figure stated without an explicit interval relates to the monthly figure needs clarification before either is relied on.** Clarification is required …" |
| `open_concerns` 1 | "• **Contradictory** message-volume measurement bases: …" | "• **Ambiguous** message-volume measurement bases: …" |

**Kept as the model wrote them, and correct:**
- `risk_assessment` 1 places '500M messages' "on a slide headed 'Traction by Apr-16' [S2/C3]" and "separately … '500M messages/month' on page 12 [S3/C2]".
- `open_concerns` 1 places the rate "on a separate page [C2/S3]".
- `questions_for_management` 1 asks whether the traction-slide figure is cumulative or monthly and cites page 12 for the rate.
- `upside_scenario` / `downside_scenario` are conditional both ways.
- No "the cumulative figure", "overstated", annualisation or merged/verified 500M remains anywhere in the stored memo or on any captured surface ([09f](09f_section_scan.txt): `ra109_cumulative_asserted` 0, `ra109_annualised_or_converted` 0; staff Chrome full memo: no "overstat", no "the cumulative figure").

**Not corrected, for grading:**
- **OF-805, source placement:** `business_model_analysis` says "the company states 140,000+ bots [S1] and **500M messages [S2, S3]** as traction metrics **(in a slide context headed 'Traction by Apr-16')**". S3 is the page-12 monthly rate with no slide context; the clause cites it under the page-10 context and folds both sources into one "500M messages". The location rule acts on "on the same (traction) slide" / "on a slide headed 'X'" followed by the citation group; this wording ("500M messages [S2, S3] … (in a slide context headed …)") is outside it.
- **OF-806, judgment wording:** `open_concerns` 1 ends "These cannot be compared without clarification; **one or both figures may misrepresent the scale of actual activity.**" The sentence has no citation, no counted noun and no definite figure referent, so it resolves to no pair and the judgment rule does not act. It also appears as its own item in the staff overview's "Worth investigating" panel.

### 3. Funding narrative and total (NP-603)

- **Narrator on every amount sentence:** all **32 sentences stating $23.1M across 43 surfaces** name Pitch Deck Hunt (`funding_sentence_missing_narrator` 0).
- **Guard:** one `attribution:Pitch Deck Hunt` insertion in `what_would_change_the_picture` ("the $23.1M funding figure (per Pitch Deck Hunt) [S4]").
- **Wording:** no "total amount raised", no "this total", no company possessive ("its funding"), no company-credited narrative (`funding_total_wording` 0, `this_or_the_total_funding` 0, `company_possessive_funding` 0, `funding_credited_to_company` 0).
- **Aggregate question:** `open_concerns` says "It is unknown whether this reflects cumulative raises, a single round, or a different basis entirely"; the management question asks "the date and composition of the $23.1M in funding listed by Pitch Deck Hunt [C1/S4] — which rounds …". It asks rather than presupposes a total (memo 99's OF-706 "this total" did not recur).
- **Profile:** one `profile_undated` edit in `business_model_analysis` ("operates in software [P2] (current profile, undated)").

### 4. Funding is not operating cash (NP-604)

- No funding amount is used as a cash or runway denominator anywhere (`runway_or_cash_premise` 0). The funding-not-runway rule had nothing to correct.
- `financial_analysis`: "Runway: Not found in the extracted evidence."; questions ask for "the current monthly cash burn, and … the cash balance as of the most recent month-end".
- `downside_scenario`: "The funding figure [C1] could not be confirmed externally, leaving the capital structure uncertain."

### 5. Full transformation replay ([09d](09d_memo_input_output_check.json), [09e](09e_guard_changes.txt))

All **15 stored fields equal the replay of the raw reply** through the merged order: list normalisation, time guard (all `time_wording_allowed` empty), funding guard, basis guard.

| Check | Result |
|---|---|
| Reversed item order (facts and basis facts) | Same output for every field (the basis-facts object itself differs; OF-815) |
| Second pass over the stored text | No change and no rule fired |
| Citations | Same refs in the same order in every field |
| Time guard | Removed nothing |
| Funding guard | 2 edits: `profile_undated` (`business_model_analysis`), `attribution:Pitch Deck Hunt` (`what_would_change_the_picture`) |
| Basis guard | 2 edits: `basis_overstatement` (`risk_assessment`), `basis_contradiction_label` (`open_concerns`) |
| Narrator-provenance, unsupported-total, funding-not-runway, cash-premise, location rules | Did not fire |

## Verification, surfaces and regression boundaries

| Check | Result |
|---|---|
| Truth Delta ([07](07_truth_delta_reports.json), [05](05_observations.json)) | 0 observations; all four claims "No external data found" (`no_data` → INSUFFICIENT); 0 verified, 0 contradicted; `overall_truth_score` None ("N/A", "NOT SCORED · LIMITED PUBLIC EVIDENCE"). `provider_outcomes` `dataforb2b: unconfigured` (keyless); SEC not found |
| Entity Integrity 41 ([08](08_entity_integrity.json)) | Website/domain/founder/founding-year checks "Not applicable" (no website on the profile); SEC EDGAR "No SEC filer with this name was found … Not found". No non-EDGAR provider returned data. No CIK, incorporation or Form D anywhere |
| Note visibility | Truth Delta "Measurement basis to clarify" block with "This is not a verification result and doesn't affect the score." for **owner, Lite, paid and staff** (HTTP probe; paid and staff in Chrome). Anonymous: redirected |
| IC memo | Owner (Lite sections, Chrome): "Ambiguous message-volume …", the OF-806 clause and the OF-805 placement; no "contradict", no "overstat". Staff (full, Chrome) and Markdown: the guard-corrected memo. Lite/paid: 404, as before |
| Company overview | Lite/paid: the executive summary only ("… neither the exact measurement date nor the measurement interval for the message figure has been independently verified"); no monthly figure and no basis flag (OF-809). Staff "Worth investigating": "Ambiguous message-volume measurement bases …" (memo 99's contradiction label is gone) and the OF-806 sentence as a separate item |
| Counts, lists, citations | "4 claims", 4/0/4; lists render; citations unchanged by the guard edits |
| Markdown ([14](14_markdown_utf8.json)) | `text/markdown; charset=utf-8`; **10,219 bytes; SHA-256 `996bf63207e79d26bd0ba83a6da5c003447cd0d5b6f9c025c6a38acab4085f6d`**; strict UTF-8; 10 `•`, 15 `—`; the reader's text equals the strict decode; no mojibake or replacement characters |
| Q1–Q7 ([10](10_retrieval_ask_q1_q7.json), [10b](10b_retrieval_ask_q1_q7_second_attempt.json)) | Owner search/RAG 200 in both attempts, near-uniform relevance; Q3's top pages are 10 and 12. `/ask/`: first attempt 500 ×5 / 503 ×2 (billing, D-10); second attempt 200 ×7, each the marketplace query-extraction message "I couldn't find specific search criteria in that — try mentioning industry, size, price, or financials for founders." (**RA-114 unchanged**). No citations in `/ask/` responses; no figure, SEC identity, revenue or advice in them |
| Authorization ([11](11_authorization_matrix.json)) | **All 90 principal × surface rows identical to the memo-99 run** (status, redirect, owner panel, canary). Logout POST 302 for every signed-in principal; the protected profile then redirects to login |
| Reconciliation ([11b](11b_reconciliation_by_principal.json)) | Owner only (Lite, paid, staff, anonymous `[]`): `prior_amount_raised` `not_comparable / profile_currency_unknown`. "Profile and deck figures to review" appears only on the owner's Truth Delta page |
| Canary | Only on the owner's and staff's profile page (`A_profile`); never in model input, memo, reports, API payloads, Chrome-read pages or other surfaces |
| Historical context | "Traction by Apr-16" kept as slide context; `base_scenario`: "as of the period referenced". Funding undated ("no date is stated"). No current total, live raise, cash balance or "as of April 2016" assertion; the questions ask whether a round is being planned (`historical_as_current` 0, `as_of_slide_context` 0) |
| Platform counts / identity / advice | No 900M/275M/100M anywhere (`platform_user_counts` 0); no SEC identity; no current revenue; the only `advice_words` hits are the paid page's "Buy 3 Truth Delta credits" product copy |
| Browser walks ([15](15_browser_walks.json), [browser/](browser/)) | Real Chrome for owner, Lite, paid, staff (real MFA verify) and anonymous, each with a positive control; six screenshots and the server-log lines for the walks; nav logout then refusal for every signed-in principal |

## Ledger

| ID | Layer | Principal | Observation | Key ref | Grade | Bucket | Sev | Blocking |
|---|---|---|---|---|---|---|---|---|
| OF-801 | 3–5 | all | Four expected claims identical to the memo-99 run (values, units, pages, narrator, context, chunk hashes); count and rate distinct; no platform counts; no invented period end | M2–M6 | PASS | — | — | No |
| OF-802 | 9 | model input | Request = dump rebuild = fresh build = memo-99 payload (doc ids masked). Basis note C3/C2; rules 10/11 and the dated-runway rule present; no key, fixture, review, guard-output or canary text | M6 / I1 | PASS | — | — | No |
| OF-803 | 9 | all memo readers | **UB-604's shape recurred in the raw reply and the merged basis guard corrected it live:** "If the cumulative figure was restated as a monthly figure, the implied monthly activity would be materially overstated" → the pair's neutral clarification. Nothing stored or captured says "the cumulative figure", "overstated", or annualises | M6 / UB-604 | Guard exercised and corrected; for grader | — | — | No |
| OF-804 | 9–10 | Lite (memo sections), staff (memo, overview), Markdown | **OF-704's shape recurred and was corrected live:** "Contradictory message-volume measurement bases" → "Ambiguous …". The staff overview's "Worth investigating" panel now shows the ambiguity heading | M6 / OF-704 | Guard exercised and corrected; for grader | — | — | No |
| OF-805 | 9 | all memo readers | `business_model_analysis`: "500M messages **[S2, S3]** as traction metrics (in a slide context headed 'Traction by Apr-16')". The page-12 monthly source S3 is cited under the page-10 context and both sources are folded into one "500M messages". Not corrected: the location rule covers "on the same slide" / "on a slide headed" placements, not this wording. Other sections place the rate on page 12 correctly | M6 / OF-705 | OF-705-type source placement in a new wording; for grader | PHASE1-GROUNDING | P2 (provisional) | No |
| OF-806 | 9–10 | all memo readers; staff overview | `open_concerns` 1: "one or both figures may misrepresent the scale of actual activity". Unsupported judgment of the figures from the pair alone; the sentence resolves to no pair (no citation, noun or referent), so the judgment rule does not act. Repeated as its own "Worth investigating" item on the staff overview | M6 | Judgment wording; for grader | INTEL-QUALITY | P2/P3 (provisional) | No |
| OF-807 | 9 | staff | `upside_scenario`: "If the 500M messages figure represents a monthly run rate [S3] … and if the 140,000+ bots [S1] reflect active, paying customers … **These conditions are stated by the company [S1, S2, S3]**". The deck states the figures, not that bots are active, paying customers | M5, M6 | Attribution of conditions to the company; for grader | PHASE1-GROUNDING | P3 (provisional) | No |
| OF-808 | 9 | all | Wording: `executive_summary` "140,000+ **bots deployed**" (UB-607 shape; the deck says bots); a question "please clarify **which is correct**" (presupposes one figure is wrong); a question names "native Facebook/Meta tooling" (outside knowledge, in a question); "chatbot/messaging automation space" stated directly (OF-712) | M5, M6 | Observations | INTEL-QUALITY | P3 | No |
| OF-809 | 10 | Lite, paid | Company overview carries only the executive summary: it says the message figure's interval is unverified but shows neither the monthly figure nor the basis question (memo 99's "requires clarification (see open concerns)" flag did not recur) | M6 / UB-606 | Surface coverage; observation | PRODUCT-UI | P3 | No |
| OF-810 | 9 | all | Funding: 32/32 $23.1M sentences across 43 surfaces name Pitch Deck Hunt; no total, possessive or company-narrative wording; no cash/runway premise; one narrator insertion, one `profile_undated` | M1 / NP-603, NP-604 | PASS | — | — | No |
| OF-811 | 10 | all | Truth Delta: 0 observations, 4 INSUFFICIENT, score N/A; note visible to owner/Lite/paid/staff with "not a verification result"; Entity Integrity: SEC not found, no identity invented | E1, M1–M6 | PASS | — | — | No |
| OF-812 | 9–10 | all | Counts, lists, citations, UTF-8 Markdown, the 90-row matrix (identical to memo 99), owner-only reconciliation, canary boundaries, Chrome walks and logouts all hold | M1 | PASS | — | — | No |
| OF-813 | 9 | owner (Ask Zelda) | First Q1–Q7 attempt failed on the Anthropic credit balance (500 ×5, 503 ×2); run paused, credits reloaded, one second attempt: 200 ×7, RA-114 marketplace message unchanged. Q3 retrieval top pages 10 and 12 | Q1–Q7 | Billing failure recorded (operational); RA-114 open | CORRECTNESS (ops) | — | No |
| OF-814 | 9 | staff | `zelda_advantage` again compares itself with an unmeasured "plain AI summary" ("The evidence-grounded pass specifically identified a measurement-basis inconsistency … that a plain AI summary would likely flatten") | — | RA-108 recurrence | INTEL-QUALITY | P3 | No |
| OF-815 | 9 | — | `basis_facts(items)` ≠ `basis_facts(reversed items)` as objects; the guard's output, changes and refs are identical for every field either way | — | Observation (order-sensitive internal representation) | CORRECTNESS | P3 | No |
| OF-816 | — | — | Unchanged and **not closed by this run**: RA-108 (OF-814), RA-114 (`/ask/`), RA-103 (funding claim from the audit-framing slide 2), FF-413 (unstyled Truth Delta page, no site nav), RA-105 (currency), PF-206/FF-311 coverage, NP-508/509, P3 basis-note rounding | — | Open | — | — | No |

No defect was repaired during the run, and no isolation or data-integrity problem occurred.

## Summary

At merged `f34e3a3`, one live generation (**memo 100**, document 3142):
- **Input:** identical to the memo-99 run, including the C3/C2 basis note.
- **Measurement basis:** the raw reply **recurred** with both reviewed shapes, the cumulative/overstatement sentence and the "Contradictory" heading, and the merged basis guard **corrected both live**. Every stored field equals the four-step replay.
- **Remaining for grading:** an OF-705-type placement in a wording the location rule does not cover (OF-805); an unresolved "may misrepresent" judgment (OF-806); conditions attributed to the company (OF-807).
- **Funding:** every amount keeps its narrator; nothing treats it as cash.
- **Blocker met during the run:** the first Q1–Q7 attempt hit an Anthropic billing failure; after the owner reloaded credits, one second attempt ran (RA-114 unchanged).

**RA-109 live output acceptance stays pending until independent grading.** RA-108 and overall hardening stay open.

## Artifacts

- [00](00_setup.json): setup, gates from both processes, isolation, sequences, Redis, DB hashes, preservation, frozen-artifact checks, model-call order and the first attempt's failed `/ask/` log lines.
- [01](01_extraction.json)–[09](09_memo.json): pipeline rows.
- [09a](09a_grounded_context_rebuilt.json)–[09f](09f_section_scan.txt): rebuild, memo model call, all 8 successful calls, input/output and four-step replay, guard edits, sentence scan.
- HTTP probe: [10](10_retrieval_ask_q1_q7.json) and [10b](10b_retrieval_ask_q1_q7_second_attempt.json) (Q1–Q7, both attempts), [11](11_authorization_matrix.json), [11b](11b_reconciliation_by_principal.json), [12](12_api_payloads.json), [13](13_rendered_reports_text.json).
- Markdown: [14](14_markdown_utf8.json) and [14_ic_memo_export.md](14_ic_memo_export.md).
- Chrome: [15](15_browser_walks.json) and [browser/](browser/).
- [16](16_probes.json): numeric-parse probes carried from earlier runs.
- [process/](process/), [scripts/](scripts/), [snapshots/](snapshots/).
