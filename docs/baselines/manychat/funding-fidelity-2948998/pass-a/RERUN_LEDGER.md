# ManyChat — post-merge funding-fidelity Pass A ledger at `2948998`

**A new, separate live run.** It does not edit or replace any earlier record:
- the frozen narrow run (document 3129);
- the 458bdc9 rerun (document 3133, memo 91);
- the post-fix run (document 3136, memo 94). Its ledger and OWNER_GRADING.md are on branch `docs/manychat-postfix-a975af3` (88df894), graded **partial pass**.
- the funding-fidelity evidence on main (`docs/baselines/three-deck-audit/funding-fidelity-*`).

Graded against the frozen [../../ANSWER_KEY.md](../../ANSWER_KEY.md) under
[../../../three-deck-audit/PROTOCOL.md](../../../three-deck-audit/PROTOCOL.md) and
[../../../nike-fy2026/PROTOCOL.md](../../../nike-fy2026/PROTOCOL.md). The key was used for grading only; none of its text reached
the model ([09d](09d_memo_input_output_check.json)).

**Status: ungraded by the owner. RA-106 and Zelda hardening stay PENDING until these artifacts are graded.** The grades
below are the run's own reading. Nothing was deployed. No application code was changed during the run.

## Run record

| Item | Value |
|---|---|
| Date | 2026-10-12 (upload 09:52:27 UTC) |
| Code | main `2948998c0af4b27a7b773abd3441f15187cb8e2d`, "Merge pull request #279 from jonmaso-hash/fix/funding-source-fidelity". A **merge commit, not a squash**: 2befa42, a0ac9ad, 3481d8f and 2230090 are all ancestors, and main's tree is byte-identical to 2230090. Detached worktree `KCV-mc-ff`; no `.py` or template changes |
| Deck | `manychat_series_a_audit_deck.pptx`, 175,622 bytes, SHA-256 `be7a7171bbc84b9895a45adfbc41f2533f3d23b3a4a561c82a8d9de6b94f3ef1`: matches the protocol on disk and in the upload process. **One upload** |
| IDs | Document **3137** (`analyzed`, `complete`). Chunks 12; insights 5172–5174; claims **2360** `funding_raised`, **2361** `usage` messages, **2362** `usage` bots; Entity Integrity report **36**; Truth Delta report **89**; memo **95**. All new: see D-3 |
| Database | An sqlite backup **copy** of the dev DB. `zelda_api.0044` applied to the copy only. Original `db.sqlite3` SHA-256 `5a0b8c1c…7e9a2` identical before and after |
| Broker / cache | Local Memurai, run-only databases: broker 11, results 12, cache 13, all empty before. Worker `mcff@…`, queue `celery` on db 11 only. Redis 0/2 (other work) and 8/9/10 (previous run) unchanged |
| Gates | Before migrating, the wrapper refused to start (`pending=1 ['zelda_api.0044_claim_source_context']`). After: `preflight --local` ok. In both server and worker: six paid keys `False`, `ANTHROPIC_API_KEY` `True`, brokers `redis://localhost` 11/11/12/13, `DB-CHECK is_copy=True`, `SCHEMA-CHECK pending=0` (0035, 0044, 0083, 0095), `CELERY_TASK_ALWAYS_EAGER=False` ([00](00_setup.json)) |
| Memory | `tools/memwatch.ps1` throughout; no process over 1,500 MB. Test-free run |
| Worker chain | pipeline (12 chunks, 3 insights) → claims (3) → Entity Integrity (36) → Truth Delta (89) → memo (**95**, 47.3 s) → notify ([06](06_worker_chain.txt)). The guard logged changes in 5 sections |
| Model | Memo: one live call, `claude-sonnet-4-6`, `max_tokens` 4000, `end_turn`, 3,199 in / 2,192 out tokens. Plus 7 `/ask/` query-extraction calls from the HTTP probe ([09b](09b_model_call.json), [09c](09c_all_model_calls.json)) |
| Principals | `ffmc_owner` (321, Application 50, not Premium), `ffmc_lite` (322), `ffmc_paid` (323, `is_premium` + active `INVESTOR_PREMIUM` subscription 9), `ffmc_staff` (324, staff MFA), anonymous |
| Profile fixture (§E) | `company_name="ManyChat"`, `prior_amount_raised=163000000`, `raising_amount=0`, revenue blank, **reporting currency blank**, canary `CANARY-MANYCHAT-4417` in `reason_for_capital` (PRIVATE) |
| Preserved | Memos 90/91 and documents 3132/3133 identical before and after (read-only snapshots). Memo 94 and document 3136 in the previous run's copy are identical, and that copy's SHA-256 (`445a2f19…`) is unchanged ([snapshots/](snapshots/)) |

### Deviations

- **D-1 / D-2:** detached worktree; upload through the session-authenticated ingest API, as in earlier runs.
- **D-3 (new): new IDs.** Both run copies derive from the same original, so the IDs would have repeated the previous run's (document 3136, memo 94). In **this copy only**, the zelda_api AUTOINCREMENT counters were advanced to the previous run's maxima, read read-only from that run's copy ([00](00_setup.json) `id_sequences_advanced_in_copy_only`). User and profile IDs (321–324, 50) still match the previous run's numbers, but they are separate rows in a separate DB.
- **D-4: read-only snapshots.** The old snapshot wrapper's worktree (`KCV-bw007`) no longer exists, and so is `KCV-mc-postfix`. Snapshots used a new read-only runner (`PRAGMA query_only = ON`) on the new worktree's code, reading only pk and timestamp columns ([scripts/](scripts/)).
- **D-5: instrumentation.** In-process recording of `anthropic` `Messages.create` (request kwargs and reply). No repo change; no credentials in kwargs.
- **D-6: Markdown export.** Read with an in-page `fetch`, so Chrome saved no file (~/Downloads unchanged this run). The HTTP probe also captured it ([13](13_rendered_reports_text.json) `STAFF:E_ic_memo_dl`).

## Memo input and output

**Input** ([09b](09b_model_call.json)) equals the payload rebuilt from the stored rows ([09a](09a_grounded_context_rebuilt.json)).
- Prompt rule 10 is present.
- C1/S3 `$23.1M raised` carry `as_of: not stated`, `narrator: Pitch Deck Hunt` and `dates_not_as_of: ["2015"]`.
- C2/C3 and S1/S2 carry `source_context: Traction by Apr-16`.
- P1/P2 are profile stage and sector.
- **Absent from the input:** "Series A deck with", "SlideShare deck has", the canary, 163,000,000, Bessemer, TechCrunch, Summit Partners, 2019, $18M, STALENESS, ATTRIBUTION ERROR.

**Output.** Every stored section equals a replay of the time-wording and funding-fidelity guards on the model's reply ([09d](09d_memo_input_output_check.json)). The guard changed 5 sections ([09e](09e_guard_changes.txt)):

| Section | Model wrote | Stored (after the guard) |
|---|---|---|
| `risk_assessment` | "The $23.1M raised figure [S3] carries no stated date…" | "The $23.1M raised figure **(per Pitch Deck Hunt)** [S3] carries no stated date…" |
| `information_readiness` | "• Self-reported funding raised: $23.1M [S3]" | "• **reported by Pitch Deck Hunt** funding raised: $23.1M [S3]" (FF-302) |
| `what_would_change_the_picture` | "…the $23.1M funding figure [S3] against remaining runway." | "…the $23.1M funding figure **(per Pitch Deck Hunt)** [S3] against remaining runway." (FF-303) |
| `upside_scenario` | "…if the $23.1M raised [S3] was deployed efficiently with meaningful runway remaining, … before seeking **this round**." | "…$23.1M raised **(per Pitch Deck Hunt)** [S3] … before seeking **any current or planned raise**." (FF-304) |
| `questions_for_management` | "Who are the investors behind the $23.1M raised, …" | "…the $23.1M raised **(per Pitch Deck Hunt)**, …" |

The model itself wrote "Pitch Deck Hunt lists $23.1M raised" in the executive summary, financial analysis and supported points, and "narrated by Pitch Deck Hunt" in open concerns and Zelda advantage.

## Section checks ([09f](09f_section_scan.txt), then rendered in Chrome)

| Check | Result |
|---|---|
| Pitch Deck Hunt attached to its funding figure | **PASS.** Every sentence stating $23.1M names Pitch Deck Hunt: 10/10 in stored sections, 10/10 in the staff full IC memo, 10/10 in the Markdown, and in the Lite overview, Lite memo API and owner Lite memo |
| No unsupported current total ("to date", "so far", "in total", "cumulative" for funding) | **PASS.** No such wording on funding; "cumulative" appears only in questions about how the bot and message counts are defined |
| No unsupported active raise / proceeds | **PASS.** No "this raise" / "stated raise" on any surface. The only raise wording is the question "Is there a current fundraise planned, and if so, what are the intended use of proceeds…", which keeps the premise conditional. "Use of proceeds: Not found" and "Runway: not calculated" are gaps |
| No unsupported runway premise | **FAIL (FF-303)** in `what_would_change_the_picture`: "against remaining runway". Borderline (FF-304) in a conditional upside scenario |
| Undated profile stage kept apart from slide dates | **PASS.** Stage always appears as "profile-listed as Series A [P1, P2]", "Stage: Series A (profile) [P1]" or "Stage (Series A, profile) [P1]", never beside a slide date. Memo 95 did not repeat memo 94's "was Series A … as of April 2016", so the "(current profile, undated)" label was not exercised |
| Citations | **PASS.** Preserved through every guard change (stored = guard replay; no citation lost or moved) |
| Lists | **PASS.** HTML lists (6, 3, 18, 10, 5 items); Markdown 15 `- ` items; no list repr anywhere |
| Counts | **PASS.** 3 / 0 / 3 and "(of 3)" on every Truth Delta page, IC memo, Markdown and overview |
| Privacy | **PASS.** Canary only in the owner's and staff's profile; owner panel only for the owner; search/RAG only owner and staff; anonymous refused everywhere; no canary or fixture amount in model input or any memo surface |

## Grades against the key (run's reading; owner grading pending)

| ID | Observation | Grade |
|---|---|---|
| M1 $23.1M | INSUFFICIENT (`no_data`); attributed to Pitch Deck Hunt on every surface; undated; never current; 2015 not used | INSUFFICIENT, no STALENESS ERROR. Attribution PASS; runway wording FF-303 |
| M2–M4 | Not extracted; no platform user count in the memo | No ATTRIBUTION ERROR |
| M5 | Bots INSUFFICIENT, dated by "Traction by Apr-16" | INSUFFICIENT, dated |
| M6 / I1 | Slide 12 "/month" not extracted; conflict not flagged (the memo asks how messages are measured) | I1 missed (RA-109) |
| M7 / M8 | Not extracted | Allowed |
| E1–E3 | Entity Integrity 36: `sec_filer` `not_found`; no invented identity | PASS |
| Q1–Q7 | Search/RAG 200 (owner), ties, `no_relevant_evidence` false; `/ask/` is marketplace query extraction for all seven | As before (RA-114) |

## Authorization matrix ([11](11_authorization_matrix.json); Chrome walks [15](15_browser_walks.json))

Same shape as the post-fix run:

| Surface | Owner | Lite | Paid | Staff | Anon |
|---|---|---|---|---|---|
| Overview `/matchmaking/memo/profile/50/` | 403 (by design) | 200 Lite | 200 Lite | 200 Full | 302 |
| IC memo / Markdown | 200 Lite / 302 | 404 / 404 | 404 / 404 | 200 Full / 200 | 302 / 302 |
| Truth Delta page | 200 + owner panel | 200 | 200 | 200 | 302 |
| Memo API | 200 | 200 `lite_sections` | 200 `lite_sections` | 200 full | 403 |
| Search / RAG | 200 | 403 | 403 | 200 | 403 |

## Ledger

| ID | Layer | Principal | Observation | Key ref | Grade | Bucket | Sev | Blocking |
|---|---|---|---|---|---|---|---|---|
| FF-301 | 9 | all memo readers | Pitch Deck Hunt attribution on every $23.1M sentence, in full and Lite views, standalone sections, questions and the Markdown. The guard supplied it in 5 sections | M1 | PASS | — | — | No |
| FF-302 | 9 | owner, Lite, paid, staff | `information_readiness`: the guard turned "• Self-reported funding raised: $23.1M [S3]" into "• **reported by Pitch Deck Hunt** funding raised: $23.1M [S3]". The attribution is right, but sentence-initial capitalisation is lost and the phrase is ungrammatical. Visible in the Lite memo, the Lite memo API, the full memo and the Markdown | M1 | Wording defect | PRODUCT-UI | P3 | No |
| FF-303 | 9 | full-memo readers, Lite (what-would-change is a Lite section) | `what_would_change_the_picture`: "…anchor assessment of the $23.1M funding figure (per Pitch Deck Hunt) [S3] **against remaining runway**." This treats reported funding as cash with runway left. The guard covers "this raise" / "the stated raise" premises but not runway or remaining-cash wording | M1 | Unsupported runway premise | PHASE1-GROUNDING | P2 | No |
| FF-304 | 9 | full-memo readers | `upside_scenario`: "if the $23.1M raised (per Pitch Deck Hunt) [S3] was deployed efficiently with meaningful runway remaining" (conditional), and the guard's rewrite "before seeking any current or planned raise" reads awkwardly | M1 | Borderline; for owner | INTEL-QUALITY | P3 | No |
| FF-305 | 9 | full-memo readers | `base_scenario`: "Taking the **self-reported** figures at face value [S1, S2, S3], ManyChat had meaningful bot-platform traction by April 2016 and **had raised a material amount of capital**." S3 is Pitch Deck Hunt's listing, called self-reported, and the sentence can be read as dating the funding to April 2016. The sentence states no amount, so the guard does not act | M1 | Attribution softened; possible dating | INTEL-QUALITY | P3 | No |
| FF-306 | 9 | all | Profile stage always labelled as profile and never beside a slide date. The memo-94 conflation did not recur, so the guard's label was not exercised | §E | PASS | — | — | No |
| FF-307 | 9 | all | No active-raise or proceeds premise. The question "Is there a current fundraise planned, and if so, what are the intended use of proceeds…" keeps a legitimate conditional | M1 | PASS | — | — | No |
| FF-308 | 9 | all | No "to date" or current-total wording on funding (RA-106 scope) | M1 | PASS | PHASE1-GROUNDING | — | No |
| FF-309 | 5, 9 | all | Counts 3/0/3 and "(of 3)", lists rendered, citations preserved through every guard edit | — | PASS | — | — | No |
| FF-310 | 10 | all | Privacy and tier boundaries hold (matrix and Chrome); no canary or fixture value in model input or any memo surface | — | PASS | — | — | No |
| FF-311 | 9 | owner vs staff | PF-206 unchanged: Section Coverage 31.2% (owner Lite) vs 100.0% (full and Markdown) for the same memo | — | — | PRODUCT-UI | P3 | No |
| FF-312 | 5–9 | — | Unchanged open items: RA-109/I1 (slide 12 "/month" not extracted), RA-103 (claim from the audit-framing slide, ownership `named`), RA-108 (Zelda advantage self-credit), RA-114 (`/ask/`), RA-105 (B-2 `not_comparable` with a blank currency) | — | As before | — | — | No |

No defect was repaired during the run.

## Summary

On a live run of the merged code (`2948998`), the funding-source fidelity fix does its main job:
- Every sentence that states the $23.1M names Pitch Deck Hunt, in full and Lite views, standalone sections, questions and the Markdown.
- No active-raise, proceeds or current-total premise appears.
- The profile stage stays undated.
- Citations, lists, counts and privacy boundaries hold.

The guard supplied the attribution in 5 sections and removed one "this round" premise. It also produced one ungrammatical rewrite (FF-302). Not fixed:
- one runway premise on the reported funding (FF-303);
- a conditional runway phrase (FF-304);
- a base-scenario sentence that calls the listing "self-reported" without stating the amount (FF-305).

**RA-106 and Zelda hardening stay pending until the owner grades this run.**

## Artifacts

- [00](00_setup.json): setup, gates, isolation, ID sequences, preservation.
- [01](01_extraction.json)–[09](09_memo.json): pipeline rows.
- Memo input and output: [09a](09a_grounded_context_rebuilt.json) rebuilt input, [09b](09b_model_call.json) model call, [09c](09c_all_model_calls.json) all calls, [09d](09d_memo_input_output_check.json) input/output check, [09e](09e_guard_changes.txt) guard changes, [09f](09f_section_scan.txt) section scan.
- HTTP probe: [10](10_retrieval_ask_q1_q7.json)–[13](13_rendered_reports_text.json).
- Chrome: [15](15_browser_walks.json) and [browser/](browser/).
- Probes: [16](16_probes.json).
- [process/](process/): server and worker logs. [scripts/](scripts/): the run's scripts. [snapshots/](snapshots/): read-only before/after snapshots.
