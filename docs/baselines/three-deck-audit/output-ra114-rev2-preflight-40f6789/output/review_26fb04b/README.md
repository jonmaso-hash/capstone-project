# Review of `26fb04b`: three tooling fixes, with RED and GREEN (OFFLINE)

These are fixes to the **validation tooling**, not to Zelda. The live run was not executed. Every result here is offline: stand-ins, stubs, and dry run 4 with memo 104's recorded replies and a loopback-only network.

**The fixed tooling** is in `../../tooling_after_review_26fb04b/`. `../../tooling/` stays as it was at `26fb04b`, because dry runs 1–3 used it.
- **Changed:** `rev2_runtime.py`, `rev2_assess.py`, `rev2_probe.js`, `rev2_gate_selftest.py` (new cases).
- **New:** `rev2_probe_selftest.mjs`, `rev2_assess_selftest.py`.
- **Unchanged:** every other file.

## P1: failed or truncated model calls did not stop the run (`rev2_runtime.py`)

**Cause:** the gate logged an exception or `stop_reason` in `model_call_results.jsonl` but never set the shared abort, and checkpoints read only the ledger lines.

**Fix:**
- **In the gate:**
  - an exception from the call persists the abort (`fail_run`) before re-raising;
  - a reply whose `stop_reason` is not `end_turn` (for example `max_tokens`) persists the abort. The response is still returned to the application, because the call has already happened, but the run is over.
- **At every checkpoint:**
  - every allowed ledger line must have a completed result: present, no error, `end_turn`. A process that dies mid-call therefore leaves an unmatched line, and the checkpoint fails;
  - `after_memo` additionally confirms on the server, read-only, that the run document is `analyzed` with a memo.
- After the abort, every later call and checkpoint is refused, and application requests get 503 (unchanged).

| Case (`rev2_gate_selftest.py`) | RED at `26fb04b` (`red_on_26fb04b/gate_selftest.json`) | GREEN (`green/gate_selftest.json`) |
|---|---|---|
| memo call times out | `after_memo` accepted and advanced to `owner_matrix` | aborted; `after_memo` refused; next call refused |
| memo reply `stop_reason=max_tokens` | accepted, no abort | aborted; `after_memo` refused |
| marketplace extraction fails | its checkpoint accepted | aborted; checkpoint refused |
| allowed call with no recorded result | accepted | checkpoint refused ("no completed result") |
| server cannot confirm the memo | accepted | `after_memo` refused |
| **All 20 cases** | 15/20 (the 5 above fail) | **20/20** |

## P2: the panel assessor skipped criterion 4 (`rev2_assess.py`)

**Cause:**
- `document_form()` took `search=None` and made criterion 4 optional;
- the panel call passed no `/search/` record, so the panel "passed 1–6" without the retrieval comparison;
- a missing Q1 `/search/` also passed Q1.

**Fix:**
- `search` is a required argument. Criterion 4 fails unless the captured record is present, answered 200, and its results equal the evidence (ids, pages, text, relevance, order).
- The panel is compared with the captured Q1 `/search/` (step `doc:Q1:search`) for the same document.

| Variant, on dry run 3's records (`rev2_assess_selftest.py`) | RED at `26fb04b` | GREEN |
|---|---|---|
| unchanged | panel pass, criterion 4 **not checked** | panel pass, criterion 4 true; Q1 pass |
| Q1 `/search/` record removed | panel **pass**, Q1 **pass** | panel fail, Q1 fail (criterion 4 false) |
| Q1 `/search/` results mismatching | panel **pass** | panel fail, Q1 fail |
| **Result** | 0/3 | **3/3** |

## P2: upload polling could time out and still advance (`rev2_probe.js`)

**Cause:** after 180 polls the probe requested `after_memo` regardless of the status.

**Fix:**
- completion must be confirmed (`analyzed` and `memo_available`), or the probe aborts the attempt;
- the server's `after_memo` check (P1) is a second, independent guard.

| Scenario (`rev2_probe_selftest.mjs`, the real probe in a vm with stubbed fetch) | RED at `26fb04b` | GREEN |
|---|---|---|
| `processing` for all 180 polls | **requested `after_memo`** | aborted, no `after_memo` |
| `analyzed` with a memo on poll 3 | `after_memo` | `after_memo` |
| `analyzed` without a memo, all polls | **requested `after_memo`** | aborted |
| pipeline `error` | aborted | aborted |
| **Result** | 2/4 | **4/4** |

## Dry run 4 with the fixed tooling (`dry_run_4/`, OFFLINE)

A fresh copy, fresh fixtures and a fresh temporary Memurai. The same sequence as dry run 3.

**Results:**
- 14 checkpoints in order, with ledger lines 0, 1, 1, 1, 1, 1, 2 … 8, 8;
- 8 attempts, all allowed, **all `end_turn`**, 0 aborts;
- document 3147; Q1–Q7 document form criteria 1–6 met, **criterion 4 evaluated for the panel too**;
- pages 2 / 10 / 10, 12 / none / 2 / 2, 1 / none;
- the Paris control, the 403 checks and the panel all pass;
- the 72 matrix rows equal memo 104's (staff not run offline).

**Environment:**
- lowest free RAM 1.30 GB, and the watchdog didn't trip;
- the source DB, earlier copies and deck hash identically before and after;
- the installed Memurai's key counts are unchanged.

**Negative control:** after `end`, a question was refused by the gate as call 9 of 8, the run aborted, and the next request got 503.

These are offline results. They show the tooling enforces the plan; they decide nothing about RA-114.

## CI panel tests: resolved by the reviewer

The reviewer read job `122011320251` (run `40450338846`, merged main `40f6789`): **all seven `tests_assistant_panel_ask` tests ran and passed, with 3,963 tests passing overall.**

The log still requires sign-in from this machine, so that reading was not repeated here. The package's "unresolved" claim is withdrawn on the reviewer's evidence.
