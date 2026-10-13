# ManyChat — post-merge funding-fidelity Pass A ledger at `9b6d215`

**A new, separate live run.** It edits or replaces no earlier record:
- the frozen narrow run (document 3129);
- the 458bdc9 rerun (document 3133, memo 91);
- the post-fix run (document 3136, memo 94), graded partial pass (88df894 on `docs/manychat-postfix-a975af3`);
- the first post-merge funding-fidelity run (document 3137, memo 95), graded partial pass ([OWNER_GRADING.md](../../funding-fidelity-2948998/pass-a/OWNER_GRADING.md) on `docs/manychat-funding-fidelity-2948998`, 9688474);
- the funding-fidelity evidence on main (`docs/baselines/three-deck-audit/funding-fidelity-*`).

Graded against the frozen [../../ANSWER_KEY.md](../../ANSWER_KEY.md) under
[../../../three-deck-audit/PROTOCOL.md](../../../three-deck-audit/PROTOCOL.md) and
[../../../nike-fy2026/PROTOCOL.md](../../../nike-fy2026/PROTOCOL.md). The key was used for grading only; none of its text reached
the model ([09d](09d_memo_input_output_check.json)).

**Status: ungraded by the owner. RA-106 and Zelda hardening stay PENDING until this run is independently graded.** The grades
below are the run's own reading. Nothing was deployed, paid-source Pass B was not run, and no application code was changed.

## Run record

| Item | Value |
|---|---|
| Date | 2026-10-13 (upload 07:57:53 UTC) |
| Code | origin/main `9b6d215a55027e39482006d8b6d17cfef8de091b`, "Merge pull request #280 from jonmaso-hash/fix/funding-cash-and-mixed-refs". Parents 2948998 and 313a4e4; the reviewed correction `7c71995` is an ancestor, and main's tree equals 313a4e4. No migrations since 2948998. Detached worktree `KCV-mc-ff3`; no `.py` or template changes |
| Deck | `manychat_series_a_audit_deck.pptx`, 175,622 bytes, SHA-256 `be7a7171bbc84b9895a45adfbc41f2533f3d23b3a4a561c82a8d9de6b94f3ef1`: matches the key on disk and in the upload process. **One upload** |
| IDs (all new) | Document **3138** (`analyzed`, `complete`). Chunks 12; insights 5175–5177; claims **2363** `funding_raised`, **2364** `usage` messages, **2365** `usage` bots; Entity Integrity report **37**; Truth Delta report **90**; memo **96** |
| Database | An sqlite backup **copy** of the dev DB (`mcff3/db_ff3_copy.sqlite3`). `zelda_api.0044` applied to the copy only. Original `db.sqlite3` SHA-256 `5a0b8c1c…7e9a2`, identical before and after |
| Broker / cache | Local Memurai, run-only databases: broker **3**, results **4**, cache **5**, all empty before. Worker `mcff3@…` on db 3 only. Every other Redis db has the same key count before and after ([snapshots/](snapshots/)) |
| Gates | Before migrating, the wrapper refused to start (`pending=1 ['zelda_api.0044_claim_source_context']`). After: `preflight --local` ok. Server and worker each print: six paid keys `False`, `ANTHROPIC_API_KEY` `True`, brokers `redis://localhost` 3/3/4/5 `local=True`, `DB-CHECK is_copy=True is_original=False`, `SCHEMA-CHECK pending=0` (0035, 0044, 0083, 0095 present), `CELERY_TASK_ALWAYS_EAGER=False` ([00](00_setup.json)) |
| Memory | `tools/memwatch.ps1` (threshold 1,500 MB) throughout: no process crossed it. No tests run |
| Worker chain | pipeline (12 chunks, 3 insights) → claims (3) → Entity Integrity (37) → Truth Delta (90) → memo (**96**, 47.4 s) → notify ([06](06_worker_chain.txt)). The funding guard logged changes in 2 sections; the time guard removed nothing |
| Model | Memo: one live call, `claude-sonnet-4-6`, `max_tokens` 4000, `end_turn`, 3,317 in / 2,190 out tokens. Plus 7 `/ask/` query-extraction calls from the HTTP probe ([09b](09b_model_call.json), [09c](09c_all_model_calls.json)) |
| Principals | `ff3mc_owner` (321, Application 50, not Premium), `ff3mc_lite` (322), `ff3mc_paid` (323, `is_premium` + active `INVESTOR_PREMIUM` subscription 9), `ff3mc_staff` (324, `is_staff`, real staff-MFA setup then verify), anonymous |
| Profile fixture (§E) | `company_name="ManyChat"`, `prior_amount_raised=163000000`, `raising_amount=0`, revenue blank, **reporting currency blank** (currency erratum carried forward: B-2 is `not_comparable / profile_currency_unknown`, not the key's `differs`), canary `CANARY-MANYCHAT-4417` in `reason_for_capital` (PRIVATE) |
| Preserved | Read-only snapshots (`PRAGMA query_only`), identical before and after: memos 90/91 and documents 3132/3133 (original DB); memo 94 / document 3136 (post-fix copy, SHA-256 `445a2f19…` unchanged); memo 95 / document 3137 (memo-95 copy, SHA-256 `2c5f5864…` unchanged). The memo 90/91 and 94 snapshots also equal the previous run's after-snapshots |

### Deviations

- **D-1 / D-2:** detached worktree; upload through the session-authenticated ingest API, as in earlier runs (the upload widget was removed in #242).
- **D-3: new IDs.** Every run copy derives from the same original. In **this copy only**, the zelda_api AUTOINCREMENT counters were advanced to the memo-95 run copy's maxima, read read-only ([00](00_setup.json) `id_sequences_advanced_in_copy_only`). User and profile IDs (321–324, 50) repeat earlier runs' numbers, but they are separate rows in a separate DB.
- **D-4: read-only snapshots** with `run_ro.py` on this worktree's code, reading only pk and timestamp columns plus whole-memo hashes.
- **D-5: instrumentation.** In-process recording of `anthropic` `Messages.create` (request kwargs and reply). No repo change; no credentials in kwargs.
- **D-6: Chrome mechanics.** Sign-in set the form fields and called `form.requestSubmit()`. The Markdown export was read with an in-page `fetch` (no file saved). The staff Truth Delta page was checked by in-page fetch and parse, not by navigation; the other four principals' Truth Delta checks were navigations. The HTTP probe's copy of the staff Markdown in [13](13_rendered_reports_text.json) shows mojibake (`â¢`): the response is `text/markdown` with no charset, and the probe's `requests` decoded it as Latin-1. Chrome's UTF-8 decode of the same bytes is clean. Recorded as FF-411, not as a memo defect.
- **D-7: process stop.** Server and worker were stopped by command-line match after the walks; the match also ended their background shell wrappers (reported as exit 255). Nothing else matched.

## Memo input and output

**Input** ([09b](09b_model_call.json)) equals the payload rebuilt from the stored rows, both by the dump and by a fresh `GroundedContext.build` for the memo task's principal ([09a](09a_grounded_context_rebuilt.json), [09d](09d_memo_input_output_check.json)).
- Prompt rule 10 and the merged sentence "Dated cash and burn give runway as of their date, never current runway" are present.
- C1/S3 `$23.1M raised` carry `as_of: not stated`, `narrator: Pitch Deck Hunt`, `dates_not_as_of: ["2015"]`.
- C2/C3 and S1/S2 (`500M messages`, `140 000+ bots`) carry **no narrator** and `source_context: Traction by Apr-16`.
- P1/P2 are profile stage and sector, labelled "(profile)".
- `funding_facts`: cash and burn absent (no dated company cash or burn), `raise_supported` false.
- **Absent from the input:** "Series A deck with", "SlideShare deck has", the canary, 163,000,000, Bessemer, TechCrunch, Summit Partners, 2019, $18M, $140M, the founders' names, STALENESS / ATTRIBUTION ERROR / INVENTED IDENTITY, the fixture's owner name and description.

**Output.** Every stored section equals a replay of the pipeline's own steps on the model's reply (list normalisation, time guard with `time_wording_allowed`, then funding guard) ([09d](09d_memo_input_output_check.json)). The time guard removed nothing. The funding guard changed 2 sections ([09e](09e_guard_changes.txt)):

| Section | Model wrote | Stored |
|---|---|---|
| `what_would_change_the_picture` | "…would allow the $23.1M funding figure [C1] to be contextualised against actual business performance." | "…the $23.1M funding figure **(per Pitch Deck Hunt)** [C1] …" |
| `questions_for_management` | "Can the $23.1M in reported funding [C1] be confirmed with a cap table…" | "…reported funding **(per Pitch Deck Hunt)** [C1] …" |

The model named Pitch Deck Hunt itself in the executive summary, financial analysis, risk assessment, information readiness ("Funding raised figure (narrated by Pitch Deck Hunt, unverified): $23.1M [C1, S3]"), open concerns and the upside scenario.

**Not exercised live.** The model wrote no runway or cash premise, no mixed self-reported group containing S3, and no malformed funding label. So the merged runway/cash rewrite, the mixed-group split, the label rewrite and the possessive "Today's" handling did not act in this run. Their behaviour stays evidenced by the regressions and probes in `funding-fidelity-7c71995/`, not by this memo.

## Section checks ([09f](09f_section_scan.txt), then rendered in Chrome [15](15_browser_walks.json))

| Check | Result |
|---|---|
| Pitch Deck Hunt attached to its funding figure | **PASS.** 44 sentences stating $23.1M across stored sections, memo API (Lite, paid, staff), owner Lite memo, staff full memo, Markdown and overview: 0 without Pitch Deck Hunt. Chrome: owner 3/3, staff memo 8/8, Markdown 8/8, overview 1/1 (Lite, paid) and 2/2 (staff) |
| Mixed citations without a dollar amount | **Not exercised for funding** (no group mixes S3 with self-reported refs; base scenario cites [S1, S2] only). **New, opposite direction (FF-405):** `zelda_advantage` attributes the traction claims [C2, C3] to Pitch Deck Hunt |
| Unsupported current funding ("to date", "so far", "in total", cumulative) | **PASS.** None on funding |
| Unsupported active raise / proceeds | **PASS.** Only "Use of proceeds: Not found" gaps and the conditional question "Is a new funding round currently being planned or raised, and if so, …" |
| Unsupported cash / runway premise | **PASS.** Runway appears only as a gap ("Runway: Not found … Insufficient data (no dated cash balance or burn rate) to derive a runway figure"), the question "What is the current monthly burn rate and cash balance, and how much runway does the company have?", and "Runway: not calculated". No remaining/available runway or cash premise on any surface |
| Natural labels and openings | **PASS.** "Funding raised figure (narrated by Pitch Deck Hunt, unverified): $23.1M [C1, S3]", "Funding raised: Pitch Deck Hunt lists $23.1M raised [C1, S3]". No sentence opens with "Today" / "Today's"; no lower-case or truncated opening from a guard edit |
| Lists | **PASS.** HTML lists render (owner Lite 2 and 4 items; staff 2, 4, 10, 5); Markdown 21 `- ` items; `•` lines in information readiness and financial analysis render as lines, as in memo 95; no list repr anywhere |
| Citations | **PASS.** Unchanged by the two guard edits (stored = replay) |
| Counts | **PASS.** 3 / 0 / 3 and "(of 3)" on every Truth Delta page, IC memo, Markdown and overview ("none of the 3 claims could be verified or contradicted") |
| Profile dates vs slide context | **PASS** on dates: the stage is cited [P1] / [P1, P2] and never placed beside a slide date (0 sentences with Series A and 2015/2016/Apr). Wording note FF-407 |
| Privacy | **PASS.** Canary only on the owner's and staff's profile page; owner panel only for the owner; search/RAG only owner and staff; anonymous refused everywhere; no canary or fixture amount in model input or any memo surface |

## Grades against the key (run's reading; owner grading pending)

| ID | Observation | Grade |
|---|---|---|
| M1 $23.1M | INSUFFICIENT (`no_data`); Pitch Deck Hunt on every surface; undated; never current; 2015 not used as its date | INSUFFICIENT, no STALENESS ERROR. Attribution PASS |
| M2–M4 | Not extracted; no platform user count in the memo | No ATTRIBUTION ERROR |
| M5 | Bots INSUFFICIENT (140,000; the S-7 parse no longer truncates it), dated by "Traction by Apr-16" | INSUFFICIENT, dated |
| M6 / I1 | Slide 12 "/month" not extracted; the conflict is not flagged (the memo asks whether the figures are cumulative or active) | I1 missed (RA-109) |
| M7 / M8 | Not extracted | Allowed |
| E1–E3 | Entity Integrity 37: `sec_filer` `not_found`, the rest `not_applicable`; no invented identity | PASS |
| §E B-2 | `prior_amount_raised` 163M vs deck 23.1M: `not_comparable` / `profile_currency_unknown`, owner only | As the currency erratum (RA-105) |
| Q1–Q7 | Search/RAG 200 for the owner; near-uniform relevance; `no_relevant_evidence` false; `/ask/` is marketplace query extraction for all seven ([10](10_retrieval_ask_q1_q7.json)) | As before (RA-114) |

## Authorization matrix ([11](11_authorization_matrix.json); Chrome [15](15_browser_walks.json))

Identical, surface by surface (status, canary, owner panel), to the memo-95 run:

| Surface | Owner | Lite | Paid | Staff | Anon |
|---|---|---|---|---|---|
| Overview `/matchmaking/memo/profile/50/` | 403 (by design) | 200 Lite | 200 Lite | 200 Full | 302 |
| IC memo / Markdown | 200 Lite / 302 | 404 / 404 | 404 / 404 | 200 Full / 200 | 302 / 302 |
| Truth Delta page | 200 + owner panel | 200 | 200 | 200 | 302 |
| Memo API | 200 | 200 `lite_sections` | 200 `lite_sections` | 200 full | 403 |
| Search / RAG | 200 | 403 | 403 | 200 | 403 |
| Profile (canary) | 200, canary | 200, no canary | 200, no canary | 200, canary | 302 |

HTTP logout for each principal: 302 to `/home/`, then the owner profile redirects to login. Chrome: every signed-in walk ended with the nav Sign Out, confirmed by a protected URL redirecting to login.

## Ledger

| ID | Layer | Principal | Observation | Key ref | Grade | Bucket | Sev | Blocking |
|---|---|---|---|---|---|---|---|---|
| FF-401 | 9 | all memo readers | Pitch Deck Hunt on every $23.1M sentence (44/44 captured, Chrome counts above). The model supplied it in 6 sections, the guard in 2 | M1 | PASS | — | — | No |
| FF-402 | 9 | all | FF-303 did not recur: no runway or cash premise on reported funding. Runway appears only as a gap, a question and "not calculated". The guard's runway rewrite was **not exercised** live | M1 | PASS (not exercised) | PHASE1-GROUNDING | — | No |
| FF-403 | 9 | full-memo readers | FF-305 did not recur: the base scenario cites [S1, S2] only and does not mention capital. No self-reported group contains S3. The mixed-group split was **not exercised** live | M1 | PASS (not exercised) | — | — | No |
| FF-404 | 9 | all | FF-302 did not recur: the model wrote a natural label itself ("Funding raised figure (narrated by Pitch Deck Hunt, unverified): $23.1M [C1, S3]"). The label rewrite was **not exercised** live | M1 | PASS (not exercised) | — | — | No |
| FF-405 | 9 | staff (full memo, Markdown); `zelda_advantage` is not a Lite section | `zelda_advantage`: "The verification pass distinguished between the company's own deck statements [S1, S2] and the same figures as reported by the third-party aggregator Pitch Deck Hunt [C1, C2, C3], correctly flagging that Pitch Deck Hunt is the narrator of the funding and traction claims…". C2/C3 (500M messages, 140,000+ bots) have **no narrator** in the input (slide 10, ownership `implied`); only C1/S3 are Pitch Deck Hunt's. A mixed citation group without a dollar amount that **moves the company's own traction to the third party**, the opposite direction to FF-305. The guard only handles refs that have a narrator, so it does not act. The sentence also credits the system for a distinction it got wrong (RA-108) | M1, M5 | Misattribution (new) | INTEL-QUALITY | P2 (provisional; for owner) | No |
| FF-406 | 9 | staff | `upside_scenario`: "140,000+ bots and 500M messages, contextualised **as of April 2016**". The input gives `as_of: not stated` with slide context "Traction by Apr-16"; "as of" reads as a stated as-of date. Conditional sentence; same shape as PF-205 | M5 | Borderline; for owner | INTEL-QUALITY | P3 | No |
| FF-407 | 9 | all | Executive summary: "ManyChat is a software company, **listed as** Series A stage [P1, P2]". Cited to the profile, never beside a slide date; the prose does not say "profile" (memo 95 said "profile-listed"). The "(current profile, undated)" label was not exercised | §E | PASS (dates); wording note | PRODUCT-UI | P3 | No |
| FF-408 | 9 | all | No active-raise or proceeds premise; the "if so" question keeps a legitimate conditional | M1 | PASS | — | — | No |
| FF-409 | 5, 9 | all | Counts 3/0/3 and "(of 3)", lists rendered, citations kept through both guard edits, no raw list repr | — | PASS | — | — | No |
| FF-410 | 10 | all | Privacy and tier boundaries hold (matrix identical to memo 95's, plus Chrome); B-2 owner-only; no canary or fixture value in model input or any memo surface | — | PASS | — | — | No |
| FF-411 | 9 | staff | Markdown export is served as `text/markdown` with no charset (unchanged since memo 95). Chrome's UTF-8 decode is clean; a client defaulting to Latin-1 shows `â¢` for `•` (seen in the HTTP probe's capture) | — | Observation | PRODUCT-UI | P3 | No |
| FF-412 | 5–9 | — | Unchanged open items: PF-206 / FF-311 (Section Coverage 31.2% owner Lite vs 100.0% full), RA-109/I1 (slide 12 "/month" not extracted), RA-103 (claim from the audit-framing slide 2, ownership `named`), RA-108 (Zelda-advantage self-credit, now with FF-405), RA-114 (`/ask/`), RA-105 (B-2 `not_comparable` with a blank currency) | — | As before, **not graded fixed** | — | — | No |

No defect was repaired during the run.

## Summary

On a live run of merged main (`9b6d215`, containing 7c71995):
- Every sentence stating the $23.1M names Pitch Deck Hunt on every surface and tier.
- No current-total, active-raise, cash or runway premise appears; runway is only a gap or a question.
- Labels and openings are natural; lists, citations, counts, privacy and tier boundaries hold; the authorization matrix is unchanged.

Three memo-95 findings (FF-302, FF-303, FF-305) did not recur, but **because the model did not write those shapes**, not because the guard corrected them. The guard only added two attributions. One new attribution defect appeared in the opposite direction (FF-405: the company's traction attributed to Pitch Deck Hunt), plus two P3 wording notes (FF-406, FF-407).

**RA-106 and Zelda hardening stay pending until this run is independently graded.**

## Artifacts

- [00](00_setup.json): setup, gates, isolation, ID sequences, Redis before/after, preservation.
- [01](01_extraction.json)–[09](09_memo.json): pipeline rows.
- Memo input and output: [09a](09a_grounded_context_rebuilt.json) rebuilt input, [09b](09b_model_call.json) model call, [09c](09c_all_model_calls.json) all calls, [09d](09d_memo_input_output_check.json) input/output check, [09e](09e_guard_changes.txt) guard changes, [09f](09f_section_scan.txt) section scan.
- HTTP probe: [10](10_retrieval_ask_q1_q7.json)–[13](13_rendered_reports_text.json); [11b](11b_reconciliation_by_principal.json) B-2 per principal.
- Chrome: [15](15_browser_walks.json) and [browser/](browser/).
- Probes: [16](16_probes.json).
- [process/](process/): server and worker logs. [scripts/](scripts/): the run's scripts. [snapshots/](snapshots/): read-only before/after snapshots and Redis key counts.
