# ManyChat — Pass A ledger at `c6c3d1b` (after PR #288): post-merge live validation for RA-109

**A new, separate live run after PR #288.** It edits or replaces no earlier record:
- **Earlier runs:** documents 3129, 3133 and 3136–3144, and memos 91 and 94–102.
- **Memo 102:** its run (`6d131f5`), independent grade (`f2a282f`) and browser diagnosis (`30115fb`) on `docs/manychat-output-fidelity-d0bad8f`.
- **PR #288's correction evidence:** the four `three-deck-audit/output-*` folders it merged.
- **Frozen artifacts:** the answer key and protocols are unchanged ([00](00_setup.json) `frozen_artifacts`: all 16 checks identical).

Graded against the frozen [../../ANSWER_KEY.md](../../ANSWER_KEY.md) under [../../../three-deck-audit/PROTOCOL.md](../../../three-deck-audit/PROTOCOL.md) and [../../../nike-fy2026/PROTOCOL.md](../../../nike-fy2026/PROTOCOL.md), with the interpretations carried in memo 102's ledger and grade. The key was used for grading only; none of its text, nor any review-finding or guard-output text, reached the model ([09d](09d_memo_input_output_check.json) `absent_from_model_input`: all absent).

**This file has two parts, kept separate:**
1. [Execution record](#part-1-execution-record): what was run and observed. Facts only.
2. [Provisional assessment](#part-2-provisional-assessment-pending-independent-review): my readings and provisional grades, **pending independent review**.

RA-109 acceptance is **not** declared here. RA-108, RA-114 and overall hardening remain open. Nothing was merged or deployed, and no application code, prompt, guard, fixture, test expectation or grading criterion was changed.

---

## Part 1: Execution record

### Run record

| Item | Value |
|---|---|
| Date | 2026-10-23 local (UTC−7). Upload **23:42:45 UTC** |
| Code | **`c6c3d1b9b1fe8b5e32d856c64a5b535a986684a0`**, "Merge pull request #288 …". Parents `d0bad8f` and the final PR head `d9f3ac7`; **0 files differ from `d9f3ac7`**. `origin/main` was exactly `c6c3d1b` when fetched. No migrations since `d0bad8f`. Worktree `KCV-mc-c6c`, branch `docs/manychat-output-fidelity-c6c3d1b`, created clean at `c6c3d1b`. Server and worker each print `CODE-CHECK head=c6c3d1b9…` and `non_pyc_files_differing_from_c6c3d1b=0` |
| Tests on the merged code | `zelda_api.tests_output_fidelity`, `tests_usage_basis` and `tests_funding_fidelity`, one at a time: **238 + 77 + 67 = 382 OK** ([process/modules_c6c3d1b.txt](process/modules_c6c3d1b.txt)). `manage.py check` and `makemigrations --check --dry-run` exit 0 ([process/check_and_migrations_c6c3d1b.txt](process/check_and_migrations_c6c3d1b.txt)). No mutation pass: the merged tree equals the reviewed head `d9f3ac7` |
| Deck | `manychat_series_a_audit_deck.pptx`, **175,622 bytes, SHA-256 `be7a7171bbc84b9895a45adfbc41f2533f3d23b3a4a561c82a8d9de6b94f3ef1`**, matching the key before and after. **One upload** (ingest API, D-1) |
| IDs (all new) | **Document 3145**<br>Chunks: 12<br>Insights: 5201–5204<br>**Claims 2389–2392**<br>Entity Integrity **44**; Truth Delta **97**; **memo 103** |
| Database | A new SQLite backup copy, `scratchpad/rc6c/db_rc6c_copy.sqlite3`, from the original opened `mode=ro`; `integrity_check` ok.<br>The gate refused it at `pending=1` (`zelda_api.0044`); the migration was applied to the copy only.<br>The wrapper refuses the original and all nine earlier run copies (memos 94–102).<br>Sequences were advanced in the copy only, to the memo-102 copy's maxima (document 3144, memo 102, claim 2388, TD 96, EI 43) |
| Broker / cache | Local Memurai db **1** (broker), db **6** (results and cache). See D-8. Worker `mcc6c@inventoroftues`, queue `celery`, solo, concurrency 1. Every other Redis db is unchanged; nothing was purged |
| Gates (inside both processes) | Server pid 11980 and worker pid 26120 each report:<br>• the six paid keys `False`; `ANTHROPIC_API_KEY` `True`;<br>• broker local on db 1/1/6/6;<br>• `DB-CHECK is_copy=True is_original=False is_historical_copy=False`;<br>• `SCHEMA-CHECK pending=0`;<br>• `CELERY_TASK_ALWAYS_EAGER=False`.<br>`preflight --local`: ok |
| Browser gate (before any model call) | **Passed.** Chrome "Browser 2" on this computer loaded a loopback probe (nonce shown, browser request logged) and then the run server's login page at 16:42:20 local, which the run server logged. See [15](15_browser_walks.json) `browser_gate` and D-10 |
| Memory | `tools/memwatch.ps1` (1,500 MB threshold) ran from before the tests until the run's processes were stopped. Its log holds only the start line, so no process crossed it. Free RAM at the checks was 0.84–1.25 GB, lower than memo 102's run; every step ran serially |
| Task order ([06](06_worker_chain.txt)) | 1. 2 fixture match refreshes.<br>2. `process_document_pipeline` (12 chunks, 4 insights).<br>3. `extract_claims_from_insights` (**4**).<br>4. `verify_entity_integrity` (44).<br>5. `verify_document_truth_delta` (97).<br>6. `generate_intelligence_memo` (**103**, 53.2 s).<br>7. `notify_document_processed` |
| Principals | `c6cmc_owner` (321, Application 50); `c6cmc_lite` (322); `c6cmc_paid` (323, Premium plus an active local `INVESTOR_PREMIUM` subscription 9 with fake Stripe IDs, no payment action); `c6cmc_staff` (324, real MFA setup in the probe and real TOTP verify in the browser); anonymous |
| Profile fixture | ManyChat; `prior_amount_raised=163000000`, `raising_amount=0`, revenue and reporting currency blank. Canary `CANARY-MANYCHAT-4417` in PRIVATE `reason_for_capital` |
| Preserved | Read-only snapshots are **byte-identical** before and after:<br>• memos 90/91 (with documents 3132/3133) in the original;<br>• memos 94–101 and **102** (with document 3144) from their run copies.<br>All ten source DB hashes and the deck hash are unchanged, with no sidecars. The original and memo 94–101 before-snapshots equal memo 102's run's committed after-snapshots (`6d131f5`) after normalisation. The stored fields of memos 97–**102** (24 each) equal their committed `09_memo.json` (`ea3ab13`, `0dd8e91`, `d821cca`, `d8b224c`, `82771ef`, `6d131f5`) before and after |

### Call ledger (every attempted model call)

All calls were recorded in-process by the run wrapper ([09c](09c_all_model_calls.json)). **8 attempted, 8 succeeded, 0 failed, 0 retried.** No second generation and no repeated question. The browser walks and the assessment replays made no call (the log stayed at 8).

| # | Process | Started (UTC) | Kind | Response id | Stop | Tokens in / out |
|---|---|---|---|---|---|---|
| 1 | worker | 23:42:50 | memo generation (`claude-sonnet-4-6`, `max_tokens` 4000) | `msg_011CgL4BQwx1J4Q5cxbHKjGo` | `end_turn` | 3,771 / 2,447 |
| 2 | server | 23:45:46 | `/ask/` Q1 query extraction | `msg_011CgL4QRKPDDgkABZ6QHZHP` | `end_turn` | 347 / 8 |
| 3 | server | 23:45:48 | `/ask/` Q2 | `msg_011CgL4QZW1qjTJgeXtsC1P8` | `end_turn` | 348 / 8 |
| 4 | server | 23:45:50 | `/ask/` Q3 | `msg_011CgL4QiENvYtANzU2QSyxf` | `end_turn` | 348 / 8 |
| 5 | server | 23:45:52 | `/ask/` Q4 | `msg_011CgL4QqSUBX3GsfRhXyRZ6` | `end_turn` | 348 / 8 |
| 6 | server | 23:45:54 | `/ask/` Q5 | `msg_011CgL4QyBJYGQEQzqBQA4qJ` | `end_turn` | 348 / 8 |
| 7 | server | 23:45:56 | `/ask/` Q6 | `msg_011CgL4R6Cy8Z88xt3ftyeGJ` | `end_turn` | 349 / 8 |
| 8 | server | 23:45:57 | `/ask/` Q7 | `msg_011CgL4RDYExDE3qKTn35rZn` | `end_turn` | 347 / 8 |

The seven questions are the recorded ones, verbatim ([scripts/probe_cfg.json.txt](scripts/probe_cfg.json.txt); the answer key's Q1–Q7). Each was asked once.

### Source map (the sent payload's refs; [17](17_grading_excerpts.json))

| Ref | Kind | Statement | Page | Context | Claim |
|---|---|---|---|---|---|
| C1 | claim | `$23.1M raised` (narrator Pitch Deck Hunt) | 2 | — | 2389 |
| **C2** | claim | `500M messages/month` | **12** | — | **2390** |
| **C3** | claim | `500M messages` | **10** | `Traction by Apr-16` | **2391** |
| C4 | claim | `140 000+ bots` | 10 | `Traction by Apr-16` | 2392 |
| S1 | statement | `140 000+ bots` | 10 (chunk 9) | `Traction by Apr-16` | — |
| S2 | statement | `500M messages` | 10 (chunk 9) | `Traction by Apr-16` | — |
| **S3** | statement | `500M messages/month` | **12** (chunk 11) | — | — |
| S4 | statement | `$23.1M raised` (narrator Pitch Deck Hunt) | 2 (chunk 1) | — | — |
| P1, P2 | profile | Stage: Series A; Sector: Software | — | — | — |

The consistency note sent was `{"kind": "measurement_basis", "refs": ["C3", "C2"], …}`, as before. The model payload equals the dump's rebuild and a fresh build for the generation principal, and equals **memo 102's payload** once document IDs are masked ([process/cmp_input_stdout.txt](process/cmp_input_stdout.txt)).

### What the guards did on the live reply ([09e](09e_guard_changes.txt), [09d](09d_memo_input_output_check.json))

- **No basis rule fired** (`basis_rule_fired: false`). No time-guard removal.
- **Funding guard: four edits**, all narrator or date qualifications:
  - `business_model_analysis`: "[P2]" → "[P2] (current profile, undated)" (`profile_undated`);
  - `information_readiness`, `what_would_change_the_picture` and `questions_for_management`: "(per Pitch Deck Hunt)" inserted (`attribution`).
- All 17 stored fields equal the replay of the raw reply through list normalisation, time, funding and basis. The replay is order-stable and idempotent, and citations stay in order.

### Surfaces and boundaries (HTTP probe and browser)

| Check | Result |
|---|---|
| Truth Delta 97 | 0 observations; all four claims "No external data found" (`no_data` → INSUFFICIENT); score None; `dataforb2b: unconfigured` |
| Entity Integrity 44 | `complete`; website not on the profile (not applicable); SEC EDGAR not found |
| Note visibility | "Measurement basis to clarify" with "not a verification result" on the owner's, paid's and staff's Truth Delta page: the same surfaces and flags as memo 102. Seen in the browser for paid and staff. The comparison script's third flag ("Page 10 states 500M messages") additionally matches three staff memo surfaces, because memo 103's own `risk_assessment` 2 uses those words ([scripts/note_vis.py.txt](scripts/note_vis.py.txt)) |
| Authorization ([11](11_authorization_matrix.json)) | **All 90 principal × surface rows identical to memo 102's run** (names and ids normalised). Every logout POST returns 302 and the protected profile then redirects |
| Reconciliation ([11b](11b_reconciliation_by_principal.json)) | Owner only: `not_comparable / profile_currency_unknown` |
| Canary | Only on the owner's and staff's profile page (`A_profile`). Never in model input, the memo, reports or API payloads, and not on any browser-walked page |
| Markdown ([14](14_markdown_utf8.json)) | `text/markdown; charset=utf-8`; **12,092 bytes; SHA-256 `b0ccf329830546ef3944da5e842440e4c486f18949f9aa8895a109028ff3a594`**; strict UTF-8; 18 `•`, 19 `—`; no mojibake; 0 replacement characters |
| Q1–Q7 ([10](10_retrieval_ask_q1_q7.json)) | Run **once**. Owner search and RAG 200; Q3's top pages are 10 and 12. `/ask/` 200 ×7, each the marketplace fallback "I couldn't find specific search criteria in that — …" |
| Browser walks ([15](15_browser_walks.json)) | **Completed** in Chrome on this computer: owner (IC memo), Lite (company overview; Truth Delta refused after logout), paid (Truth Delta), staff (real TOTP verify, Truth Delta, IC memo, company overview), anonymous (four protected URLs → `opaqueredirect`). Screenshots in [browser/](browser/); every request is in [browser/server_log_browser_walks.txt](browser/server_log_browser_walks.txt) |

### Deviations

- **D-1: ingest API upload.** As before.
- **D-2: repeated ID numbers.** Users 321–324, Application 50 and subscription 9 repeat earlier runs' numbers, as rows in a separate DB.
- **D-3: instrumentation.** In-process recording of `Messages.create`. No repo change, and no credentials recorded.
- **D-5: process stop.** Server, worker and watchdog were stopped by exact PID (11980, 26120, 14236, and the two launcher processes 6008 and 28092); their shells report exit 127 because of that stop.
- **D-8: Redis databases.** No Memurai db was empty and none was purged. Used: dbs 1 and 6, which held only the three static `_kombu.binding.*` sets with empty queues ([snapshots/redis_run_dbs_keys_before.txt](snapshots/redis_run_dbs_keys_before.txt)). Not used: dbs 3 and 4 (the memo-101 and memo-102 runs' cached embeddings).
- **D-10: browser selection.** The connected "Browser 1" failed four loopback probes (fresh nonces on 127.0.0.1:8765–8768): Chrome's error page, and no browser request in the probe server log; at the first probe this computer had no `chrome.exe` process at all. After the owner opened Chrome on this computer, "Browser 2" connected; the owner chose it, and its probe passed (nonce `8b9cafeda45da918` visible, `GET /index.html` and `/favicon.ico` logged). Probe pages and logs: [browser/loopback_gate/](browser/loopback_gate/). This resolves the memo-102 blocker (D-9 / OF-1015) for this run.
- **D-12: operator slips, none affecting the run.**
  1. After all eight calls, an empty inline `python -` heredoc (a shell check) hung and was stopped. It made no call and changed no file.
  2. `cmp_input.py`'s first printout still carried its template's "memo-101" label while comparing memo 102's payload; it was relabelled and rerun read-only with the same result ([process/cmp_input_stdout.txt](process/cmp_input_stdout.txt)).
- **Tracked `__pycache__` noise.** Running the tests and the read-only scripts rewrote tracked `.pyc` files in the run worktree (allowed by the Nike protocol, rule 2). None is committed; `CODE-DIFF` excludes them and reports 0 other files.

---

## Part 2: Provisional assessment (pending independent review)

**Everything in this part is my reading.** The grades are provisional, and the open questions are for the grader. Assessment-only analyses were run after the eight calls, read-only and without model calls; their outputs are in [assessment/](assessment/), separate from the execution record:
- [assessment/assess_replay.json](assessment/assess_replay.json): selected sentences replayed through the merged guard sequence (time → funding → basis) with document 3145's own context.
- [assessment/assess_brackets.json](assessment/assess_brackets.json): every citation bracket in the stored memo, in any form, with each ref resolved to its page and statement.

### Acceptance table

| Criterion (source) | Reading | Supporting excerpt (stored = raw reply unless stated) |
|---|---|---|
| **OF-1003: page 12's monthly statement does not inherit page 10's April-2016 context** (M6 / I1; grade `f2a282f`) | **FAIL (observed), provisional P2, blocking for RA-109** | `base_scenario`: "Taking the self-reported traction at face value without independent verification [S1, S2, S3], the company had deployed a meaningful bot platform by the period referenced in the 'Traction by Apr-16' slide context, with Pitch Deck Hunt listing $23.1M in prior funding [C1, S4]." S3 is page 12's monthly statement, with no context; the sentence dates it by page 10's "Traction by Apr-16" period. Displayed unchanged on the staff IC memo ([browser/staff_ic_memo_base_scenario.jpg](browser/staff_ic_memo_base_scenario.jpg)). See OF-1102 |
| OF-1003 class, conditional form | **Open (Q-1); my reading: same class, provisional P2** | `upside_scenario`: "If the company's self-reported 140,000+ bots [S1] and 500M messages/month [S3] are accurate and the per-month figure is the correct basis, ManyChat would represent a platform with significant throughput at the time of the 'Traction by Apr-16' slide …". See OF-1103 |
| **OF-1004: each figure's citations identify its own claim and statement** (M6; grade `f2a282f`) | **PASS** | All 39 brackets resolve; every group written after one figure cites that figure's page. Page 12's figure: "[C2/S3]" (`risk_assessment` 2, `zelda_advantage`), "[S3]" (8 sections). Page 10's: "[C3/S2]", "[C3]", "[S2]". Mixed groups are lists or comparisons naming both figures in order: "[C2, C3]", "[S2, S3]", "[C3 vs. C2, consistency note]", "[S1, S2, S3]". No group cites C3 for page 12's figure, or C2/S3 for page 10's |
| Each figure kept separate (page and context) elsewhere | **Pass** | `executive_summary`: "… on a slide headed 'Traction by Apr-16' [S1, S2], with a separate slide stating 500M messages/month [S3]"; `business_model_analysis`, `risk_assessment` 1 and 2, `open_concerns` 1 and `questions_for_management` 1 likewise |
| Page 10 not inferred cumulative (OF-906 class) | **Pass, with a P3 wording question (Q-2)** | Every "cumulative" is an alternative or a condition: `downside_scenario` "If the 500M messages figure refers to a cumulative total rather than a monthly run rate [C3 vs. C2, consistency note]"; scan `cumulative_presupposed` 0. But `risk_assessment` 1 "(total vs. per month)" and `information_readiness` "total vs. per-month [C2, C3]" call page 10's figure a "total". See OF-1105 |
| No contradiction or judgment from the two statements alone (OF-905 class) | **Pass, with P3 wording** | `judgment_wording`, `inflation_or_imprecise`, `figures_referent_with_judgment`, `other_interval_or_page_with_judgment` all 0. The one `basis_contradiction_label` hit is product copy on the company overview ("none of the 4 claims could be verified or contradicted against a public source"). "Measurement-basis inconsistency" and "inconsistency" are OF-910 class (OF-1108) |
| No annualisation | **Pass** | `ra109_annualised_or_converted` 0 |
| Clarification sought | **Pass** | `questions_for_management` 1: "Do the '500M messages' on the traction slide [S2] and '500M messages/month' on the separate slide [S3] refer to the same metric? …"; `information_readiness` "Needs Validation"; `open_concerns` 1 |
| Interval wording | **Pass** | "(no interval stated)", "without an explicit interval", "without an interval" used for page 10 only; `unspecified_interval_relabel` 0, `basis_guard_wording` 0 |
| Subject ownership, clause preservation (PR #287), citation and condition rules (PR #288) | **Pass where exercised; mostly not exercised** | No basis rule fired. The guards deleted and replaced nothing. Replay with this run's context: the merged guard corrects memo 101's OF-904 sentence (`basis_source_context`), memo 102's OF-1003 sentence (`basis_condition_context`) and memo 102's OF-1004 sentence (`basis_citation_identity`) exactly as reviewed, and leaves memo 103's sentences unchanged |
| OF-807: conditions not attributed to the company | **Pass** (did not recur) | `upside_scenario` keeps its conditions as "if"s; `questions_for_management`: "what share of the 140,000+ bots [S1] are paying versus free-tier users?" |
| Facts, qualifications, conditions, questions and narrator preserved | **Pass** | The four guard edits add a narrator or "(current profile, undated)"; nothing was removed |
| April-2016 traction historical | **Pass** | "at the time of the 'Traction by Apr-16' slide", "by the period referenced in …"; `historical_as_current` 0 |
| $23.1M attributed, not current or verified | **Pass, with P3 (OF-909 class and a narrator question)** | `funding_sentence_missing_narrator` 0 across 55 sentences on 51 surfaces; "Pitch Deck Hunt lists $23.1M raised [C1, S4] … could not be confirmed"; `runway_or_cash_premise` 0. See OF-1107 |
| Platform counts not user counts | **Pass** | `platform_user_counts` 0 |
| No SEC identity, revenue, external verification or advice (Q4, Q5, Q7) | **Pass, with the RA-108 note** | Entity Integrity: SEC EDGAR not found; revenue "Not found in the extracted evidence"; the only `advice_words` hits are "Buy 3 Truth Delta credits" product copy |
| Raw vs persisted | Shown | Identical except the four funding-guard edits ([09e](09e_guard_changes.txt)) |
| Browser: owner, Lite, paid, staff/MFA, anonymous | **Pass (first complete browser record since memo 101)** | [15](15_browser_walks.json); see OF-1113 |

### Ledger

| ID | Layer | Principal | Observation | Key ref | Grade (provisional) | Bucket | Sev | Blocking |
|---|---|---|---|---|---|---|---|---|
| OF-1101 | 3–9 | all / model input | Four expected claims (2389–2392), identical to memo 102's; request = rebuild = fresh build = memo-102 payload (doc ids masked); rules present; no key, review, guard or canary text | M2–M6 / I1 | PASS | — | — | No |
| OF-1102 | 9 | staff (memo API, IC memo, download), Markdown | `base_scenario` dates page 12's S3 by page 10's "Traction by Apr-16" period ("Taking the self-reported traction at face value without independent verification [S1, S2, S3], the company had deployed a meaningful bot platform by the period referenced in the 'Traction by Apr-16' slide context, with Pitch Deck Hunt listing $23.1M in prior funding [C1, S4]"). Same shape as memo 101's graded OF-904 base sentence. **No guard edit.** Read-only replay: the merged guard corrects memo 101's sentence but not this one; removing either "without independent verification" or the trailing ", with Pitch Deck Hunt listing … [C1, S4]" clause alone still leaves it unchanged, removing both makes `basis_source_context` correct it ([assessment/assess_replay.json](assessment/assess_replay.json)) | M6 / OF-904, OF-1003 | **FAIL: OF-1003 / OF-904 class recurred in a new wording** | PHASE1-GROUNDING | P2 | **Yes for RA-109** |
| OF-1103 | 9 | staff, Markdown | `upside_scenario`: the condition is accuracy and basis ("are accurate and the per-month figure is the correct basis"), and the consequence places S3's monthly figure "at the time of the 'Traction by Apr-16' slide". Unlike memo 101's non-blocking upside ("If … [S3] reflects a monthly run-rate as of the 'Traction by Apr-16' slide context"), the date is not itself the hypothesis. By `f2a282f`'s reasoning for OF-1003 ("'Taken at face value' does not establish that S3 shares page 10's date"), "accurate" does not either. No guard edit | M6 / OF-904 (conditional) | **Open (Q-1)**; my reading: same class | PHASE1-GROUNDING | P2 (provisional) | Open |
| OF-1104 | 9 | all | OF-1004 did not recur: 39 brackets resolved, each figure's group names its own claim and statement ([assessment/assess_brackets.json](assessment/assess_brackets.json)) | M6 / OF-1004 | PASS | — | — | No |
| OF-1105 | 9 | Lite, paid, staff | OF-905 and OF-906 did not recur (no judgment; "cumulative" only as an alternative or condition). Wording: "(total vs. per month)" (`risk_assessment` 1) and "total vs. per-month" (`information_readiness`) call page 10's no-interval figure a "total", which the evidence does not state | M6 / OF-806, UB-604 | PASS; wording **Q-2** (P3 or OF-906 class?) | INTEL-QUALITY | P3 (provisional) | No |
| OF-1106 | 9 | staff | OF-807 did not recur | M5 / OF-807 | PASS | — | — | No |
| OF-1107 | 9 | all | Funding attributed on every surface; four narrator/undated insertions. **P3 (OF-909 class):** "would establish how much of the narrated $23.1M raised (per Pitch Deck Hunt) remains available"; "how long reported funding would sustain operations". **Q-3:** `supported_points` "Pitch Deck Hunt lists a cumulative funding figure of $23.1M raised [C1, S4]; … it indicates the company has sought to characterise a meaningful prior capital history" credits the company with Pitch Deck Hunt's listing | M1 / NP-603, NP-604, OF-909 | PASS; wording P3; Q-3 open | INTEL-QUALITY | P3 | No |
| OF-1108 | 9 | staff; Lite/paid for `information_readiness` | Wording (OF-910 class): `zelda_advantage` "The verification pass identified a specific internal measurement-basis inconsistency" (**RA-108 recurrence**); `risk_assessment` 2 "Measurement-basis inconsistency"; "two figures that are numerically identical"; `questions_for_management` 1 "which measurement basis is correct" (presupposes one is wrong); `downside_scenario` "[C3 vs. C2, consistency note]" names internal machinery | M6 / RA-108 | Observations (OF-910 class) | INTEL-QUALITY | P3 | No |
| OF-1109 | 9 | Lite, staff | Inference beyond the evidence, hedged: `executive_summary` "operating in the chatbot/messaging automation space" (the evidence gives bots, messages and the Software sector); `risk_assessment` 5 "operating on third-party messaging infrastructure (implied by the product category)". `outside_knowledge_platform` 0 | M1 | Observation (Q-4) | INTEL-QUALITY | P3 (provisional) | No |
| OF-1110 | 10 | all | Truth Delta: 0 observations, 4 INSUFFICIENT, score N/A; note shown with "not a verification result" (owner, paid, staff; browser for paid and staff). Entity Integrity: SEC not found | E1, M1–M6 | PASS | — | — | No |
| OF-1111 | 9–10 | all | 90-row matrix identical to memo 102; owner-only reconciliation; canary boundaries; UTF-8 Markdown | M1 | PASS | — | — | No |
| OF-1112 | 9 | owner | `/ask/` 200 ×7 marketplace fallbacks: not document answers | Q1–Q7 | **RA-114 open** (unchanged) | PRODUCT-UI | — | No (separate) |
| OF-1113 | — | owner, Lite, paid, staff, anon | **Browser walks completed** in Chrome on this computer after the loopback gate (D-10): IC memo, company overview, Truth Delta, real staff TOTP, anonymous redirects; no canary on any walked page; logouts via the nav form (paid via `/`, FF-413) | M1 / D-9, OF-1015 | PASS (resolves the memo-102 browser blocker for this run) | PROCESS | — | No |
| OF-1114 | 9 | — | Guard coverage: no basis rule fired. OF-1102 is a shape the merged `basis_source_context` rule does not read when the "face value" phrase carries a hedge ("without independent verification") or the sentence continues with another clause (", with Pitch Deck Hunt listing … [C1, S4]"). `basis_facts` built from reversed items is again not equal as an object; the output is identical (OF-815 carried) | — | Observation | CORRECTNESS | P2 driver (see OF-1102) | — |
| OF-1115 | — | — | Unchanged and **not closed by this run**: RA-108 (OF-1108), RA-114 (OF-1112); RA-103, FF-413 (seen again in the paid walk), RA-105, PF-206/FF-311, NP-508/509; P3 basis-note rounding; slash and "vs." citations not recognised by `_REF` (four such brackets here: "[C3/S2]", "[C2/S3]" ×2, "[C3 vs. C2, consistency note]") | — | Open | — | — | No |

### Open grading questions

- **Q-1 (OF-1103):** is the upside's "If … [S3] are accurate and the per-month figure is the correct basis, ManyChat would represent … at the time of the 'Traction by Apr-16' slide" an unsupported date transfer (my reading, as for OF-1003), or a conditional the grader treats as non-blocking like memo 101's upside?
- **Q-2 (OF-1105):** does calling page 10's no-interval figure a "total" ("total vs. per month") count as OF-906 class (presupposing a basis), or as P3 wording?
- **Q-3 (OF-1107):** does "it indicates the company has sought to characterise a meaningful prior capital history", after "Pitch Deck Hunt lists …", credit the company with the narrator's figure (NP-603/604 class), or is it P3?
- **Q-4 (OF-1109):** are the hedged product-category inferences acceptable, or an inference leak?

### RA-108 and RA-114 coverage

- **RA-108:** the protocol covers it only through the memo's wording. "The verification pass identified …" recurred in `zelda_advantage` (OF-1108, P3). **Open; this run does not test or close it.**
- **RA-114:** covered by Q1–Q7 through `/ask/`. All seven are still the marketplace fallback (OF-1112). **Open.**

## Summary

| Category | Items |
|---|---|
| **Observed failures** (provisional) | **OF-1102** (`base_scenario`: page 12's S3 dated by page 10's "Traction by Apr-16" period; OF-1003 / OF-904 class in a wording the merged guard does not read; P2, blocking) |
| **Open** (provisional, for the grader) | **OF-1103** (upside conditional, Q-1; my reading P2); Q-2, Q-3, Q-4 (P3 wording) |
| **Passed** | OF-1004 (citation identity); separation elsewhere; OF-905, OF-906, OF-807 did not recur; no annualisation; clarification sought; interval wording; funding attribution; historical framing; no platform counts, identity or advice; Truth Delta and Entity Integrity states; matrix, reconciliation, canary, Markdown; **browser walks for all five principals**; 382 tests and checks on the merged code; all earlier records preserved |
| **Not tested / still open** | RA-108 (wording only; recurred P3), RA-114 (fallbacks), and the carried items in OF-1115. The PR #288 guard rules were not exercised by this reply |

**Run's reading:** this sample does **not** meet the RA-109 output criteria, because OF-1003's class recurred (OF-1102). RA-109 acceptance stays pending independent review, and overall hardening is not complete.

## Artifacts

- [00](00_setup.json): setup, gates, isolation, Redis, sequences, DB hashes, preservation, frozen-artifact checks, model calls.
- [01](01_extraction.json)–[09](09_memo.json): pipeline rows.
- [09a](09a_grounded_context_rebuilt.json)–[09f](09f_section_scan.txt): rebuild, the memo model call (raw reply), all 8 calls, input/output and four-step replay, guard edits, sentence scan.
- [10](10_retrieval_ask_q1_q7.json), [11](11_authorization_matrix.json), [11b](11b_reconciliation_by_principal.json), [12](12_api_payloads.json), [13](13_rendered_reports_text.json): HTTP probe.
- [14](14_markdown_utf8.json) and [14_ic_memo_export.md](14_ic_memo_export.md): Markdown export.
- [15](15_browser_walks.json) and [browser/](browser/): the browser gate and walks, screenshots, server-log lines.
- [16](16_probes.json): numeric-parse probes.
- [17](17_grading_excerpts.json): source map, raw reply, raw and stored text of every section, standard-form citation groups resolved to pages.
- [assessment/](assessment/): assessment-only replays and citation resolution.
- [process/](process/), [scripts/](scripts/), [snapshots/](snapshots/).
