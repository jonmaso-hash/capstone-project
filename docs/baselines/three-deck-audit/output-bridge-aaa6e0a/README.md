# Memo-98 basis rule: complete-bridge allowlist at `aaa6e0a`

**Separate, additive evidence.** It edits nothing in `../output-fidelity-2fb8530/`, `../output-containment-3e0fa33/`, `../output-association-c297ec3/`, any run ledger, grading, memo, answer key, protocol or frozen fixture. No memo was regenerated and no live model run was made.

**Status:** branch `fix/usage-basis-output-fidelity`, pushed and **unmerged**, with no PR. Main is still `d276918`.
- RA-109 live output acceptance stays open.
- RA-106's scoped acceptance is unchanged.
- RA-108, overview coverage, styling, the P3 notes and overall hardening are separate.

| Commit | What |
|---|---|
| `c297ec3` / `f9c4704` | Positive association and its evidence (review: one remaining bridge P2) |
| `aaa6e0a` | **This correction:** `zelda_api/basis_fidelity.py` (`_BRIDGE`, `_bridges`, docstring); `zelda_api/tests_output_fidelity.py` (new regressions only; no existing body or expectation changed) |

## The finding and the correction

At `c297ec3` an anaphoric opener was enough to make a bridge, so a sentence that opened with "This" or "These" but named another metric kept the message pair alive:

| Intervening sentence (two notes; the passage is `The message figures use different bases [C3, C2]. <middle> The cumulative figure is overstated.`) | `c297ec3` | `aaa6e0a` |
|---|---|---|
| `This revenue figure is unaudited.` | last sentence became the message clarification | **unchanged** |
| `These operating expenses are unaudited.` | message clarification | **unchanged** |
| `These use different measurement bases for expenses.` | message clarification | **unchanged** |

**Correction:** the reviewer's candidate, applied as given. A bridge is now a deliberate allowlist matched against the **whole sentence**:

> `These|This|They|Both|Each|The two` `use(s) different measurement bases`, optionally followed by memo 98's `and cannot be compared or reconciled without clarification from management` or the note's `and need clarification before comparison`, then an optional `.` or `!`.

Any other wording ends the antecedent: another metric, a citation, a figure, a paraphrase, or a valid prefix with an added tail. The former citation and digit subchecks were **removed**, because the whole-sentence allowlist already admits neither.

## Emitted text ([output/emitted_text_probe.json](output/emitted_text_probe.json), helper at `aaa6e0a`)

| Case | Result |
|---|---|
| The three non-bridges above | unchanged |
| Bridge, short form `These use different measurement bases.` | the referent becomes the message clarification |
| Bridge, note form | message clarification |
| Bridge, memo-98 form | message clarification |
| Memo-98 contiguous passage (actual wording, two notes) | message clarification |
| Direct referent after `[C3, C2]`; cited `[C3] … [C2]`; noun "cumulative messages figure" | message clarification (the cited form keeps `[C3] [C2]`) |
| Earlier reviews: stale revenue antecedent; operating expenses with a sole note | unchanged |

**Memo replay** ([output/replay_memos_96_97_98.json](output/replay_memos_96_97_98.json)): **identical** to the `c297ec3` replay.

| Memo | Sections differing from stored |
|---|---|
| 98 | the same four sections, with the same text |
| 97 | none |
| 96 | only the accepted FF-405 `zelda_advantage` wording |

## Evidence

- **Red** ([output/red_run_on_c297ec3.txt](output/red_run_on_c297ec3.txt)): the new regressions run against the code at `c297ec3` gave **60 tests, 4 failures**. Three came from `test_an_anaphoric_sentence_naming_another_metric_ends_the_association` (one per sentence) and one from the memo writer. The positive controls (the three known bridge forms, plus the direct, cited and named paths) passed, as they should.
- **Green** ([output/green_module_run.txt](output/green_module_run.txt)): 60 OK at `aaa6e0a`. No existing test body or expectation was changed.

### New regressions

| Class | Covers |
|---|---|
| `BasisBridgeTests` | The three non-bridges with two notes leave the referent unchanged; the three known bridge forms continue the pair, with the exact emitted text; the direct, cited and named paths are unaffected |
| `PipelineBridgeTests` | The memo writer stores the three non-bridge passages (in `executive_summary`, `open_concerns` and `upside_scenario`) unchanged, and still corrects memo 98's contiguous `risk_assessment` |

### Mutations ([output/mutations_output.txt](output/mutations_output.txt))

**29 of 29 caught on the committed code `aaa6e0a`.**
- **How they ran:** one at a time, with the watchdog running.
- **Hashes:** the pre-mutation SHA-256 of all three files is in [output/pre_mutation_hashes.txt](output/pre_mutation_hashes.txt), and each file was verified after every restore and at the end.
- **Labels:** `tests_output_fidelity`, `tests_funding_fidelity` and `tests_usage_basis` (204 tests).

| Set | Mutations |
|---|---|
| Carried, unchanged | O1–O6, O8, F1–F7, F9, C1–C9, A1–A3 |
| **Retired** | **A4** ("any uncited sentence bridges"): its anchor, the opener-plus-subchecks rule, no longer exists; **replaced by B1**. **A5** ("a sentence stating a figure bridges"): the digit subcheck was removed as redundant, since the whole-sentence allowlist admits no figure. No gate remains to mutate, so no artificial substitute was kept to preserve the count. |
| **New B1** | Opener-only bridge recognition restored: caught (5 failures) |
| **New B2** | A valid bridge prefix permits an unrelated suffix (`match` in place of `fullmatch`): caught (2 failures) |

### Validation at `aaa6e0a`

**1,350 tests OK** in the four established sequential batches. Free RAM was 1.52–1.79 GB before each batch, and the watchdog logged nothing over 1,500 MB.

| Batch | Result |
|---|---|
| A | 319 OK |
| B | 415 OK |
| C | 430 OK |
| D | 186 OK |

`manage.py check`: no issues. `makemigrations --check --dry-run`: no changes.

## Isolation and limits

- **Isolation:** test databases only. No network, provider or model call; no memo regenerated; no frozen artifact edited.
- **Narrow by design:** only the three listed bridge forms continue an antecedent. Any paraphrase ("Neither interval is stated.") ends it, so a later bare referent is left as written. That is a missed correction rather than a wrong one.
- **Not proven live:** live behaviour still needs a post-merge run after review.
