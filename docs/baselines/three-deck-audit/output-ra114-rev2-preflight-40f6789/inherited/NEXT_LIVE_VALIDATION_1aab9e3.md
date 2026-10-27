# Next live validation: ManyChat Pass A at `b278364` (prepared, not run)

**Status: this is a procedure, not a run.** Nothing in this file has been executed. Running it requires an explicit owner go-ahead, because it makes model calls and starts the worker. Neither is authorised by the post-merge verification it is filed with.

## Purpose and scope

The run checks RA-109's live output acceptance on the merged code (PR #290, F-1 and F-2) with the frozen ManyChat audit deck. It reuses the inputs, questions and budget of the memo-104 run at `5120190`, as recorded in `f73bef5` (`docs/baselines/manychat/output-fidelity-5120190/pass-a/`).

- **Decided by this run (provisionally, for the grader):** whether F-1 and F-2 hold live, and whether the earlier regressions stay fixed.
- **Re-observed only:**
  - RA-108, RA-114 and Q-2–Q-4: `b278364` contains no change for them (see the post-merge README), so the run is expected to record them as open. They are not pass/fail criteria for this run.
  - Overall acceptance is not decided by this run.

## Call budget

| | |
|---|---|
| Ceiling | **8 model calls**: 1 memo, plus Q1–Q7 through `/ask/`, once each |
| Retries | **none.** A failed or truncated call is recorded and the run stops. A retry needs a new owner go-ahead and is counted |
| Ledger | `model_calls.jsonl` line count and SHA-256 recorded before the upload, after Q7, after any restart and at the end |
| Outside the budget | browser checks, replays, restarts and any repair make **0** calls. Any call in those steps fails the run |

A 9th attempted call fails the run immediately, and so does any call from another document or process.

## Preconditions (all before the first call; any failure stops the run with 0 calls)

1. **Owner go-ahead** for: 8 calls, starting the worker for this one document, and the browser sign-ins.
2. **Code:** the execution SHA equals `origin/main` (`b278364` unless main has moved; if it has, re-run the post-merge byte comparison first). The worktree is clean, and no application change is made during the run.
3. **Tests, run serially:** the four modules (452 OK), plus `check` and `makemigrations --check --dry-run` exiting 0.
4. **Isolation:**
   - a fresh SQLite copy of the dev DB; the run wrapper refuses the original and historical copies (`gate_refusal_before_migrate`);
   - new, unused Memurai dbs (not 6–9);
   - paid keys blank;
   - the original DB and memos 94–104 hashed before the run.
5. **Memory:**
   - memory watchdog at 1500 MB;
   - free RAM of 1.2 GB or more at start; the 0.9 GB floor is never lowered;
   - below 0.9 GB with services running: stop the server and worker first, then hold.
6. **Browser gate:** a fresh nonce is read from the probe page, and the run server logs the request, before any call, on Chrome `b60b1997`. Three failed gate attempts stop the run.
7. **Accounts:**
   - Use the existing `m512mc_*` fixture accounts, or new run-scoped fixtures, created by the run's setup script on the copy only.
   - After every sign-in, check the identity from the nav text before counting the check. Chrome autofill caused D-2 last time.
   - No password, TOTP secret, setup key, QR content or recovery code is read, captured or recorded.
   - The run makes no MFA change. If staff MFA is unusable, stop the staff check and ask the owner. Do not reset it.

## Steps

1. Take snapshots of the source DB, memos 94–104 and Redis key counts. Start the worker for this document only.
2. Upload the deck once (SHA-256 `be7a7171…f3ef1`). This generates one memo, call 1.
3. Run the HTTP probe once: the 90-row matrix and Q1–Q7 (calls 2–8). Then stop the worker.
4. Dump outputs 00–17 in the `f73bef5` layout, including the raw reply, the stored memo, `09e` guard changes and the Markdown export.
5. Run the browser checks for anonymous, owner, Lite, paid and staff, by manual sign-in. Sign each out with the nav Logout button.
6. Take after-snapshots. Stop the server by PID. Record the call ledger and its hash.
7. Commit the evidence additively on a new `docs/manychat-output-fidelity-b278364` branch. Part 1 (execution) and Part 2 (provisional assessment) stay separate.

## Pass / fail criteria

**Run integrity:** every item must hold, otherwise the run is invalid:
- at most 8 calls, no retry, ledger hashes consistent;
- one code state;
- the original DB, memos 94–104 and the deck byte-identical before and after;
- the worker stopped at the end, and no other document processed.

**F-1** (funding attribution, `zelda_api/funding_fidelity.py`):
- **Pass:**
  - no word is split by an inserted attribution: no `(per …)` is directly followed by a letter, and none sits inside a word;
  - every funding figure keeps its Pitch Deck Hunt attribution on every surface (stored memo, API, rendered pages, Markdown);
  - a second guard pass changes nothing.
- **Fail:** any split word, or a funding figure without attribution.

**F-2** (heading scope, `zelda_api/basis_fidelity.py`):
- **Pass:** no sentence places page 10's 'Traction by Apr-16' heading over S3/C2 (page 12's 500M messages/month). Every sentence that names the heading and cites S3 or C2 does one of two things:
  - keeps S3 separate with its own page ("separately … on page 12");
  - is one the guard keeps for review, in which case the grader judges it.
- **Fail:** the heading is attached to S3 without that separation, or a page-10 date reaches S3 (the OF-1102 class).
- **Not exercised:** the model writes no heading list over a cross-page pair. F-2's live pass then cannot be declared; the replay evidence at `b278364` stands, and the run says so.

**Regressions:** each must hold as in the memo-104 run:
- verification qualifiers present on every surface;
- historical dates only; no present-day date on a historical figure;
- OF-1102 and OF-1103 do not recur;
- OF-1004: every citation bracket resolves to a supplied ref;
- the 90-row matrix is identical to memo 104's;
- canaries are absent;
- reconciliation is shown to the owner only;
- the Markdown is UTF-8 with 0 replacement characters;
- all five browser checks pass;
- every guard change in `09e` is accounted for.

**Recorded for the grader, not pass/fail:**
- RA-108: the wording in `zelda_advantage`;
- RA-114: the `/ask/` answers to Q1–Q7, where the marketplace fallback is expected again;
- Q-2–Q-4: P3 wording.

**Outcome:** a run that passes integrity, F-1, F-2 (or records it as not exercised) and the regressions is proposed for independent grading as RA-109 live output evidence. It does not by itself close RA-109 or any other item.
