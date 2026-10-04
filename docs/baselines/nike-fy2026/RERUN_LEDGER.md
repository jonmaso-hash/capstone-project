# Nike FY2026 rerun — ledger (Phase 1 acceptance)

Graded against [RERUN_ADDENDUM.md](RERUN_ADDENDUM.md) (frozen at `e44fc44` before the first upload), [ANSWER_KEY.md](ANSWER_KEY.md) and every L-number in [BASELINE_LEDGER.md](BASELINE_LEDGER.md). The addendum is not edited; corrections are recorded as errata below.

<!-- RUN RECORD, LAYER RESULTS AND L-NUMBER GRADES ARE FILLED IN AS EACH PASS COMPLETES -->

## Errata

**E-2 (2026-10-04), the broker.** Recorded before the Pass A upload that this ledger grades.

*What happened:*
- The first Pass A attempt uploaded the deck as document 3118. Its pipeline task never ran.
- The local `.env` points `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` and `CACHE_URL` at a shared Upstash Redis instance, not the local `memurai.exe`. That instance held 213 waiting tasks left by focused local test runs (refresh-matches for investors 1–3, memo regeneration and re-verification for document 1, and others). Document 3118's task sat behind them.
- The worker drained part of that backlog before it was stopped. That included about 10 `generate_intelligence_memo(1)` tasks, each a real Claude call that overwrote local document 1's memo. None of them touched Nike rows.
- The baseline ran the same way; see `BASELINE_LEDGER.md` erratum E-2.

*Correction (a setup change, not a code change):*
- The run wrapper sets the broker and result backend to `redis://localhost:6379/0`, and the cache to `redis://localhost:6379/1`, in-process. `read_env()` uses `setdefault`, so these values win over `.env`.
- Before starting, each server and worker process prints the effective host of `settings.CELERY_BROKER_URL`, `settings.CELERY_RESULT_BACKEND`, the Celery app's `broker_url` and `result_backend`, and the cache `LOCATION`. It exits unless every one is `localhost`.
- Proved both ways before the run: all five printed `localhost` with exit 0; with the override suppressed, all five printed the Upstash host and the process refused to start (exit 1).
- Document 3118 is abandoned. Its status is set to `error`, with `source_entity` "NIKE, Inc. (abandoned, erratum E-2)", so it cannot collide with the fresh upload. Its stranded task stays in Upstash, unexecuted.
- The Upstash queue is **not** purged. No queued task is executed. Ownership of that instance is open (see Follow-ups).

*Effect on the addendum:* none of the §2–§4 expectations change. §1 "Setup" gains the broker requirement above.

## Follow-ups

- **Fail-closed test broker** (separate PR after this one): the test runner refuses any Celery broker that is not in-memory, as it already refuses network calls.
- **Upstash queue:** before any purge is proposed, capture a non-secret manifest of the queued task names, ids and arguments, and establish that no other environment or process references that instance.
