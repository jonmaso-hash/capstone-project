# RA-114 revision 2: operating runbook (prepared, not run)

**This is how revision 2 would be executed. It is not a run, and it changes no criterion.**
- **Criteria:** revision 2 (`output-ra114-ranking-panel-9ee8d3d/NEXT_LIVE_VALIDATION_REV2_RA114.md`), revision 1 (`output-ra114-ask-document-e4d17d7/NEXT_LIVE_VALIDATION_REV_RA114.md`) and the base procedure (`1aab9e3`, tag `ra114/base-live-procedure-1aab9e3`; see `BASE_PROCEDURE.md`) govern. None of those files is edited.
- **Running it requires** independent review of this package, then the owner's explicit go-ahead for 8 model calls, the worker and the manual sign-ins.
- **Outcome:** a passing run is *proposed* to the grader as RA-114 live evidence. It closes nothing by itself. RA-108, RA-109, RA-114, Q-2–Q-4 and overall acceptance stay open until independently reviewed.

## What this runbook changes in *how* (not *what*)

| Inherited | Here | Why |
|---|---|---|
| Fixture passwords and staff TOTP read from scratchpad files by `setup_fixtures.py`, `upload.py` and `probe.py` (`f73bef5`); staff MFA set up by script | **No credential or TOTP file is read, written or created.** Fixtures get unusable passwords. The owner sets each one in their own terminal (`rev2_run.py <cfg> setpassword <user>`, `getpass`). Every sign-in is **by hand in Chrome**, and staff MFA is completed by hand through the real setup and verify pages | Standing rule. Staff MFA stays enforced, with nothing emulated or bypassed |
| An HTTP probe with its own sessions (`requests`) | **The probe runs in the signed-in browser tab** (`/__rev2/probe/`, same origin) and sends requests as whoever is signed in. The run server records them | No session cookie leaves the browser. Identity is checked twice: the server's session and the nav text |
| "New, unused Memurai dbs (not 6–9)" | **A separate, temporary Memurai instance** on 127.0.0.1:6391: run-local config, 2 dbs, no persistence, 64 MB cap. The installed instance on 6379 is not used or touched | All 16 dbs of the installed instance hold keys (`99c92ea`). Measured ≈75 MB |
| No retries, enforced by the operator | **No retries, enforced in code.** The gate refuses any call on a client with `max_retries != 0`. The wrapper sets `ANTHROPIC_WEB_REQUEST_MAX_RETRIES=0` and `ANTHROPIC_BACKGROUND_MAX_RETRIES=0` | `ANTHROPIC_BACKGROUND_MAX_RETRIES` defaults to **2** (`config/settings.py:521`). The memo call could retry silently before |
| The ledger records successful calls after the fact | **Every attempt is a ledger line written before the call.** The gate decides it from the phase the ordered checkpoints set | A refused or failed attempt is visible. A 9th attempt is refused, not made |
| — | One more fixture, an **unrelated investor**, for revision 1's authorization probe | Revision 1 names it; `setup_fixtures.py` didn't create it |

## Environment

- **Code:** a clean, detached worktree at `40f6789889dfeaf6b67558f3e1f9981d0a05b30a` (= `origin/main` at preparation). `rev2_run.py` refuses to start if any application file differs from it (`docs/` and `*.pyc` excluded).
  - If main has moved, the post-merge byte check is repeated first (base precondition 2).
- **Database:** a fresh sqlite backup copy of `C:\Users\jonathan\Desktop\KCV\db.sqlite3`, made with the source opened read-only (`rev2_prep.py before`). It is then migrated: the source lacks `zelda_api.0044`.
  - **Refused:** the source DB and all 11 earlier runs' copies (memos 94–104), plus the dry-run copies.
  - **Hashed:** the source, those copies and the deck, before and after.
  - At preparation the source hash was `5a0b8c1c…7e9a2`, and the copy hash at creation was `15bec0d2…`, equal to memo 104's copy at creation.
- **Broker, results and cache:** the temporary instance, `redis://127.0.0.1:6391/0` (broker) and `/1` (results and cache). `rev2_run.py` checks the instance's `config_file` before starting.
- **Keys:** the six paid keys are blank in `os.environ`. The Anthropic key comes from `.env` (live only).
- **Memory:** the watchdog (`rev2_memwatch.ps1`, run as a plain loop) stops the server and worker when free RAM falls below **0.9 GB** or the run's processes exceed **1500 MB**.
  - Start only with **≥ 1.2 GB** free.
  - **Measured offline:** dry run 2 *was stopped by this watchdog* (free 0.79 GB, with headless Chrome plus the panel popup); dry run 3 bottomed at 1.16 GB.
  - Close other applications first. Chrome is the largest consumer.
- **Model:** `claude-sonnet-4-6` (code literal) for the memo and for query extraction.
- **Browser:** Chrome `b60b1997` (the established browser). Before any call:
  - the base browser gate (fresh nonce);
  - **popups allowed for 127.0.0.1:8000**, because the panel check opens the real panel in a popup.

## Accounts (run-scoped, created on the copy only)

| Role | Username | Created as | Used for |
|---|---|---|---|
| Owner | `r2mc_owner` | founder with the ManyChat profile (private canary `CANARY-MANYCHAT-4417`) | upload, matrix, Q1–Q7 in both forms, control, panel |
| Lite | `r2mc_lite` | non-premium investor | matrix, authorization probe (403) |
| Paid | `r2mc_paid` | premium investor, active `INVESTOR_PREMIUM` | matrix, authorization probe (403) |
| Unrelated investor | `r2mc_investor` | non-premium investor, other sector | authorization probe (403) |
| Staff | `r2mc_staff` | `is_staff`, **no MFA yet** | matrix |

**Passwords:**
- Every account starts with an unusable password.
- The owner runs `python -B rev2_run.py <cfg> setpassword <username>` in **their own terminal** for each account, and only for the run's own accounts. Nothing is passed on the command line or stored.

**Staff:**
- The staff account must enroll MFA through the real setup page before the staff check. That creates a `StaffMFA` row **in the run copy only**.
- **Owner decision:** whether that enrollment is acceptable under base precondition 7 ("the run makes no MFA change"). If it is not, the staff check is not run and is recorded as not run.
- No staff account in the source DB has usable enrolled MFA except two earlier fixtures, whose secrets were scripted.
- Secrets, QR content and recovery codes are never read, recorded or screenshotted. The recorder never records `/accounts/` sign-in or MFA pages.

## Order of operations

**Before any sign-in**, everything independent of sign-in. **0 model calls.**
1. Owner go-ahead recorded. Free RAM ≥ 1.2 GB.
2. Create the worktree at `40f6789`.
3. Create a new `<LIVE_RUN_DIR>`, and copy the tooling and the two memo-104 reference files into it.
4. Fill `live_config.json` from `tooling/live_config.template.json.txt`.
5. Start the temporary Memurai: `memurai.exe <LIVE_RUN_DIR>\memurai\rev2_memurai.conf`. Check `dbsize` is 0 on both dbs.
6. Run `rev2_prep.py <cfg> before`, then `rev2_run.py <cfg> migrate`, then `rev2_run.py <cfg> check` (`CHECK OK`).
7. Base precondition 3, serially:
   - the four fidelity modules (452);
   - `check`;
   - `makemigrations --check --dry-run`.
8. Run `rev2_run.py <cfg> script rev2_fixtures.py`. Record `fixtures.json` (ids, unusable passwords, sequences bumped).
9. Start the watchdog loop. Start the server (`rev2_run.py <cfg> server`) and the worker (`rev2_run.py <cfg> worker`).
10. Pass the base browser gate in Chrome `b60b1997`.

**The owner then sets the passwords** (`setpassword`, own terminal).

**Signed-in steps**, on the probe page `http://127.0.0.1:8000/__rev2/probe/`. Each step unlocks only in its phase, and its identity is checked against both the server session and the nav text.

| # | Signed in as (by hand) | Probe step | Calls allowed in the step | Ledger checkpoints (lines expected) |
|---|---|---|---|---|
| 1 | owner | upload once (the deck is served only in phase `memo`, with the frozen hash), then poll status until `analyzed` with a memo | **1** (memo, worker) | `before_upload` (0), `after_memo` (1) |
| 2 | owner | matrix (16 GET + `/search/`, `/rag/` with Q1) | 0 | — |
| 3 | owner | Q1–Q7, **document form** `{"q", "document_id"}`, each with `/search/` and `/rag/` | **0** | `before_document_form` (1), `after_document_form` (1) |
| 4 | owner | **unrelated control** `{"q": "What is the weather in Paris?", "document_id"}` | 0 | — |
| 5 | owner | **panel check** in the real panel (popup): Library, "Ask about this document", context bar, Q1 submitted through the panel's own form, rendered passages read; "Ask the marketplace instead", bar gone, no second `/ask/` | **0** | `before_panel` (1), `after_panel` (1) |
| 6 | owner | Q1–Q7, **marketplace form** `{"q"}`, in order | **1 each**, the question verbatim | `after_marketplace_Q1` … `_Q7` (2 … 8) |
| — | — | **stop the worker**; owner signs out with the nav Logout button; signed-out check | 0 | — |
| 7 | Lite | matrix and authorization probe (Q1 document form and `/search/`: 403, 403) | 0 | — |
| 8 | Paid | matrix and authorization probe | 0 | — |
| 9 | unrelated investor | authorization probe | 0 | — |
| 10 | staff (MFA by hand) | matrix; refused unless the session carries the MFA stamp: *stop the staff check and ask the owner* | 0 | — |
| 11 | signed out | matrix | 0 | — |
| 12 | — | `end` | 0 | `end` (8) |

Then:
1. Stop the server.
2. Stop the temporary Memurai (`shutdown nosave`).
3. Run `rev2_prep.py <cfg> after`, and `rev2_assess.py <cfg>`.
4. Produce the base procedure's 00–17 dumps.
5. Commit the evidence additively on a new branch. Part 1 (execution) and Part 2 (provisional assessment) stay separate.

**Total: 8 model calls (1 memo + 7 query extraction). Ceiling 8. No retries.**

## Abort rules (enforced by the tooling; no step retries anything)

**Tooling:** use `tooling_after_review_26fb04b/` (review of `26fb04b`). It adds three rules to the ones below:
- **A failed or truncated call stops the run:** an exception, or any `stop_reason` other than `end_turn`, persists the abort.
- **Every checkpoint requires a completed result for every allowed call,** and `after_memo` is confirmed on the server, read-only: the document is `analyzed` with a memo.
- **Upload polling that ends without confirmed completion aborts the attempt.**

**The gate refuses**, writes a ledger line, aborts the run and raises:
- any call outside its phase's allowance (0 in setup, matrix, document form, controls, panel and after the last question);
- a call of the wrong kind;
- an extraction whose text is not that phase's question;
- a client with retries;
- any 9th attempt;
- any call after an abort.

**A checkpoint aborts** when:
- it is out of order;
- the ledger's line count differs from the expected one;
- a refused attempt is in the ledger.

A marketplace question that makes no call is recorded as a **deviation** and not retried.

**The probe aborts** on:
- a wrong account (server session or nav text);
- an upload not returning 201 with a document id, or a recorded id that differs;
- a second ingest;
- a pipeline `error`;
- a document form answering for another document;
- a panel that sends ≠ 1 `/ask/`.

**After an abort**, the server answers every application request with **503**, logout excepted. A new attempt is a new run with a new go-ahead and a new copy.

**A watchdog stop** (memory floor) ends the attempt. It is recorded, and a restart follows the base procedure's restart rule (ledger checkpoint after any restart). A step already started is not repeated.

## What the recorder writes, and never writes

**Written:**
- every request's method, path, principal, phase, step tag, status and `Location`;
- JSON request and response bodies under `/api/v1/zelda/`;
- the upload's name, size and SHA-256;
- for matrix-tagged requests, the marker, B2 and canary flags and the readable text.

**Never written:**
- headers, cookies, CSRF tokens;
- form posts outside `/api/v1/zelda/`;
- any `/accounts/` sign-in, MFA, password or recovery page body.

The probe token is a per-run nonce for `/__rev2/` endpoints. It is not a credential and is not committed.
