# ManyChat — Pass A ledger at `5120190` (after PR #289): post-merge live validation for RA-109

The deck is the frozen ManyChat audit deck, run once through the merged code with the RA-109 runbook, inputs, questions and budget: one memo plus Q1–Q7, **8 model calls**. Part 1 records what ran. Part 2 is my provisional reading, kept apart:
- **Observations** are what a surface showed.
- **Provisional findings** are defects I propose, with severity left to the grader.
- **Replay results** are read-only reruns of the merged guards over fixed sentences.
- **Browser checks** were completed by manual sign-in.

RA-108, RA-109, RA-114, Q-2–Q-4 and overall hardening stay open.

| Item | Value |
|---|---|
| Execution SHA | `5120190ce47708e99cff5b417baf2c565059cf7f` (merge of PR #289). Non-docs changes since `c6c3d1b`: `zelda_api/basis_fidelity.py`, `zelda_api/tests_output_fidelity.py` and the two memo-103 fixture files; 0 migrations. No application, prompt, guard, fixture or test change during the run |
| Tests | 259 + 77 + 67 = **403 OK** at free RAM 2.19–2.27 GB; `check` and `makemigrations --check --dry-run` exit 0; `preflight --local` ok |
| Rows | Document **3146**; 12 chunks; insights 5205–5208; claims **2393–2396**; Entity Integrity **45**; Truth Delta **98**; memo **104** |
| Isolation | SQLite backup copy of the dev DB (`zelda_api.0044` applied, sequences advanced, both in the copy only); Memurai db 8 (broker) and db 9 (results and cache); six paid keys blank; `pending=0`. The original DB and the memo-94–103 copies are byte-identical before and after |

## Part 1: Execution record

### Run record

1. **Preflight**, serial and under the memory watchdog (1500 MB):
   - the 403 tests, `check` and migrations;
   - the original and historical copies are refused by the wrapper ([00](00_setup.json) `gate_refusal_before_migrate`).
2. **Before-snapshots:** the original and memos 94–102 equal the memo-103 run's committed after-snapshots (`4ee3639`). Memos 97–103 match their committed `09_memo.json` field by field.
3. **Browser gate.**
   - Two failed attempts on device `203c1a8f`: a Chrome error page, with no request reaching the probe server.
   - The third, on device `b60b1997` (Chrome on this computer), passed. The browser tool read the fresh nonce `c601933be9b8543a` from the probe page; the probe server logged GET `/index.html` 200 at 16:14:45, and the run server logged `GET /accounts/login/?gate=c601933be9b8543a` 200 at 16:14:59.
   - This was before any model call ([15](15_browser_walks.json), [browser/loopback_gate/](browser/loopback_gate/)).
4. **Upload at 16:15:51 local** → memo 104, generated in 51.3 s. Then the HTTP probe ran the 90-row matrix and Q1–Q7, once each.
5. **Browser checks** for anonymous and owner (completed below).
6. **Low-memory interruption and restart.**
   - The first Lite attempt was the owner by autofill. After it, Claude Code's reaper stopped the server, worker and watchdog at 0.97 GB free.
   - A read-only check showed nothing had changed ([process/intact_check_after_shutdown.txt](process/intact_check_after_shutdown.txt)).
   - I restarted only once free RAM held at **1.2 GB or more** (1.86–1.96 GB): watchdog first, then the server only, at 5120190 with every gate passing again. The worker stayed stopped.
   - The gate was re-run with a fresh nonce: browser `b60b1997` loaded `/home/?gate=0a56b792ed1b2c1a`, and the restarted server logged that request at 19:15:23.
7. **Lite, paid and staff checks**, with manual sign-in. The staff check needed a test-account setup repair first (below).
8. **After-snapshots, then stop.** Snapshots are byte-identical to the before set. Source-DB and deck hashes are unchanged. The server was stopped by PID; the worker was already stopped.

### Call ledger (every attempted model call; [09c](09c_all_model_calls.json))

| # | Process | Started (UTC) | Kind | Response | Stop | Tokens in/out |
|---|---|---|---|---|---|---|
| 1 | worker 20188 | 23:15:57 | memo | `msg_011CgMuwRh2dFNCNMdNSAs2z` | end_turn | 3,771 / 2,304 |
| 2–8 | server 20368 | 23:19:01–23:19:14 | `/ask/` query extraction (Q1–Q7) | `msg_011CgMvB2x…` to `msg_011CgMvBxF…` | end_turn | 347–349 / 8 |

- **No failures and no retries.**
- **Ledger file** `model_calls.jsonl`: SHA-256 `f8f21dcf…a16299`, checked again after the restart. It was still 8 lines at the end.
- **No calls after the run:** no model call was made by the browser checks, the restart, the MFA repair or the replays.

### Raw output and stored memo

- [09b](09b_model_call.json) holds the raw reply, and [09](09_memo.json) holds the stored memo 104.
- [09d](09d_memo_input_output_check.json) confirms:
  - the sent payload equals memo 103's once document ids are masked;
  - every `absent_from_model_input` entry is true;
  - `basis_facts_equal_with_reversed_items` is False (OF-815, carried).
- **Guard edits:** the merged guards changed exactly one section, `questions_for_management`, with `attribution:Pitch Deck Hunt` ([09e](09e_guard_changes.txt)). The time guard removed nothing, and the basis guard did not fire.
- **Markdown export** ([14](14_ic_memo_export.md)): 11,374 bytes, UTF-8, 0 replacement characters.

### Source map (the sent payload; [17](17_grading_excerpts.json))

| Ref | Statement | Page | Context in payload |
|---|---|---|---|
| C1 / S4 | $23.1M raised | 2 | narrator Pitch Deck Hunt; as of "not stated" |
| C2 / S3 | 500M messages/month | 12 | none |
| C3 / S2 | 500M messages | 10 | 'Traction by Apr-16' |
| C4 / S1 | 140 000+ bots | 10 | 'Traction by Apr-16' |

Consistency note (refs C3, C2): "Page 10 states 500M messages without an explicit interval; page 12 states 500M messages/month."

### Surfaces and boundaries

- **Automated HTTP probe:**
  - all 90 matrix rows are identical to memo 103's ([11](11_authorization_matrix.json));
  - reconciliation is shown to the owner only;
  - canaries are absent everywhere;
  - Q1–Q7 all return the marketplace fallback (RA-114).
- **Browser checks:** these are a separate record; see Part 2, section D.

### Deviations

- **D-1, browser gate.** Two failed attempts on `203c1a8f` are preserved (`gate_attempt1.txt`, `gate_attempt2.txt`). Only `b60b1997` was used after that.
- **D-2, two sign-ins landed on the wrong account.** Chrome's saved logins caused both:
  - the first owner handoff signed in as `founder2`;
  - the first Lite handoff signed in as `m512mc_owner`.

  Each was identified from the nav text, `last_login` and the newest session, signed out, and not counted. The Lite fixture was diagnosed read-only ([process/diag_lite_stdout.txt](process/diag_lite_stdout.txt)): active, usable password, one shared fixture password, no lockout. No hash or password was printed.
- **D-3, low-memory shutdown.** Covered in step 6 above. The 0.9 GB working floor and the 1500 MB watchdog limit were never lowered. Twice, work was held while free RAM was below 0.9 GB: before the MFA reset (0.85 GB) and after the staff check (0.80 GB, so the server was stopped first).
- **D-4, staff test-account setup repair.**
  - **Why:** the HTTP probe had enrolled `m512mc_staff` in MFA with a random secret, held only in a scratchpad file that was not read, so the machine owner could not complete MFA.
  - **What was run:** on the owner's instruction, the app's supported command `reset_staff_mfa`, for `m512mc_staff` only, on the copy. It ran under the run wrapper's gates, plus a script assertion that the connection was the copy.
  - **What changed:** that one enrollment was deleted. The other two staff enrollments were unchanged ([snapshots/staff_mfa_state_*.txt](snapshots/)), and the MFA requirement was not changed.
  - **Re-enrollment:** the owner enrolled again through the normal setup page, which shows a text setup key, not a QR code, using the password and a fresh code. No setup key, code or recovery code was read, captured or recorded.
  - This is a test-account repair, not a product check.
- **D-5, Redis db 6.** It dropped from 86 to 77 keys during the run. These are the memo-103 run's TTL cache keys expiring; this run never addressed db 6.

## Part 2: Provisional assessment (pending independent review)

### A. Provisional findings (severity for the grader)

**F-1, funding-guard word split.** Provisional P2, because it is rendered to staff.

| | Text |
|---|---|
| Raw reply (`questions_for_management` item 5) | "What is the composition of the $23.1M reportedly raised [S4] — how many rounds, at what valuations, and from which investors?" |
| Stored and rendered | "What is the composition of the $23.1M **reported (per Pitch Deck Hunt)ly** raised [S4] — …" |

- **Read-only reproducer:** [assessment/repro_reportedly.json](assessment/repro_reportedly.json), produced by `scripts/repro_reportedly.py.txt` under `run_ro.py`, with `query_only=ON` on the copy.
- **Part A, the tail regex alone.** `_FIGURE_TAIL` (`zelda_api/funding_fidelity.py:100`) is `(?:\s+(?:in\s+)?(?:funding|raised|figure|total|listed|reported))*`, with no word boundary after the alternatives. After "$23.1M" it matches " reported" and stops before "ly raised".
  - Controls: "$23.1M reported raised" → " reported raised"; "$23.1M raised" → " raised"; "$23.1M reportedness" → " reported".
- **Part B, the merged guards.** Run in order (time, funding, basis) with document 3146's context, the output equals the stored line (`output_equals_stored: true`) with `funding_changes ['attribution:Pitch Deck Hunt']`. It is idempotent.
- **Cause:** `_attribute` inserts ` (per <narrator>)` at the tail's end (`:423`).
- **Status:** a code reading confirmed by the reproducer. PR #289 did not change this rule, and no code was changed.
- **Seen in the browser:** the staff IC memo renders it (`browser/staff_ic_memo_questions_reportedly.jpg`). The owner's Lite memo has no questions section, so it doesn't show there.

**F-2, possible heading spread (OF-1003 class).** For the grader.

The full sentence, in `business_model_analysis`, is stored identical to the raw reply:

> "The only indicators of commercial activity are the company's self-reported traction figures — 140,000+ bots [S1] and 500M messages or 500M messages/month (see consistency note below) [S2, S3] — contextualised under a slide heading 'Traction by Apr-16', but these figures are undated as counts and have not been independently verified [C2, C3, C4]."

- **Cited source text and page boundaries** ([assessment/heading_concern.json](assessment/heading_concern.json), [17](17_grading_excerpts.json)):
  - **S1** "140 000+ bots" and **S2** "500M messages" are on page 10 (chunk 9), with `source_context` 'Traction by Apr-16'. Page 10 as chunked: "Total Bots Created / Jul-15 … Apr-16 / … / Traction by Apr-16 / 140 000+ bots / 500M messages".
  - **S3** "500M messages/month" is on page 12 (chunk 11), with **no context**. Page 12: "ManyChat / 140 000+ bots / 500M / messages/month / Launching on Facebook / Messenger this month".
  - Page 11 (chunk 10) lies between them: "Just got approved on / Facebook Messenger."
- **Guard replay:** unchanged (`changed: false`, `basis_changes: []`, idempotent).
- **Reading:** the heading is page-10 context, but the sentence attaches it to all three figures, including S3. It does so in the same sentence that calls them "undated as counts", so it doesn't assert a date for S3. Whether placing a page-10 heading over a page-12 figure, without a date, is an OF-1003 recurrence is a question for the grader.

### B. Replay results (read-only; [assessment/assess_replay.json](assessment/assess_replay.json))

All ten cases were replayed through the merged guards with document 3146's context:

| Case | Result |
|---|---|
| memo 103 `base_scenario` (OF-1102) | corrected by `basis_source_context` |
| memo 103 `upside_scenario` (OF-1103) | corrected by `basis_consequence_context` |
| memo 104 `business_model_analysis` sentence (F-2) | unchanged |
| memo 104 `questions_for_management` item 5 (raw) | becomes the F-1 split (funding guard) |
| memo 104 `base_scenario` sentence 1 | unchanged (no date in it) |
| Five controls: denial in the consequence, unrelated consequence, unknown trailing clause, date stated as the hypothesis, qualifier and attribution with no heading | all unchanged |

Every case is idempotent. All 17 memo-104 sections replay identically, including in reversed item order.

### C. Acceptance table (provisional)

| Check | Reading | Evidence |
|---|---|---|
| Verification qualifiers kept | **Pass.** "self-reported", "could not be independently verified" and "neither … independently confirmed" on every surface | 09, 13, 15 |
| Funding attribution | **Pass in substance, broken in form.** Pitch Deck Hunt is named on every surface, but F-1 corrupts one sentence | 09e, repro |
| Historical dates | **Pass.** No figure is given a present-day date. "Traction by Apr-16" appears only as a heading or context | 09, 17 |
| No page-10 date moved to page 12 | **Pass, with F-2 open.** No date reaches S3 in either scenario. In F-2, the heading spans S3 without a date | heading_concern |
| OF-1102 / OF-1103 recurrence | **Did not recur** in base or upside. The replay corrects memo 103's sentences | assess_replay |
| Denials, unrelated consequences, unknown trailing clauses | **Pass.** The controls are unchanged | assess_replay |
| OF-1004 (citation identity) | **Pass.** All 35 brackets resolve to standard form. The one group mixing C3 and S3 is the question asking whether 500M is a total or a monthly rate, which names both figures on purpose | assess_brackets |
| Earlier regressions (matrix, canaries, reconciliation, UTF-8) | **Pass.** 90 rows identical; no canary; reconciliation owner-only; Markdown clean | 11, 14 |
| RA-114 (`/ask/`) | **Open.** All seven questions get the marketplace fallback | 10 |
| RA-108 (verification-process wording) | **Open.** "The verification process identified …" (`zelda_advantage`) | 09 |

**P3 wording, for the grader:**
- "materially different metrics";
- "reliability of the company's own traction reporting";
- "undated total on page 10" (Q-2);
- "see consistency note below";
- "bot/messaging automation space" (Q-4);
- present-tense "large installed base" in the base scenario (whether historical figures read as current, Q-3 class).

### D. Browser checks (manual sign-in; [15](15_browser_walks.json), [browser/](browser/))

| Principal | Result | What was checked |
|---|---|---|
| Anonymous | **Pass** (16:22) | `/home/` loads signed out; the IC memo, verification, company overview and owner profile URLs each redirect to login |
| Owner `m512mc_owner` | **Pass** (16:35) | IC memo is "Zelda Lite Memo" (5,420 chars); F-2 sentence shown verbatim; no scenarios or questions; no canary |
| Lite `m512mc_lite` | **Pass** (19:20) | Overview keeps the funding attribution and qualifier; investment analysis locked; Truth Delta 403 after sign-out |
| Paid `m512mc_paid` | **Pass** (19:26) | Verification page matches the probe at 54,461 bytes; "Measurement basis to clarify" block shown; signed out via `/` (FF-413) |
| Staff `m512mc_staff` | **Pass** (20:35, after MFA) | Full verification; Truth Delta API (4 claims); IC memo base and upside without a date and with F-1 rendered; full company overview |

- **None not run.**
- **Failed attempts preserved:** the founder2 and owner mis-sign-ins (D-2).
- **Observation only:** "Series B" is in the Lite overview's HTML but not in its visible text.

## Summary

- **Not proposed for acceptance.** F-1 is a rendered word split. F-2 is open for the grader.
- **What held:**
  - OF-1102 and OF-1103 did not recur live;
  - the merged rules correct memo 103's graded sentences in replay;
  - all regression checks and all five browser checks passed.
- **Still open:** RA-108, RA-109, RA-114, Q-2–Q-4 and overall hardening.
- **Not done:** no merge or deployment.

## Artifacts

| Folder | What it holds |
|---|---|
| top level | 00–17 run outputs |
| `browser/` | screenshots, `server_log_browser_walks.txt`, `loopback_gate/` (all gate attempts) |
| `assessment/` | replay, brackets, reproducer, heading concern |
| `process/` | logs, walk notes, intact check, RAM samples, Lite diagnosis, MFA reset output |
| `snapshots/` | before/after DB snapshots, hashes, Redis, MFA state |
| `scripts/` | every script used, as `.txt` |
