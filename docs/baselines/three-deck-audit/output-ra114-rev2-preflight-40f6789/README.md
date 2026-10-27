# RA-114 revision 2: preflight package for independent review (`40f6789`)

**Status:** preparation only. **The live run has not been executed.** No live model call was made, the worker was never started, nothing was deployed, and the source application database and MFA were not changed.
- **Offline:** every result below comes from **offline dry runs**. Model replies were memo 104's recorded replies, served by a stand-in, and the network was loopback only. They test the tooling and the procedure. **They are not live results and decide nothing about RA-114.**
- **Revision 2's seven predicted grounding passes remain predictions.**
- RA-108, RA-109, RA-114, Q-2–Q-4 and overall acceptance remain open.
- This builds on `99c92ea` (post-merge verification and preflight), which is not edited.

## 1. Main and the validated code

| | |
|---|---|
| `origin/main` | `40f6789889dfeaf6b67558f3e1f9981d0a05b30a`, unchanged since `99c92ea` (no commits after the #291 merge) |
| Application files vs `b124c6b` | identical (`99c92ea`, `output/merge_bytes.txt`). Only the three CI labels differ |
| The run's code check | every `rev2_run.py` start compares the worktree's application files with `40f6789`: **0 differing** in every dry run |

Main hasn't moved, so no new difference needed assessing, and the carried-forward evidence of `99c92ea` stands.

## 2. The revision 2 probe and run tooling (`tooling/`, saved as `.txt`)

| File | Role |
|---|---|
| `rev2_runtime.py` | the **model-call gate**; the **ordered checkpoints**; the **request recorder** and the `/__rev2/` endpoints (probe page, state, checkpoint, record, abort, deck); the offline stand-in and the network block |
| `rev2_run.py` | wrapper: isolation checks (code SHA, copy DB, run Memurai instance, paid keys blank, retries 0, migrations); modes `check`, `migrate`, `server`, `worker`, `script`, `setpassword` |
| `rev2_probe.html`, `rev2_probe.js` | the probe page, served same-origin. Steps 1–12 in revision 2's order, each checking identity and phase |
| `rev2_prep.py` | read-only hashes; creates the run's copy from the source opened read-only |
| `rev2_fixtures.py` | run-scoped accounts with **unusable passwords** (plus the unrelated investor); sequence bump |
| `rev2_assess.py` | read-only assessment: revision 1 criteria 1–7, authorization, control, panel, marketplace control, matrix vs memo 104, ledger integrity; grounding reported as an aid |
| `rev2_memwatch.ps1`, `rev2_memurai.conf` | watchdog (0.9 GB floor, 1500 MB); temporary Memurai config |
| `live_config.template.json.txt` | the live configuration, to fill on run day |
| `rev2_gate_selftest.py`, `rev2_dry_sessions.py`, `rev2_dry_driver.mjs` | **offline only:** gate self-test; throwaway sessions on the dry-run copy; the headless driver |

**Where things come from:**
- **Questions:** taken verbatim from memo 104's probe config, and equal to `ANSWER_KEY.md` "Fixed questions".
- **Control question:** taken from revision 2.
- **Matrix:** memo 104's 16 surfaces, plus `/search/` and `/rag/`.
- **Expected outcomes and order:** revisions 1 and 2. See `RUNBOOK_REV2_RA114.md` for the step table.

## 3. Credentials, sign-in and MFA

No credential file or TOTP file is read anywhere in the tooling:
- fixtures get unusable passwords;
- the owner sets each password in their own terminal (`setpassword`, `getpass`, run accounts and run copy only);
- every live sign-in is by hand in Chrome;
- the probe runs inside that signed-in tab, so no session cookie leaves the browser.

**Staff MFA stays enforced:**
- the staff step refuses to run unless the session carries the MFA stamp;
- enrollment of the run's staff fixture is by hand, on the copy only;
- whether that counts as an MFA change under base precondition 7 is an **owner decision**.

**The dry runs** used throwaway sessions seeded on the dry-run copy, because no person could sign in offline:
- the keys were written to a local file and never printed or committed;
- a scan found none of the 15 session keys or probe tokens in the committed files;
- staff was not exercised offline.

## 4. Memurai isolation

A **separate localhost instance works within the memory limits:**
- **Instance:** `memurai.exe` 8.1 with a run-local config: 127.0.0.1:6391, 2 dbs, `save ""`, no AOF, `maxmemory 64mb`, ≈75 MB working set.
- **Checks:** every start checked the instance's port, pid and `config_file`.
- **Lifecycle:** it was shut down with `nosave` between attempts and after the last one.
- **The installed instance on 6379** was never used. Its key counts are identical before and after (`output/dry_run_3/memurai_after.txt`), and no existing db was cleared, flushed or repurposed.

## 5. Offline dry runs (OFFLINE evidence: stand-in model, loopback network)

**Gate self-test** (`output/gate_selftest/gate_selftest.json`): **15/15.**
- **The planned sequence:** 8 calls, every checkpoint accepted.
- **Refused, each aborting the run:**
  - a call before the upload;
  - any call after an abort;
  - a second memo call;
  - an extraction in the memo phase;
  - a client with SDK retries;
  - an extraction during the document form (whose checkpoint then fails);
  - an extraction during the panel check;
  - Q2's text in Q1's phase;
  - a second extraction for one question;
  - the 9th call (ceiling);
  - an out-of-order checkpoint.
- **A missing memo** fails `after_memo`.
- **A question with no call** is a recorded deviation.
- **Two processes racing** for one allowance get exactly one call.

**Dry run attempts**, all preserved:

| Attempt | Outcome | What it found |
|---|---|---|
| 1 (`output/dry_run_1_aborted/`) | **aborted at the identity precondition, 0 calls** | the probe truncated page text to 300 characters, so the nav check could not see the username. Fixed (full text). The abort path worked: every later request got 503 |
| 2 (`output/dry_run_2_memory_stop/`) | **stopped by the memory watchdog** during the panel step (free 0.79 GB < 0.9 GB floor; headless Chrome plus the popup). 1 call made | the recorder lost every JSON POST (`RawPostDataException`, reading `request.body` after DRF). Fixed: bodies are read before the view, and a failing field no longer drops the record. Diagnosed on a separate debug copy, which is not evidence of the procedure |
| **3** (`output/dry_run_3/`) | **completed**; lowest free RAM 1.16 GB | see below |

**Dry run 3** (`assessment.txt`, `assessment.json`). These are OFFLINE results.

**Run integrity:**
- 14 checkpoints in order, ledger lines exactly as planned: 0, 1, 1, 1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 8.
- 8 attempts, 0 refused, in the planned phases and kinds: memo, then Q1…Q7 extraction, every client with `max_retries` 0.
- One upload: 201, deck SHA-256 equal to the key, by the owner, in phase `memo`. Document **3147**.
- The document-form and panel ledger windows were unchanged.
- No abort, and 0 recorder errors.

**Document form, Q1–Q7:** revision 1 criteria 1–6 **all met for every question**:
- exact request body;
- 200 and `success`, the right `document_id`, `results` empty;
- not the fallback;
- every excerpt byte-identical to its chunk in the copy;
- identical to `/search/`;
- `no_relevant_evidence` explicit;
- the response exactly the fixed sentence.

| Q | Pages (offline) | Revision 2 prediction |
|---|---|---|
| Q1 | 2 | 2 |
| Q2 | 10 | 10 |
| Q3 | 10, 12 | 10, 12 |
| Q4 | none | none |
| Q5 | 2 | 2 |
| Q6 | 2, 1 | 2, 1 |
| Q7 | none | none |

The dry run ingested the frozen deck offline. Its **12 chunks are identical** (index, page, text) to memo 104's recorded chunks (`zelda_api/data/document_retrieval/memo104_chunks.json`), and the pages reached match the prediction. That supports the prediction's premise ("if the live deck chunks the same way"), but it is not a live result. **Grounding is not graded here.** The grader decides it against the answer key on the live run.

**The other checks:**
- **Unrelated control (Paris):** 200, `no_relevant_evidence` true, 0 evidence, exact body.
- **Authorization:** Lite, paid and the unrelated investor each got 403 and 403 (document form, `/search/`), with no document text in the body.
- **Panel:**
  - exactly one `/ask/`, sent by the panel's own code;
  - body exactly `{"q": Q1, "document_id": 3147}`;
  - response criteria 1–6 met;
  - rendered "Page 2 · Why this deck fits the audit leg", with 0 marketplace cards;
  - context bar "ManyChat";
  - cleared without a second request;
  - ledger unchanged.
- **Marketplace form, Q1–Q7:** 200, exact `{"q"}` bodies, and responses equal to memo 104's. That is expected, since the stand-in returned memo 104's extraction replies, so it says nothing about the live model.
- **Matrix:** 72 rows (owner, Lite, paid, signed out), **all equal to memo 104's** on status, location, B2 and canary (`M_search`/`N_rag` on the fields memo 104 recorded). The canary showed only on the owner's own profile, as in memo 104. **Staff was not run offline.**
- **Outbound connections blocked offline:** 3 public-record addresses (the entity-integrity check). The live run reaches public sources as memo 104 did.
- **Not exercised offline:** the worker (Celery was eager in the server, so the memo call came from the server process; in the live run it comes from the worker, through the same gate and files); manual logout POSTs; staff; the browser gate.

**Post-run negative control** (`dry_driver_negative.json`), after `end`:
- the probe step refused (wrong phase);
- a direct marketplace question was **refused by the gate as call 9 of 8** before reaching the stand-in, and returned 500;
- the run aborted, and the next application request got **503**;
- the allowed total stayed 8. Ledger line 9 is the refused attempt (`model_calls_at_end.jsonl` is the ledger before it).

**Sources unchanged:** the source DB, all earlier copies and the deck have equal hashes before and after (`hashes_before/after.json`).

## 6. Panel tests in merged-main CI: **unresolved**

The job log shows whether `tests_assistant_panel_ask`'s seven tests ran or skipped (`node is not installed`). It is not reachable here:
- the API log endpoint returns 403;
- the web page says "Sign in to view logs";
- `gh` isn't installed and no Chrome browser was connected.

The only stored GitHub credential is the Git Credential Manager's. Extracting it for an API call wasn't done without the owner's say-so. **Local success does not show that CI ran them.**

To settle it, any one of these works:
- connect Chrome and read job 122011320251's "Run test suite" step;
- install `gh` and run `gh run view 40450338846 --log`;
- authorize one read-only API call with the stored credential.

## 7. The base procedure

It is preserved by the pushed tag `ra114/base-live-procedure-1aab9e3`, plus a byte-verified copy. `BASE_PROCEDURE.md` documents how base, revision 1, revision 2 and this runbook stack.

## Remaining blockers before live authorization

1. **Independent review** of this package, the runbook and the tooling.
2. **Owner decisions:**
   - (a) staff MFA enrollment of the run fixture on the copy, under base precondition 7, or run without the staff check;
   - (b) accept the runbook's method changes (manual sign-in, in-browser probe, temporary Memurai).
3. **Chrome `b60b1997` connected** for the browser gate, with popups allowed for 127.0.0.1:8000.
4. **Memory:** start with ≥ 1.2 GB free and other applications closed. Offline, Chrome plus the popup drove free RAM to the floor once.
5. **CI panel-test execution unresolved** (section 6).
6. **On run day:** base precondition 3 (452 OK, `check`, `makemigrations --check`) at the execution SHA, serially.
