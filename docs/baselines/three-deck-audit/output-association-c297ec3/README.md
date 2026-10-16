# Memo-98 basis rule: positive association at `c297ec3`

**Separate, additive evidence.** It edits nothing in `../output-fidelity-2fb8530/`, `../output-containment-3e0fa33/`, any run ledger, grading, memo, answer key, protocol or frozen fixture. Memo 98 and memo 97 are not edited or regenerated. No live model run was made.

**Status:** branch `fix/usage-basis-output-fidelity`, pushed and **unmerged**, with no PR. Main is still `d276918`.
- RA-109 live output acceptance stays open.
- RA-106's scoped acceptance is unchanged.
- RA-108, overview coverage, styling, the P3 notes and overall hardening are out of scope and still open.

| Commit | What |
|---|---|
| `2fb8530` / `60a5b3a` | First output-fidelity correction and its evidence |
| `3e0fa33` / `d3fa50b` | Containment corrections and their evidence (review: one remaining P2) |
| `c297ec3` | **This correction:** `zelda_api/basis_fidelity.py`, `zelda_api/tests_output_fidelity.py` |

## The finding and the correction

The review of `3e0fa33` found that the fallback still assigned unrelated prose to a usage note.

| Input | `3e0fa33` | `c297ec3` |
|---|---|---|
| Sole C3/C2 note: `Monthly operating expenses are overstated.` | "How the figure stated without an explicit interval relates to the monthly figure needs clarification before either is relied on." (expenses are on no list; sole-pair fallback) | **unchanged** |
| C3/C2 and C5/C6 notes: `The message figures use different bases [C3, C2]. Revenue is reported as $10M. The cumulative figure is overstated.` | last sentence became the message clarification (stale antecedent across revenue) | **unchanged** |
| Control: same two notes, `The cumulative figure is overstated.` alone | unchanged | unchanged |

**Correction.** A sentence is rewritten only with a **positive tie** to exactly one pair:

| Route | Ties when |
|---|---|
| Citations | Every cited ref is that pair's (statement aliases included) |
| Noun | Nothing is cited, and the sentence names the pair's counted noun ("messages") for exactly one pair |
| Antecedent | Nothing is cited, there is no noun, the sentence has a **definite figure referent** ("the cumulative figure", "the monthly total", "the figures"), and the discussion it continues, in the same paragraph or list item, is still about one pair: the last sentence resolved to that pair, with only **bridge** sentences between |

- **A bridge** opens with these/this/they/both/each/the two, cites nothing and states no figure. An example is memo 98's "These use different measurement bases and cannot be compared or reconciled without clarification from management."
- **Any other sentence ends the antecedent:** a different metric, another citation, a new figure, an unresolved sentence, or a new paragraph or bullet.
- **There is no sole-pair fallback.** One note does not make every uncited monthly or cumulative sentence about it.
- **The other-metric word list remains, but only as a backstop.** It stops a sentence that is tied to the pair yet also names revenue, customers and so on. The gate itself is the positive tie, so a metric on no list (expenses, churn, retention, support tickets) is kept because nothing ties it to the pair.

## Emitted text ([output/emitted_text_probe.json](output/emitted_text_probe.json), helper at `c297ec3`)

| Case | Result |
|---|---|
| Review 1: `Monthly operating expenses are overstated.` (sole note) | unchanged |
| Review 2: stale antecedent across revenue (two notes) | unchanged |
| Review 2 control | unchanged |
| Expense sentence between the pair and the referent | unchanged |
| Uncited sole-note scenario `If the cumulative figure is presented as monthly, the claim is materially overstated.` | unchanged (no tie) |
| Memo-98 contiguous passage, with one note or three notes | "... clarification from management. How the figure stated without an explicit interval relates to the monthly figure needs clarification before either is relied on." |
| Directly following referent after `[C3, C2]` | message clarification |
| Cited pair `[C3] ... [C2]` | message clarification `[C3] [C2]` |
| Noun "cumulative messages figure" | message clarification |
| Statement aliases `[S2] ... [S3]` | "The figure stated without an explicit interval [S2] sits beside a monthly rate [S3]." |
| Daily pair `[C6] ... [C5]` | daily clarification `[C6] [C5]` |
| Explicit cumulative pair `[C7, C9]` | "How the cumulative figure relates to the weekly figure ..." (its cumulative fact is kept) |
| Question after `[C3, C2]` | still a question; only its referent is corrected |

**Memo replay** ([output/replay_memos_96_97_98.json](output/replay_memos_96_97_98.json)): **identical** to the `3e0fa33` replay.

| Memo | Sections differing from stored |
|---|---|
| 98 | the same four sections, with the same repaired text |
| 97 | none |
| 96 | only the accepted FF-405 `zelda_advantage` wording |

## Evidence

### Red

All red runs used the application code at `3e0fa33`.

- **First run** ([output/red_run_on_3e0fa33.txt](output/red_run_on_3e0fa33.txt)): 52 tests, 14 failures. These covered the two review cases, four metrics on no list, an uncited sole-note scenario, intervening non-bridge sentences, a missing figure referent and the memo writer. One of the 14 was the test's own mistake; see the corrections below.
- **After the corrections and the edge tests** ([output/red_run_all_56_on_3e0fa33.txt](output/red_run_all_56_on_3e0fa33.txt)): the full current file, run against `3e0fa33` in a temporary worktree that was then removed, gave **56 tests, 14 failures**.
  - Three edge tests pass on the old code by design: O3, C1 and C6 guard gates that `3e0fa33` already had. They were added because removing the fallback made the older tests vacuous for those gates.

### Test corrections (all recorded in commit `c297ec3`)

1. **Question control, before the fix.** The new control asserted that `... [C3, C2]. Is the cumulative figure overstated?` is entirely unchanged. Both before and after the fix, the guard never turns a question into the judgment clarification. Its referent rule does correct "the cumulative figure" inside a question; that is existing behaviour, accurate, and outside this finding. The control now asserts no `basis_overstatement` and that the output is still a question.
2. **Four older `BasisGuardTests`.** Two of them failed on the first fix run ([output/first_fix_run.txt](output/first_fix_run.txt)), and two became vacuous. All four used a bare uncited sentence that only the removed sole-pair fallback tied to the note. They now name the pair's noun ("the cumulative messages figure/total"), and `test_idempotent` also asserts that the first pass did change the sentence.

### Regressions ([`zelda_api/tests_output_fidelity.py`](../../../../zelda_api/tests_output_fidelity.py), 56 tests)

| Class | Covers |
|---|---|
| `BasisAssociationTests` | Metrics on no list with a sole note (6 forms, including the uncited scenario); the stale two-pair antecedent and its control; intervening expense, churn, customers and users sentences; an inherited sentence without a figure referent. Positive controls: the memo-98 contiguous passage under 1 and 3 notes, a directly following referent, cited, noun and alias paths, explicit cumulative evidence, and a question |
| `BasisAssociationEdgeTests` | A named sentence not about the bases keeps its judgment (O3); a tied sentence that also names another metric is kept (C1); no inheritance across a blank line, a newline or a bullet (C6); an anaphoric sentence stating a new figure ends the antecedent (A5) |
| `PipelineAssociationTests` | The memo writer: the expense sentence and the stale-antecedent passage are stored unchanged; memo 98's contiguous passage is still corrected |
| Carried | All earlier classes, including the historical memo-98 replay, order and idempotence tests |

### Mutations ([output/mutations_output.txt](output/mutations_output.txt))

**29 of 29 caught on the committed code `c297ec3`.**
- **How they ran:** one at a time, with the watchdog running. SHA-256 of all three files was verified after every restore.
- **Labels:** `tests_output_fidelity`, `tests_funding_fidelity` and `tests_usage_basis` (200 tests).
- **Carried mutations:** O1–O6, O8, F1–F7, F9 and C1–C9. C5 was re-anchored to the antecedent gate.
- **New:**

| ID | Mutation | Result |
|---|---|---|
| A1 | The sole-pair fallback is restored | caught |
| A2 | Stale inheritance: an intervening sentence never ends the antecedent | caught |
| A3 | An inherited sentence needs no figure referent | caught |
| A4 | Any uncited sentence bridges | caught |
| A5 | A sentence stating a figure bridges | caught |

**First run** ([output/mutations_first_run.txt](output/mutations_first_run.txt), same code with 52 tests): 25 of 29 caught; four survived.

| Mutation | Why it survived | Fix |
|---|---|---|
| O3 | Its control sentence no longer resolved once the fallback was gone | A named control |
| C1 | No test tied a sentence to the pair while also naming another metric | A tied-and-other-metric test |
| C6 | The list-item test was reset by the "2." marker sentence, not by the newline | Blank-line, newline and bullet cases |
| A5 | No test had an anaphoric sentence stating a new figure | "They also report 40% growth." |

Only tests were added; the code is unchanged. Each of the four was caught on rerun, and the full set was then rerun on the committed code.

### Validation at `c297ec3`

**1,346 tests OK** in the four established sequential batches. Free RAM was 1.36–1.88 GB before each batch, and the watchdog logged nothing over 1,500 MB.

| Batch | Result |
|---|---|
| A | 315 OK |
| B | 415 OK |
| C | 430 OK |
| D | 186 OK |

`manage.py check`: no issues. `makemigrations --check --dry-run`: no changes. The focused related modules ran 265 OK ([output/focused_related_modules.txt](output/focused_related_modules.txt)) before the four edge tests were added.

## Isolation and limits

- **Isolation:** test databases only. No network, provider or model call; no memo regenerated; no frozen artifact edited.
- **Conservative:** a sentence with no citation, no pair noun and no contiguous, bridged antecedent is left as written, even if it does misstate the usage basis. That is a missed correction rather than a wrong one. The old sole-pair repairs of bare uncited sentences no longer happen.
- **Lexical:** the bridge and figure-referent forms are lexical. A paraphrased bridge (for example "Neither interval is stated.") ends the antecedent, so a later referent is kept as written.
- **Not proven live:** live behaviour still needs a post-merge run after review.
