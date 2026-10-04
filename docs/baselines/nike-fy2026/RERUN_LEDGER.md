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

**E-3 (2026-10-04), the local database schema.** Recorded before the Pass A upload that this ledger grades.

*What happened:*
- The second Pass A attempt (document 3119) ran on the local broker as intended, but against a database that had never had migrations `zelda_api` 0029–0034 applied. That is every Phase 1 schema change.
- The blocking gate builds a fresh test database, so it never saw the gap. The addendum's §1 pinned the code, not the schema.
- Effect on 3119:
  - Extraction, chunking, insights and claims completed.
  - Truth Delta verification raised `no such column: zelda_api_observeddatapoint.role` and was recorded as a failure (`verification_failed_at`).
  - No report was written.
  - The document still reached `analyzed`.
  - A memo was generated through the failure path.

*Correction:*
- The services were stopped.
- The database was backed up with SQLite's online backup API (integrity `ok`) to `KCV_backups/db.pre-phase1-migrations-2026-10-04.sqlite3`, outside the repository, SHA-256 `baa2e577…4b7f9`.
- Migrations 0029–0034 were applied. `showmigrations` now lists nothing unapplied.
- Document 3119 is abandoned: status `error`, `source_entity` "NIKE, Inc. (abandoned, erratum E-3)".
- §1 "Setup" gains the requirement that the database have no unapplied migrations. The run wrapper now checks this in every server and worker process, and exits otherwise. Proved both ways: 0 pending on the migrated database (exit 0); 6 pending on a copy of the backup (exit 1).

*Effect on frozen baseline rows:* three of those migrations rewrite existing data, and they did so to document 3117 exactly as their code states:

| Migration | Document 3117 before | After |
|---|---|---|
| 0030 bound excerpts | claim excerpts of 1,309 and 1,312 characters (whole chunks, L-005) | 23 and 73 characters |
| 0031 role/origin | SEC observation with no role or origin | `can_establish` / `sec_filing` |
| 0033 honest label | 11 chunks labelled `claude-3-5-sonnet` (L-003) | `hash-legacy` |

The baseline ledger graded the pre-migration rows. Those rows are preserved unchanged in the backup, so the baseline's evidence stands.

*A passing control from the incident.* The 3119 memo states that the document's "verification failed", and calls the $52.8B figure one that "could not be independently verified". It is saved under `rerun/abandoned/`. This is the designed failure path (`truth_delta_tasks.verify_document_truth_delta`), observed working on a real failure.

## Follow-ups

- **Fail-closed test broker** (separate PR after this one): the test runner refuses any Celery broker that is not in-memory, as it already refuses network calls.
- **Schema check before local runs:** a local run protocol should require `manage.py migrate --check` to pass before the first upload. This could go in the same PR as the broker guard.
- **Upstash queue:** before any purge is proposed, capture a non-secret manifest of the queued task names, ids and arguments, and establish that no other environment or process references that instance.
