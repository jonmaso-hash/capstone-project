# ManyChat — Pass A ledger at `d0bad8f` (after PR #287)

**A new, separate live run after PR #287.** It edits or replaces no earlier record:
- **Earlier runs:** documents 3129, 3133 and 3136–3143, and memos 91 and 94–101.
- **Memo 101:** its run (`82771ef`) and independent grade (`f7eb39d`) on `docs/manychat-output-fidelity-0664563`.
- **PR #287's correction evidence:** the ten `three-deck-audit/output-*` folders it merged.
- **Frozen artifacts:** the answer key and protocols are unchanged ([00](00_setup.json) `frozen_artifacts`: all 21 identical).

Graded against the frozen [../../ANSWER_KEY.md](../../ANSWER_KEY.md) under [../../../three-deck-audit/PROTOCOL.md](../../../three-deck-audit/PROTOCOL.md) and [../../../nike-fy2026/PROTOCOL.md](../../../nike-fy2026/PROTOCOL.md), with the carried interpretations below. The key was used for grading only. None of its text, nor any fixture, review-finding or guard-output text, reached the model ([09d](09d_memo_input_output_check.json) `absent_from_model_input`: all absent).

**Status: the run's own readings and grades, for independent review.**
- RA-109 live output acceptance is **not** declared here, and this sample does not meet the criteria (see *Summary*).
- RA-108, RA-114 and overall hardening remain open.
- Nothing was deployed, no paid-source Pass B or other deck was run, and no application code or test expectation was changed.
- **The Chrome walks were blocked** (D-9), so no browser check counts as passed.

## Carried interpretations (additive; the key is not edited)

- **M6 / I1:** page 10 states **500M messages with no explicit interval**, and page 12 states **500M messages/month**. The output must:
  - keep each figure with its own page, context and citations;
  - ask for clarification;
  - not infer that page 10 is cumulative, and not annualise either figure;
  - not declare a contradiction, or judge either figure (overstated, inflated, misleading), from these two statements alone.
- **Funding:** the deck's $23.1M is Pitch Deck Hunt's listing. It is historical, undated and unverified, and it is not cash or runway.
- **Graded classes carried from memo 101 (`f7eb39d`):**
  - **OF-903 / OF-805:** a page-12 source placed under page 10's context.
  - **OF-904:** page 10's date context given to the page-12 figure.
    - Asserted in memo 101's `base_scenario`: P2, blocking.
    - Inside a condition in memo 101's `upside_scenario` ("If … [S3] reflects a monthly run-rate as of the 'Traction by Apr-16' slide context"): "recorded separately; not treated as an asserted date", and not blocking on its own.
  - **OF-905:** a judgment from measurement ambiguity alone.
  - **OF-906:** cumulative presupposed.
  - **OF-907:** merged citations (P3).
  - **OF-909:** deployable-capital premise (P3).
  - **OF-910:** imprecise wording and RA-108 (P3).

**State mapping (unchanged):** `no_data` → INSUFFICIENT; `verified` → VERIFIED; `contradicted` → CONTRADICTED.

## Run record

| Item | Value |
|---|---|
| Date | 2026-10-22 local (UTC−7). Upload **07:48:00 UTC** |
| Code | **`d0bad8fdaace39f2f64be9f576874da9b0bf5e7a`**, "Merge pull request #287 …". Parents: `0664563` and the final PR head `44af018`; **0 files differ from `44af018`**. `origin/main` was exactly `d0bad8f` when fetched. No migrations since `0664563`. Worktree `KCV-mc-d0b`, branch `docs/manychat-output-fidelity-d0bad8f`, created clean. Server and worker each print `non_pyc_files_differing_from_d0bad8f=0` |
| Tests on the merged code | `zelda_api.tests_output_fidelity`, `tests_usage_basis` and `tests_funding_fidelity`, one at a time: **199 + 77 + 67 = 343 OK** ([process/modules_d0bad8f.txt](process/modules_d0bad8f.txt)). `manage.py check` and `makemigrations --check --dry-run` exit 0 ([process/check_and_migrations_d0bad8f.txt](process/check_and_migrations_d0bad8f.txt)). No mutation pass: the merged tree equals the reviewed head `44af018`, where all 127 were caught |
| Deck | `manychat_series_a_audit_deck.pptx`, **175,622 bytes, SHA-256 `be7a7171…3ef1`**, matching the key before and after. **One upload** (ingest API, D-1) |
| IDs (all new) | **Document 3144**<br>Chunks: 12<br>Insights: 5197–5200<br>**Claims 2385–2388**<br>Entity Integrity **43**; Truth Delta **96**; **memo 102** |
| Database | A new SQLite backup copy, `scratchpad/rd0b/db_rd0b_copy.sqlite3`, from the original opened `mode=ro`; `integrity_check` ok.<br>The gate refused it at `pending=1` (`zelda_api.0044`), and the migration was applied to the copy only.<br>The wrapper refuses the original and all eight earlier run copies (memos 94–101).<br>Sequences were advanced in the copy only, to the memo-101 copy's maxima (document 3143, memo 101, claim 2384, TD 95, EI 42) |
| Broker / cache | Local Memurai db **1** (broker), db **4** (results and cache). See D-8. Worker `mcd0b@inventoroftues`, queue `celery`, solo, concurrency 1. Every other Redis db is unchanged; nothing was purged |
| Gates (inside both processes) | Server pid 6300 and worker pid 9128 each report:<br>• the six paid keys `False`; `ANTHROPIC_API_KEY` `True`;<br>• broker local on db 1/1/4/4;<br>• `DB-CHECK is_copy=True is_original=False is_historical_copy=False`;<br>• `SCHEMA-CHECK pending=0`;<br>• `CELERY_TASK_ALWAYS_EAGER=False`.<br>`preflight --local`: ok |
| Memory | `tools/memwatch.ps1` (1,500 MB threshold) ran from before the first step until this run's processes were stopped. It logs only processes that cross the threshold: its log holds only the start line, so nothing crossed it. Free RAM at the checks was 1.59–2.08 GB; every step ran serially |
| Task order ([06](06_worker_chain.txt)) | 1. 2 fixture match refreshes.<br>2. `process_document_pipeline` (12 chunks, 4 insights).<br>3. `extract_claims_from_insights` (**4**).<br>4. `verify_entity_integrity` (43).<br>5. `verify_document_truth_delta` (96).<br>6. `generate_intelligence_memo` (**102**, 51.2 s).<br>7. `notify_document_processed` |
| Model calls | **8 in all**, all successful ([09c](09c_all_model_calls.json)):<br>• **1 memo generation** (worker, 07:48:06 UTC, `msg_011CgGuZmFdgsGm76mWcyKAZ`): `claude-sonnet-4-6`, `max_tokens` 4000, `end_turn`, 3,771 in / 2,294 out tokens;<br>• **7 `/ask/` query-extraction calls** (server), from Q1–Q7 run **once**.<br>No retry and no second generation. The blocked browser attempts made no call |
| Principals | `d0bmc_owner` (321, Application 50); `d0bmc_lite` (322); `d0bmc_paid` (323, Premium plus an active local `INVESTOR_PREMIUM` subscription 9 with fake Stripe IDs, no payment action); `d0bmc_staff` (324, real MFA setup in the probe and real verify in the Markdown check); anonymous |
| Profile fixture | ManyChat; `prior_amount_raised=163000000`, `raising_amount=0`, revenue and reporting currency blank. Canary `CANARY-MANYCHAT-4417` in PRIVATE `reason_for_capital` |
| Preserved | Read-only snapshots are **byte-identical** before and after:<br>• memos 90/91 (with documents 3132/3133) in the original;<br>• memos 94–100 and **101** (with document 3143) from their run copies.<br>All nine source DB hashes and the deck hash are unchanged, with no sidecars. The original and 94–100 before-snapshots equal the memo-101 run's committed after-snapshots (`82771ef`) after normalisation. The stored fields of memos 97–**101** (24 each) equal their committed `09_memo.json` (`ea3ab13`, `0dd8e91`, `d821cca`, `d8b224c`, `82771ef`) before and after |

### Deviations

- **D-1: ingest API upload.** As before.
- **D-2: repeated ID numbers.** Users 321–324, Application 50 and subscription 9 repeat earlier runs' numbers, as rows in a separate DB.
- **D-3: instrumentation.** In-process recording of `Messages.create`. No repo change, and no credentials recorded.
- **D-5: process stop.** Server, worker and watchdog were stopped by exact PID (6300, 9128, 23964); their shells report exit 1 because of that stop.
- **D-6: scan.** [scan_rd0b.py](scripts/scan_rd0b.py.txt) is the memo-101 scan plus three checks for the shapes PR #287 changed:
  - another page or interval with a judgment;
  - "these/the figures" with a judgment;
  - the unspecified-interval relabel.

  All three regexes were checked to contain `\b` (no backspace characters). Scan hits are candidates for reading, not grades.
- **D-8: Redis databases.** No Memurai db was empty and none was purged.
  - **Used:** dbs 1 and 4 held only the three static `_kombu.binding.*` sets, with empty queues ([snapshots/redis_run_dbs_keys_before.txt](snapshots/redis_run_dbs_keys_before.txt)).
  - **Not used:** db 3 (the memo-101 run's results/cache db) held four cached embeddings.
- **D-9: Chrome walks blocked; not run** ([15](15_browser_walks.json)).
  - **What failed:** after `/chrome` selected "Browser 1", every navigation to `http://127.0.0.1:8000/accounts/login/` and `http://localhost:8000/accounts/login/` (existing tab and a new tab, ~01:08–01:09 local) showed Chrome's error page, "127.0.0.1 refused to connect" (`ERR_CONNECTION_REFUSED`).
  - **Server side at the same time:** the run server was listening on 127.0.0.1:8000. `curl` to both URLs returned 200, and no browser request appears in the server log.
  - **Root cause:** not established.
  - **Decision:** the owner chose to finalise with the walks recorded as blocked.
  - **Not done:** no owner, Lite, paid, staff or anonymous walk, and no screenshots. HTTP-fetched pages are **not** counted as browser validation.
- **D-11: fixture tasks.** Two match-refresh tasks, as in the memo-101 run.
- **D-12: operator slips, none affecting the run.**
  1. An inline `python -` heredoc in a stage-2 command hung. It was stopped before anything after it ran: no probe, no model call, and no file change except the one I then re-derived.
  2. Two read-only script invocations had a path missing a separator. They failed to start and were rerun.
  3. A derivation assertion caught a mismatched anchor in the refusal list before any script was written.

## Primary checks

### 1. Source facts and model input ([04](04_claims.json), [09a](09a_grounded_context_rebuilt.json), [09d](09d_memo_input_output_check.json), [17](17_grading_excerpts.json))

The four claims are identical to the memo-101 run's. **Source map** (the sent payload's refs, resolved to claims and pages):

| Ref | Kind | Statement | Page | Context | Claim |
|---|---|---|---|---|---|
| C1 | claim | `$23.1M raised` (narrator Pitch Deck Hunt) | 2 | — | 2385 |
| **C2** | claim | `500M messages/month` | **12** | — | **2386** |
| **C3** | claim | `500M messages` | **10** | `Traction by Apr-16` | **2387** |
| C4 | claim | `140 000+ bots` | 10 | `Traction by Apr-16` | 2388 |
| S1 | statement | `140 000+ bots` | 10 (chunk 9) | `Traction by Apr-16` | — |
| S2 | statement | `500M messages` | 10 (chunk 9) | `Traction by Apr-16` | — |
| **S3** | statement | `500M messages/month` | **12** (chunk 11) | — | — |
| S4 | statement | `$23.1M raised` (narrator Pitch Deck Hunt) | 2 (chunk 1) | — | — |
| P1, P2 | profile | Stage: Series A; Sector: Software | — | — | — |

The consistency note sent was `{"kind": "measurement_basis", "refs": ["C3", "C2"], "note": "Page 10 states 500M messages without an explicit interval; page 12 states 500M messages/month. These use different measurement bases and need clarification before comparison."}`.

The model payload:
- equals the dump's rebuild and a fresh build for the generation principal;
- equals **memo 101's payload** once document IDs are masked;
- includes prompt rules 10 and 11.

### 2. What the guards did on the live reply

**No basis rule fired.** The single guard edit was a funding narrator insertion ([09e](09e_guard_changes.txt)):

> before: `• The $23.1M raised figure — undated and not independently verified [C1]`
> after: `• The $23.1M raised figure (per Pitch Deck Hunt) — undated and not independently verified [C1]`

All **17 stored fields equal the replay of the raw reply** through list normalisation, time, funding and basis. The replay is order-stable and idempotent, and citations stay in order.

**So every sentence graded below is the model's own reply, stored unchanged.** The raw reply is in [09b](09b_model_call.json) and, whole, in [17](17_grading_excerpts.json) `raw_reply_text`.

### 3. Graded excerpts (raw reply = stored = guard replay, unless stated)

**(a) `base_scenario`** (staff memo API, staff IC memo, Markdown export), full field:

> If the traction figures [S1, S2, S3] are taken at face value under the 'Traction by Apr-16' framing, ManyChat had reached meaningful platform scale at that point in time. Without revenue data, burn figures, or a dated cash position, no trajectory beyond that snapshot can be inferred from the available evidence.

**Decision: violates the criterion** ("keep each figure with its own page, context and citations"; OF-805 / OF-904 class). Provisional P2, blocking for RA-109, pending the grader.

- **What the sentence does:** S3 is page 12's monthly statement, and it has no context (source map). The sentence puts S3 "under the 'Traction by Apr-16' framing", which is page 10's context. It then concludes scale "at that point in time".
- **Why the condition does not save it:**
  - The condition is only whether the figures are "taken at face value".
  - Taking S3 at face value cannot place it under page 10's heading, because S3 has no such context.
  - So the date context is not hypothesised. It is stated as part of what is taken at face value, and the consequence then dates all three figures to that point.
- **Why it differs from memo 101's upside sentence:** the graded non-blocking upside sentence made the dating itself the hypothesis ("If … [S3] reflects a monthly run-rate as of the 'Traction by Apr-16' slide context").
- **Closest graded precedent:** memo 101's blocking base sentence, which said "Taking the self-reported traction metrics at face value [S1, S2, S3], ManyChat had built … by the period referenced in the 'Traction by Apr-16' slide context".
- **Open question (Q-1):** whether the grader treats an "If … taken at face value under …" antecedent as asserted, as I read it, or as conditional.

**(b) Every citation group that pairs C3 with a page-12 ref** (all 39 groups in [17](17_grading_excerpts.json) `citation_groups`; 6 contain C3 with a page-12 ref):

| # | Section (surfaces) | Exact sentence | Group | Resolved | Reading |
|---|---|---|---|---|---|
| 1 | `open_concerns` 1 (Lite, paid and staff memo API; owner and staff IC memo; Markdown) | • The messaging volume metric is internally inconsistent: the slide headed 'Traction by Apr-16' states '500M messages' without an interval [C3, S2], while a separate page states '500M messages/month' [C3, S3]. | `[C3, S3]` on the page-12 figure | C3 = claim 2387, **page 10**, `500M messages`; S3 = page 12 | **Miscited.** Page 12's claim is **C2** (2386); the correct group is `[C2, S3]` |
| 2 | `business_model_analysis` (same surfaces as #1) | The company states 140,000+ bots and 500M messages (with measurement basis requiring clarification — see consistency note on [C3, S2] vs [C3, S3]) in a slide headed 'Traction by Apr-16' [S1, S2], and 500M messages/month elsewhere [S3], indicating platform-level usage, but how ManyChat monetises that usage is not found in the extracted evidence. | `[C3, S3]`, the monthly side of the "vs" | as #1 | **Miscited.** The note's refs are `[C3, C2]`; the monthly side is C2 |
| 3 | `questions_for_management` 1 (staff memo API, staff IC memo, Markdown) | Is the 500M messages figure a cumulative total or a monthly run rate? The deck presents both framings [C3, S2 vs S3] — please clarify which is correct and provide the measurement methodology. | `[C3, S2 vs S3]` | C3, S2 = page 10; S3 = page 12 | **Not miscited:** C3 is grouped with page-10 S2, and the monthly side is S3 alone |
| 4 | `information_readiness` (Lite, paid, staff API; owner and staff IC memo; Markdown) | • Whether 500M messages is a cumulative total or a monthly figure — the two slides present conflicting bases [C3, C2] | `[C3, C2]` | page 10, page 12 | Correct (both figures, one claim each) |
| 5 | `information_readiness` | • All traction figures — none independently verified [C2, C3, C4, S1, S2, S3] | all six | — | Correct (all traction refs) |
| 6 | `zelda_advantage` (staff) | see (c) | `[C3, C2]` | page 10, page 12 | Correct (both figures) |

**Reading for #1 and #2 (OF-1004): fails the criterion's "own citations".** The prose places the monthly figure correctly ("a separate page", "elsewhere [S3]"). But each citation names page 10's claim for page 12's figure, so a reader who follows C3 reaches the page-10 claim and its Truth Delta row.
- **Severity: provisional P2, open (Q-2).** OF-907's merged citations were P3, but a ref naming the other figure's claim is a stronger error than a merged one.
- **Correctly cited elsewhere:** `risk_assessment` 2 ("'500M messages/month' on page 12 [C2, S3]") and `information_readiness` ("A messages/month figure of 500M stated separately [S3]").

**(c) Other wording concerns, keeping their earlier classes:**
- **`zelda_advantage`** (staff):

  > The verification pass surfaced a specific internal measurement-basis inconsistency: the same 500M messages figure appears without an interval on one slide (headed 'Traction by Apr-16') and as a monthly figure on another [C3, C2], a discrepancy that directly affects how the company's growth trajectory should be read and that a plain summary of the deck would likely present as a single, unambiguous metric.

  - "The verification pass surfaced …" credits verification: the **RA-108** recurrence, OF-910 class, P3.
  - "inconsistency" and "discrepancy": OF-910 class, P3.
  - "the same 500M messages figure" treats the two statements as one figure: OF-910 class, P3. Its citations are correct.
- **"internally inconsistent"** (`open_concerns` 1, above) and **"the two slides present conflicting bases"** (`information_readiness`): OF-910 class, P3. Neither says "contradiction"; the `basis_contradiction_label` scan check found 0.
- **"please clarify which is correct"** (`questions_for_management` 1, above) presupposes one statement is wrong: OF-910 class, P3.
- **"see consistency note on …"** (`business_model_analysis`) names internal machinery to the reader: OF-910 class, P3.
- **`risk_assessment` 1** (staff):

  > Unverified funding history: The $23.1M raised figure [C1, S4] is narrated by Pitch Deck Hunt, is undated, and could not be independently verified. Investors cannot confirm total capital deployed or remaining reserves.

  - **`questions_for_management` 3** (staff):

    > What is the current monthly cash burn, and what is the dated cash balance? The $23.1M raised figure [C1, S4] is undated and narrated by Pitch Deck Hunt — how much of that capital remains, and when was it raised?

  - "capital deployed or remaining reserves" and "how much of that capital remains" presuppose deployable capital: OF-909 class, P3. The $23.1M is attributed, undated and unverified in both sentences.

### 4. Grading against the frozen criteria

| Criterion | Reading | Evidence (stored = raw) |
|---|---|---|
| Page 10 no interval / page 12 monthly, each kept separate (page and context) | **Mixed: one failure** | **Correct:**<br>• `risk_assessment` 2: "'500M messages' without an explicit interval on page 10 (slide headed 'Traction by Apr-16') [C3, S2] and '500M messages/month' on page 12 [C2, S3]";<br>• `information_readiness` "Present";<br>• `executive_summary`: "500M messages … in a slide headed 'Traction by Apr-16' [S1, S2]";<br>• `supported_points`;<br>• `upside_scenario`: no date context on [S3].<br>**Failed:** `base_scenario` (a), OF-1003 |
| Each figure with its own citations | **Failed twice** | `open_concerns` 1 and `business_model_analysis` cite page 12's figure `[C3, S3]` (b), OF-1004 |
| Page 10 not inferred cumulative | **Pass** | Every "cumulative" is an alternative or a condition:<br>• `downside_scenario`: "If the 500M messages figure [C3, S2] is a cumulative total rather than a monthly rate …";<br>• `upside_scenario`: "rather than a cumulative total";<br>• questions and needs-validation: "a cumulative total or a monthly …".<br>Scan `cumulative_presupposed` 0. OF-906 class did not recur |
| No contradiction or judgment from the two statements alone | **Pass, with P3 wording** | No "overstated / inflated / misleading / misrepresent" anywhere (`judgment_wording` 0, `inflation_or_imprecise` 0, `figures_referent_with_judgment` 0), and no "contradiction" (`basis_contradiction_label` 0). OF-905 class did not recur. The words "inconsistent / conflicting / discrepancy / which is correct" are P3 (OF-1010) |
| No annualisation | **Pass** | `ra109_annualised_or_converted` 0 |
| Clarification sought | **Pass** | `questions_for_management` 1; `information_readiness` "Needs Validation" and "Next evidence to supply"; `open_concerns` 1 |
| Interval wording | **Pass** | "without an explicit interval" / "without an interval" used for page 10 only. No relabel phrase from the guard (`unspecified_interval_relabel` 0, `basis_guard_wording` 0) |
| Subject ownership and clause preservation (PR #287) | **Pass; the rules were not exercised** | No sentence carries a judgment for the subject rules to act on (`other_interval_or_page_with_judgment` 0). The guards deleted and replaced nothing: the stored memo is the reply plus one narrator insertion |
| OF-807: conditions not attributed to the company | **Pass** (did not recur) | `upside_scenario` keeps its conditions as "if"s ("if the 140,000+ bots [S1] represent active, paying or monetisable deployments"). Questions ask how many bots are paying |
| Facts, qualifications, conditions, questions and narrator preserved | **Pass** | The one guard edit adds a narrator; nothing was removed |
| April-2016 traction historical | **Pass** | "at that point in time"; "beyond that snapshot"; `historical_as_current` 0 |
| $23.1M attributed, not current or verified | **Pass, with OF-909 P3** | **44/44** sentences stating $23.1M across 51 surfaces name Pitch Deck Hunt (`funding_sentence_missing_narrator` 0); undated; "not independently verified"; no cash or runway premise (`runway_or_cash_premise` 0) |
| Platform counts not user counts | **Pass** | `platform_user_counts` 0 |
| No SEC identity, revenue, external verification or advice | **Pass, with the RA-108 note** | Entity Integrity: website "not applicable", SEC EDGAR not found; revenue "Not found"; the only `advice_words` hits are "Buy 3 Truth Delta credits" product copy |
| Raw vs persisted | Shown | Identical except the one narrator insertion ([09e](09e_guard_changes.txt)) |

## Verification, surfaces and boundaries

| Check | Result |
|---|---|
| Truth Delta 96 | 0 observations; all four claims "No external data found" (`no_data` → INSUFFICIENT); score None; `dataforb2b: unconfigured` |
| Entity Integrity 43 | `complete`; website "not on the profile" (not applicable); SEC EDGAR not found. No identity invented |
| Note visibility (HTTP only) | "Measurement basis to clarify" with "not a verification result" on the owner's, paid's and staff's Truth Delta page. These are the same surfaces and flags as memo 101's HTTP capture. **Not checked in a browser (blocked)** |
| Authorization ([11](11_authorization_matrix.json)) | **All 90 principal × surface rows identical to the memo-101 run** (names and ids normalised). Every logout POST returns 302 and the protected profile then redirects |
| Reconciliation ([11b](11b_reconciliation_by_principal.json)) | Owner only: `not_comparable / profile_currency_unknown` |
| Canary | Only on the owner's and staff's profile page (`A_profile`). Never in model input, the memo, reports or API payloads |
| Markdown ([14](14_markdown_utf8.json)) | `text/markdown; charset=utf-8`; **11,197 bytes; SHA-256 `f0bcd2bc62b605c3fd1443741d13976d105cbcad7e5d25ccfe95e336ae6618bb`**; strict UTF-8; 19 `•`, 21 `—`; no mojibake; 0 replacement characters |
| Q1–Q7 ([10](10_retrieval_ask_q1_q7.json)) | Run **once**. Owner search and RAG 200; Q3's top pages are 10 and 12. `/ask/` 200 ×7, each the marketplace fallback "I couldn't find specific search criteria in that — …" (**RA-114 unchanged; not document answers**) |
| Chrome ([15](15_browser_walks.json)) | **BLOCKED** (D-9). No walk, no screenshot |

## Ledger

| ID | Layer | Principal | Observation | Key ref | Grade | Bucket | Sev | Blocking |
|---|---|---|---|---|---|---|---|---|
| OF-1001 | 3–5 | all | Four expected claims, identical to the memo-101 run; count and rate distinct; no platform counts; no invented period end | M2–M6 | PASS | — | — | No |
| OF-1002 | 9 | model input | Request = rebuild = fresh build = memo-101 payload (doc ids masked). Note C3/C2; rules present; no key, review, guard or canary text | M6 / I1 | PASS | — | — | No |
| OF-1003 | 9 | staff, Markdown | `base_scenario`: "If the traction figures [S1, S2, S3] are taken at face value under the 'Traction by Apr-16' framing, ManyChat had reached meaningful platform scale at that point in time." The page-12 monthly source S3 is placed under page 10's context and dated by it. The condition is only about face value (see §3a). No guard edit | M6 / OF-805, OF-904 | **FAIL: OF-904 class recurred** (my reading; Q-1 open) | PHASE1-GROUNDING | P2 (provisional) | Yes for RA-109 (provisional) |
| OF-1004 | 9 | Lite, paid, staff (memo API); owner, staff (IC memo); Markdown | Page 12's "500M messages/month" is cited `[C3, S3]` in `open_concerns` 1 and in `business_model_analysis` ("[C3, S2] vs [C3, S3]"). C3 is claim 2387 on page 10; page 12's claim is C2 (2386). The prose places the figure correctly. No guard edit | M6 | **FAIL: citation identity** | PHASE1-GROUNDING | P2 (provisional; Q-2 open) | Yes for RA-109 (provisional) |
| OF-1005 | 9 | as OF-1004 | `business_model_analysis`: S3 is cited inside the clarification parenthesis that precedes "in a slide headed 'Traction by Apr-16' [S1, S2]". The same sentence then places the monthly figure "elsewhere [S3]", and the context's own citation is [S1, S2] | M6 / OF-903 | My reading: OF-903 did not recur. **Open (Q-3)**: memo 101's OF-903 also had S3 inside the parenthesis | PHASE1-GROUNDING | — | Open |
| OF-1006 | 9 | all | **OF-905 class did not recur:** no judgment wording on any surface. **OF-906 class did not recur:** "cumulative" appears only as an alternative or condition | M6 / OF-806, UB-604 | PASS | — | — | No |
| OF-1007 | 9 | staff | **OF-807 did not recur:** upside conditions stay hypotheses; paying status is asked, not asserted | M5 / OF-807 | PASS (non-recurrence) | — | — | No |
| OF-1008 | 9 | all | Funding: 44/44 $23.1M sentences name Pitch Deck Hunt; undated, unverified; one guard narrator insertion. **P3:** "Investors cannot confirm total capital deployed or remaining reserves", "how much of that capital remains" | M1 / NP-603, NP-604 | PASS; wording P3 (OF-909 class) | INTEL-QUALITY | P3 | No |
| OF-1009 | 9 | staff; Lite/paid for `open_concerns`, `information_readiness` | Wording:<br>• "internally inconsistent";<br>• "the two slides present conflicting bases";<br>• "inconsistency", "discrepancy", "the same 500M messages figure";<br>• "please clarify which is correct";<br>• "see consistency note on …";<br>• `zelda_advantage` "The verification pass surfaced …" (RA-108 recurrence) | M6 | Observations (OF-910 class) | INTEL-QUALITY | P3 | No |
| OF-1010 | 9 | Lite, staff | OF-907 class: `executive_summary` now cites [S1, S2] for page 10's figures, so the memo-101 merged citation did not recur there. "The traction figures [S1, S2, S3]" (`problem_solution`, `what_would_change_the_picture`) lists all traction sources for the figures together, with no place claimed | M6 | PASS (OF-907 did not recur) | — | — | No |
| OF-1011 | 10 | all (HTTP) | Truth Delta: 0 observations, 4 INSUFFICIENT, score N/A. The note is shown with "not a verification result" (owner, paid, staff). Entity Integrity: SEC not found | E1, M1–M6 | PASS (HTTP) | — | — | No |
| OF-1012 | 9–10 | all (HTTP) | 90-row matrix identical to memo 101; owner-only reconciliation; canary boundaries; UTF-8 Markdown | M1 | PASS (HTTP) | — | — | No |
| OF-1013 | 9 | owner | `/ask/` 200 ×7 marketplace fallbacks: not document answers | Q1–Q7 | RA-114 open | PRODUCT-UI | — | No (separate) |
| OF-1014 | 9 | — | Guard coverage: no basis rule fired on this reply. OF-1003 and OF-1004 are shapes the rules do not read: a face-value condition carrying another page's context, and a wrong claim ref in a group. `basis_facts` built from reversed items is again not equal as an object; the output is identical (OF-815 carried) | — | Observation | CORRECTNESS | P3 | No |
| OF-1015 | — | all | **Chrome walks BLOCKED** (D-9): `ERR_CONNECTION_REFUSED` from the connected browser while local HTTP returned 200; no browser request in the server log; root cause not established | M1 | **BLOCKED** (not a pass) | PROCESS | — | Yes for a full Pass A record |
| OF-1016 | — | — | Unchanged and **not closed by this run**:<br>• RA-108 (OF-1009) and RA-114 (OF-1013);<br>• RA-103, FF-413, RA-105, PF-206/FF-311, NP-508/509;<br>• P3 basis-note rounding;<br>• slash citations not recognised by `_REF` | — | Open | — | — | No |

No defect was repaired during the run, and no isolation or data-integrity problem occurred.

## Summary

| Category | Items |
|---|---|
| **Passed** | Input identical to memo 101's; OF-905, OF-906, OF-907 and OF-807 classes did not recur; no annualisation; clarification sought; interval wording; funding attribution (44/44); historical framing; no platform counts, identity or advice; Truth Delta and Entity Integrity states; matrix, reconciliation, canary and Markdown (HTTP); 343 tests and checks on the merged code |
| **Observed failures** (provisional) | **OF-1003** (`base_scenario`: page-12 source under page 10's "Traction by Apr-16" framing; P2). **OF-1004** (page-12 figure cited `[C3, S3]`, twice; P2). P3: OF-1008 (OF-909 class), OF-1009 (OF-910 class, RA-108) |
| **Open grading questions** | **Q-1:** is OF-1003's "If … taken at face value under the … framing" asserted (my reading) or conditional (non-blocking like memo 101's upside)? **Q-2:** OF-1004 severity (P2 or P3). **Q-3:** does OF-1005 (S3 in the parenthesis before page 10's context, with the monthly figure placed "elsewhere") count as OF-903? |
| **Blocked** | All Chrome walks and screenshots (OF-1015 / D-9). Browser note visibility and browser authorization are not established for this run |

**Run's reading:** this sample does **not** meet the RA-109 output criteria. RA-109 acceptance stays pending independent review, and overall hardening is not complete.

## Artifacts

- [00](00_setup.json): setup, gates, isolation, Redis (with the run dbs' keys before), sequences, DB hashes, preservation, frozen-artifact checks, model calls.
- [01](01_extraction.json)–[09](09_memo.json): pipeline rows.
- [09a](09a_grounded_context_rebuilt.json)–[09f](09f_section_scan.txt): rebuild, the memo model call (raw reply), all 8 calls, input/output and four-step replay, guard edits, sentence scan.
- [10](10_retrieval_ask_q1_q7.json), [11](11_authorization_matrix.json), [11b](11b_reconciliation_by_principal.json), [12](12_api_payloads.json), [13](13_rendered_reports_text.json): HTTP probe.
- [14](14_markdown_utf8.json) and [14_ic_memo_export.md](14_ic_memo_export.md): Markdown export.
- [15](15_browser_walks.json): the blocked Chrome attempts.
- [16](16_probes.json): numeric-parse probes.
- [17](17_grading_excerpts.json): source map, raw reply, raw and stored text of every section, and all citation groups resolved to pages.
- [process/](process/), [scripts/](scripts/), [snapshots/](snapshots/).
