# RA-114 post-merge verification at `40f6789` (PR #291), with the live-run preflight

**Status:** post-merge checks and a read-only preflight. No model call was made, and no worker or server was started. The application database, MFA and Memurai were not changed, and nothing was deployed. Earlier evidence folders are not edited.

Revision 2 of the live plan (`output-ra114-ranking-panel-9ee8d3d/NEXT_LIVE_VALIDATION_REV2_RA114.md`) has **not** been run. RA-108, RA-109, RA-114, Q-2–Q-4 and overall acceptance remain open. The seven predicted passes are offline predictions, not live results.

## 1. What merged (`output/merge_bytes.txt`)

| | |
|---|---|
| Merge commit | `40f6789889dfeaf6b67558f3e1f9981d0a05b30a`, parents `b278364` (main) and `a5164d4` (PR head) |
| `origin/main` at verification | `40f6789889dfeaf6b67558f3e1f9981d0a05b30a` |
| CI fix `a5164d4` | an ancestor of main |
| Validation SHA `b124c6b` | an ancestor of main |
| Tree of `40f6789` vs `a5164d4` | identical (`5f57445…`). The merge itself added nothing |

## 2. Merged files vs the validation commit `b124c6b`

- **Outside `docs/`**, the only difference is `a5164d4`'s three added labels in `.github/workflows/ci.yml`. The workflow change is CI wiring: it doesn't touch the application, the tests' content, the evidence or the live plan.
- **The application and test files:** all 12 files RA-114 changed have identical bytes at main and at `b124c6b`. These are git blob content hashes. The mutation log's "restored sha256" values were taken from the CRLF working copy, so some differ textually.
- **Under `docs/`**, the difference is the round 3 evidence commit `57a8a36`, which adds files only.
- **Both live-plan files** (revision 1, revision 2) are byte-identical to the reviewed copies.

**Consequence:** the round 3 results carry over to main without a rerun, as `1aab9e3` did for `b278364`:
- 702 OK;
- 32/32 targeted mutants (not complete mutation coverage);
- the offline replays;
- the race walk and the panel walks.

## 3. CI for the merged commit (`output/ci_main_jobs.json`)

| | |
|---|---|
| Run | https://github.com/jonmaso-hash/capstone-project/actions/runs/40450338846 (push, `40f6789`) |
| Job | `check` (122011320251), `ubuntu-latest`: **success**, every step including "Run test suite" |
| Only annotation | the Actions runtime notice (Node 20 actions forced to Node 24). It concerns the actions, not the tests |

**Not verified: whether CI ran the seven panel tests or skipped them.** `tests_assistant_panel_ask` and `tests_assistant_panel_escaping` skip with `node is not installed` when no `node` is on PATH. The job log is the only place that shows which happened. The log API returned 403 without a sign-in, `gh` isn't installed, and no Chrome browser was connected.

To settle it, open the job log, expand "Run test suite" and search for `tests_assistant_panel_ask`:
- seven `... ok` lines mean the tests ran;
- `skipped 'node is not installed'` means they were skipped.

GitHub's `ubuntu-latest` image normally includes Node, but that is an expectation, not evidence. Locally, all seven ran under Node v25.1.0 at `a5164d4`'s workflow fix.

## 4. Revision 2's post-merge requirement and the preflight

Revision 2 requires, before it runs:
- independent review and merge (done: #291);
- the post-merge byte check at the merge commit (done above);
- the owner's go-ahead (not given; this report is for that decision).

It inherits the preconditions of `1aab9e3`'s procedure and revision 1. Each is checked read-only below (`output/preflight_inputs.txt`).

| Precondition | State | Ready? |
|---|---|---|
| 1 Owner go-ahead | not given | **no (by design)** |
| 2 Code: execution SHA = `origin/main`, clean worktree | `40f6789` = main; worktree `KCV-pm-40f` clean apart from this folder. The run worktree must be a clean checkout of `40f6789` | yes |
| 3 Tests at the execution SHA: four fidelity modules (452), `check`, `makemigrations --check` | Same bytes as `b124c6b` (452 OK there), and CI ran all three on `40f6789`. **On run day the plan still requires them locally and serially** | at run time |
| 4a Fresh SQLite copy of the dev DB | source `KCV/db.sqlite3` present, sha256 `5a0b8c1c…7e9a2`, mtime 2026-10-11, unchanged | yes |
| 4b **New, unused Memurai dbs (not 6–9)** | **Memurai has 16 dbs and every one holds keys.** dbs 1, 8 and 11 hold only the three static `_kombu.binding.*` sets, the state the memo-104 run accepted for its broker. db1 and db8 were earlier runs' brokers, and db8 is excluded. **No db is clean for results and cache** | **no: owner decision** |
| 4c Paid keys blank | set in the run processes' environment at start, as before | at run time |
| 5 Memory: 1.2 GB free at start, watchdog 1500 MB, 0.9 GB floor | 1.93 GB free now | yes (re-check at start) |
| 6 **Browser gate on Chrome `b60b1997`** | **no Chrome browser is connected** to the extension | **no: needs the browser connected** |
| 7 **Accounts** | **no `m512mc_*` accounts in the source DB.** The run creates run-scoped fixtures on the copy, but the established tooling conflicts with precondition 7 and the standing rules (below) | **no: owner decision** |
| Deck | 175,622 bytes, sha256 `be7a7171…f3ef1`, matches the key | yes |
| Revision 1/2 run tooling | **not prepared** (below) | **no** |

### Blockers

1. **The established tooling reads password and TOTP files.** `f73bef5`'s run scripts depend on these files:
   - `setup_fixtures.py` creates the fixtures with a password from `pw.txt`;
   - `probe.py` signs in with `pw.txt`;
   - for staff, `probe.py` completes MFA setup through the real page, writes the TOTP secret to a scratchpad file and later reads it back.

   This conflicts with the standing rule ("Do not read or materialize password/TOTP files") and with precondition 7 as written. It also makes an MFA change on the copy's staff fixture, which precondition 7 forbids.

   The panel walks of rounds 2–3 avoided all of this with session cookies seeded on a throwaway copy, so no password is ever entered. That method is available, but it is a change to the procedure. **The owner decides which sign-in method the run uses, and what the staff browser check does without MFA setup.**
2. **No probe exists for revisions 1 and 2.** `probe.py` sends only the marketplace form (`{"q"}`). The run needs a revision 1/2 probe for:
   - the document form for Q1–Q7, with the per-question `/search/` equality and the DB byte check;
   - the authorization probe as Lite, paid and an unrelated investor;
   - the unrelated-question control;
   - the extra ledger checkpoints, including those around the panel document check;
   - an unrelated-investor fixture, which `setup_fixtures.py` doesn't create.

   It should be written and dry-run first against a throwaway server with extraction replaced by a recorder, which needs no model call. It should then be reviewed with the plan.
3. **Memurai isolation (4b):**
   - **Options:** use db11 (kombu bindings only) for the broker and choose a results/cache db; or run a second, temporary Memurai instance on another port with a run-local config, which leaves the installed configuration unchanged.
   - **Not an option without authorization:** flushing any db, which is destructive.
4. **The browser gate (6)** needs Chrome `b60b1997` connected to the extension.
5. **The base procedure isn't on main.** `1aab9e3`'s `NEXT_LIVE_VALIDATION.md` is only on `origin/docs/post-merge-verification-b278364`. Revisions 1 and 2 (on main) inherit it by commit. If that branch is deleted, the inherited preconditions and the F-1, F-2 and regression criteria become hard to reach. Merging that docs branch, or keeping it, removes the risk.

## 5. The run as specified (for the go-ahead; unchanged ceiling)

| | |
|---|---|
| Environment | local machine, run server and worker on a fresh SQLite copy of `KCV/db.sqlite3`. Memurai dbs per blocker 3; paid keys blank in-process; watchdog 1500 MB. Execution SHA `40f6789` |
| Target document | the **one** document created by the single upload of `manychat_series_a_audit_deck.pptx` (sha256 `be7a7171…f3ef1`) as the run's owner fixture. Its id is assigned at upload, which is recorded before any question |
| Accounts (run-scoped, on the copy only) | the owner of the profile that uploads, plus Lite, paid, staff and **an unrelated investor** (new for the revision 1 authorization probe). Sign-in method per blocker 1 |
| Model | `claude-sonnet-4-6` (code literal) for the memo and for query extraction |

**The calls, in order.** 8 at most, no retries; a 9th attempted call fails the run.

| # | Call | Expected model calls |
|---|---|---|
| — | ledger checkpoint (lines, sha256) before upload | — |
| 1 | upload, then the worker's memo generation | **1** |
| — | 90-row matrix, `/search/` and `/rag/` probes, browser checks | 0 |
| — | checkpoint; **Q1–Q7, document form**, `{"q": Qn, "document_id": <run doc>}` as the owner; checkpoint (no new line allowed) | **0** |
| — | unrelated control `{"q": "What is the weather in Paris?", "document_id": <run doc>}`; authorization probe (Q1 + run doc as Lite, paid, unrelated investor: 403 each) | 0 |
| — | checkpoint; **panel document check** in the browser (Library, "Ask about this document", context bar, Q1, then "Ask the marketplace instead" without sending); checkpoint (no new line allowed) | **0** |
| 2–8 | **Q1–Q7, marketplace form**, `{"q": Qn}` as the owner, once each (query extraction) | **7** |
| — | checkpoint; stop the worker; dump, after-snapshots, final checkpoint | 0 |
| | **Total** | **8** |

**What the run decides, and how it is graded:**
- **Criteria:** revision 1's RA-114 criteria 1–7, its authorization criteria and per-question grounding table, and revision 2's control and panel criteria.
- **F-1, F-2 and the regressions:** as in `1aab9e3`, with F-2's **"not exercised"** outcome available.
- **Grounding:** graded per question against `docs/baselines/manychat/ANSWER_KEY.md`. Excerpts alone are not a pass.
- **Matrix comparison:** `cmp_matrix.py` compares status, location, B2 and canary flags, not bodies. So the ranking change doesn't alter the 90-row matrix comparison by design, and a difference there would be a real finding.

## Verdict

**Revision 2 is not ready to execute.**
- **Ready:** the code and plan are verified post-merge, and the deck, source DB and memory are in order.
- **Not ready:** blockers 1–4 need owner decisions, a prepared probe and a connected browser before the go-ahead can be acted on. Blocker 5 is a recommended docs fix.
- **Open:** whether CI ran the panel tests is unverified (section 3).
