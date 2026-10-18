# Review of 2465791 addressed: a placed figure is matched whole at `9d24d97`

**Separate, additive evidence.** It edits nothing in `output-arithmetic-nesting-2465791/`, any earlier review or grade, the memo-99 run evidence, any historical memo, frozen fixture or ledger. The reviews are recorded in [`../output-further-figure-review-ed29f3b-3/`](../output-further-figure-review-ed29f3b-3/README.md) (third review of `ed29f3b`) and [`../output-figure-form-review-2465791/`](../output-figure-form-review-2465791/README.md). No live model run was made.

**Status:** branch `fix/basis-label-source-context`, **unmerged**, with no PR. Main is still `64f9db5`.
- RA-109 live output acceptance stays open.
- RA-106's scoped acceptance is unchanged.
- RA-108 and overall hardening are out of scope and still open.

| Commit | What |
|---|---|
| `2465791` / `825d6c0` | Arithmetic, signs and nested asides keep the sentence (second review of `ed29f3b`) |
| `d4c2ba8` | Regressions only: "(700M messages)" and "(500M, 500M/month, 700M)" (third review of `ed29f3b`) |
| `9d24d97` | **This correction:** a figure's "+" and interval must be ones a cited statement states (`zelda_api/basis_fidelity.py`); regressions in `zelda_api/tests_output_fidelity.py` |

## Third review of `ed29f3b`: already kept

"(700M messages)" and "(500M, 500M/month, 700M)" keep the sentence at `bcf9e0a`, at `2465791` and now. `d4c2ba8` pins them through the full guard sequence and the helper, with the "(500M, 500M/month)" control:
- [output/further_figure_red_on_ed29f3b.txt](output/further_figure_red_on_ed29f3b.txt): **4 failures** on `ed29f3b`'s code.
- [output/further_figure_run_on_bcf9e0a.txt](output/further_figure_run_on_bcf9e0a.txt): passes on `bcf9e0a`'s code.
- Mutation **P32** (after one held figure, the rest of the aside is not checked) is caught by this test and the earlier unknown-number test.

## Review of `2465791`: the fix

**Before:** `_figure_key()` kept a figure's value and the words after it, and dropped the "+". The value had to be held, and the words had to be in the clause vocabulary. So "500M+" passed as 500M, and "500M/messages" passed because "messages" is a statement word.

**Now:** a figure's complete form (value, any "+", any "/interval") must be a form a cited statement states.
- A statement's forms are read from its own figures. The interval is taken from the figure ("500m/month") or its noun ("500M messages/month" states "500M/month").
- A placed figure may **leave out** a "+" or interval its statement gives ("140,000" for "140 000+", "500M" for "500M messages/month"). The restatement gives the statement's own wording back, so nothing in the text is lost.
- It may not **add** one: "500M+", "500M+/month" and "500M/messages" keep the sentence. So do the earlier "500M/day" and "$500M".

| Input | Output at `9d24d97` |
|---|---|
| "(500M+)", "(500M+/month)", "(500M/messages)" (**full sequence** and helper) | unchanged |
| "(700M messages)", "(500M, 500M/month, 700M)" (full sequence and helper) | unchanged |
| "140,000+ bots and 500M messages … [S1, S3]" | **restated** (control) |
| "140,000 bots and 500M/month … [S1, S3]" | **restated** (control: "+" left out, interval stated) |
| "(500M, 500M/month)" | **still restated** (accepted positive control) |
| Memo 99's accepted repairs | **still restated** |

All emitted text is in [output/emitted_text_probes.json](output/emitted_text_probes.json): 75 cases at `9d24d97`. The 63 carried from `2465791` emit **identical** text and changes.

## Replay of the actual memo replies

[output/replay_memos_96_97_98_99_9d24d97.json](output/replay_memos_96_97_98_99_9d24d97.json): memos 96, 97, 98 and 99 are **identical** to `2465791`'s replay, and so to the accepted replay.

## Evidence

### Red

The new test was run with `basis_fidelity.py` swapped in from older commits. The working copy was then restored from a byte copy and hash-checked.
- **`2465791`** ([output/red_run_on_2465791.txt](output/red_run_on_2465791.txt)): **6 failures**. All three cases fail, through both the full sequence and the helper. The controls pass.
- **`ed29f3b`** ([output/red_run_on_ed29f3b.txt](output/red_run_on_ed29f3b.txt)): the same **6 failures**.

### Green

**`9d24d97`:** 107 OK ([output/green_module_9d24d97.txt](output/green_module_9d24d97.txt)).

### Mutations

Labels: `tests_output_fidelity`, `tests_funding_fidelity` and `tests_usage_basis`.
- **Carried:** the 69 from `2465791`, plus P32 from `d4c2ba8`.
  - P22, P23, P24, P25 and P32 are re-anchored to the complete-form check, with the same semantics.
  - P23 now also covers this review's denominator case: with the interval left out of a figure's form, "500M/messages" passes as 500M.
- **New:**

| ID | Mutation |
|---|---|
| P32 | After one held figure, the rest of the text is not checked ("500M, 500M/month, 700M" passes) |
| P33 | A figure's "+" is not part of its form ("500M+" passes as 500M) |
| P34 | A statement's interval on its noun is not read ("500M messages/month" no longer states "500M/month": the control and memo repairs are lost) |
| P35 | Every stated figure admits a "+" ("500M+" passes when the statement says "500M") |

**Result: 73 of 73 caught at `9d24d97`.** The run used fifteen foreground chunks of five ([output/mutations_9d24d97_chunk01.txt](output/mutations_9d24d97_chunk01.txt) … `chunk15.txt`), with 2.24–2.34 GB free before each.

The new and re-anchored mutants were first run alone and all were caught ([output/mutations_targeted_new_and_reanchored.txt](output/mutations_targeted_new_and_reanchored.txt)). Each line names the tests that failed.

Every restore was SHA-256 checked, and the three guard and pipeline files are identical before and after: [output/pre_mutation_hashes_9d24d97.txt](output/pre_mutation_hashes_9d24d97.txt), [output/post_mutation_hashes_9d24d97.txt](output/post_mutation_hashes_9d24d97.txt).

**Interrupted run at `d4c2ba8`** ([output/interrupted_d4c2ba8_run/](output/interrupted_d4c2ba8_run/)): a 70-mutation run was started on `d4c2ba8`.
- Chunks 1–3 and C7 were caught: 22/22.
- A low-memory reap of idle background jobs then killed the chunk loop and the watchdog during C8. The orphaned runner left the C8 mutant in `zelda_api/funding_fidelity.py`.
- The runner was killed, the file restored to its exact pre-run bytes and the hashes checked. That run was superseded by the full run at `9d24d97` above.
- An earlier stall in that run came from a pipe in the chunk script, unrelated to memory.

### Validation at `9d24d97`

`manage.py check`: no issues. `makemigrations --check --dry-run`: no changes ([output/check_and_migrations.txt](output/check_and_migrations.txt)).

| Batch | Free RAM before | Result |
|---|---|---|
| A | 2.27 GB | 366 OK (364 + the 2 new tests) |
| B | 2.11 GB | 415 OK |
| C | 1.35 GB | 430 OK |
| D | 2.15 GB | 186 OK |

**1,397 tests OK.** The batches ran sequentially in the foreground with the 1.2 GB gate. The memory watchdog was not restarted after the reap, so this round has no watchdog log. Free RAM was gated and logged before every chunk and batch instead.

**Commands** are in `output/scripts/`:
- **Mutation runner:** `mutate_i.py.txt`, which carries `mutate_h.py.txt` and, through it, the chain recorded in `../output-arithmetic-nesting-2465791/output/scripts/`. It is driven by `i_one.sh.txt` → `mut_chunk_i.sh.txt`.
- **Batches:** `batch_i.sh.txt` and `t.sh.txt` (CI env, memory broker, `--parallel 1`).
- **Probes and replay:** `probe_i.py.txt` and `replay_memos.py.txt`, run through `shell.sh.txt`.

## Isolation and limits

- **Isolation:** test databases only. No network, provider or model call; no memo regenerated; no frozen artifact edited; no deployment; no paid-source Pass B. No credentials in this folder (leak-checked).
- **Bounded and lexical:**
  - A statement's interval is read only from "N/x" or "N noun/x". A statement written "500M messages per month" states no "500M/month" form, so a placed "500M/month" against it keeps the sentence. That is the conservative direction.
  - A figure that leaves out its statement's "+" or interval is still restated, because the restatement uses the statement's own words.
- **Not proven live:** live behaviour still needs a post-merge sample after review.
