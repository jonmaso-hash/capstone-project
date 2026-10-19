# Second review of ed29f3b addressed: unknown numbers, arithmetic and nested asides kept at `2465791`

**Separate, additive evidence.** It edits nothing in `output-additional-figure-bcf9e0a/`, any earlier review or grade, the memo-99 run evidence, any historical memo, frozen fixture or ledger. The review is recorded in [`../output-additional-figure-review-ed29f3b-2/`](../output-additional-figure-review-ed29f3b-2/README.md). No live model run was made.

**Status:** branch `fix/basis-label-source-context`, **unmerged**, with no PR. Main is still `64f9db5`.
- RA-109 live output acceptance stays open.
- RA-106's scoped acceptance is unchanged.
- RA-108 and overall hardening are out of scope and still open.

| Commit | What |
|---|---|
| `bcf9e0a` / `aa42a62` | A figure must be one the cited statements hold (first review of `ed29f3b`) |
| `2465791` | **This correction:** signs, operators, partial figure tokens and nested or unbalanced parentheses keep the sentence (`zelda_api/basis_fidelity.py`); regressions in `zelda_api/tests_output_fidelity.py` |

## Where each reported case stood

**The review's three cases were already fixed at `bcf9e0a`:** "(600M messages)", "(500M, 600M/month)" and "(500M (600M))". 600M is not a value the cited statements hold, so the sentence is kept. They fail at `ed29f3b`, as reported, and are now explicit regressions through the full guard sequence and the helper.

**Still rewritten at `bcf9e0a`, and fixed here** (this is the review's "arithmetic and unclassified nested parentheses"):
- Operators between tokens were never looked at, so a sum, comparison or sign of *held* figures passed: "(500M + 500M)", "(500M = 500M/month)", "(500M-500M/month)", "(~500M)".
- "500M+500M" was read as one figure token whose value, 500M, is held.
- A nested aside holding only held figures, "(500M (500M/month))", and an unbalanced one passed.

## What changed

- **Separators:** words and figures in placing wording may be separated only by spaces, commas and full stops. Any other character (`+`, `-`, `=`, `~`, `%`, a quote, a parenthesis left over) keeps the sentence.
- **Whole figure tokens:** a figure token must be whole: a value, an optional "+", one "/interval" and closing punctuation ("140,000+", "500M/month,"). "500M+500M", "1.5x" and a lone "$" keep the sentence.
- **Parentheses:** single-level asides are taken out and judged as before. A nested or unclosed aside leaves a parenthesis behind, which the separator check rejects. A separate nesting counter was written first and then removed before commit: no test could ever catch its removal, for the same reason.
- **List markers:** a list marker ("- ", "• ") is the line's lead. With no reporting verb, the clause is checked from after its lead, so a bulleted "- The figures appear on the same slide [S2, S3]." is still restated, as before.

| Input (helper unless noted) | Output at `2465791` |
|---|---|
| "(600M messages)", "(500M, 600M/month)", "(500M (600M))", "(500M + 500M)" (**full sequence** and helper) | unchanged |
| "(500M+500M)", "(500M = 500M/month)", "(500M-500M/month)", "(~500M)", "(500M, 5%)", "(500M (500M/month))", "(500M))" | unchanged |
| "The company states (the message figures on the same slide [S2, S3])." | unchanged |
| "- The figures appear on the same slide [S2, S3]." / "• …" | **restated** (control) |
| "(500M, 500M/month)" | **still restated** (accepted positive control) |
| Memo 99's accepted repairs | **still restated** |

All emitted text is in [output/emitted_text_probes.json](output/emitted_text_probes.json): 63 cases at `2465791`. The 45 carried from `bcf9e0a`'s probes emit **identical** text and changes.

## Replay of the actual memo replies

[output/replay_memos_96_97_98_99_2465791.json](output/replay_memos_96_97_98_99_2465791.json): memos 96, 97, 98 and 99 are **identical** to `bcf9e0a`'s replay, and so to the accepted replay.

## Evidence

### Red

- **On the `ed29f3b` code** ([output/red_run_on_ed29f3b.txt](output/red_run_on_ed29f3b.txt)): the new regression fails with **16 failures**, every case, including the review's three through the full sequence.
- **On the `bcf9e0a` code** ([output/red_run_on_bcf9e0a.txt](output/red_run_on_bcf9e0a.txt)): **9 failures**, every arithmetic, sign, nested and unbalanced case.
  - The review's three cases and "(500M, 5%)" pass there.
  - The list-marker control was run only on `bcf9e0a`, where it passes: it exists for the mutation run (P31).

The application file was restored from git after the `ed29f3b` run, and the worktree was checked clean.

### Green

**`2465791`:** 105 OK ([output/green_module_2465791.txt](output/green_module_2465791.txt)).

### Mutations

Labels: `tests_output_fidelity`, `tests_funding_fidelity` and `tests_usage_basis`.
- **Carried:** the 66 from `bcf9e0a`.
  - P16, P17 and P24 are re-anchored, with the same semantics: the no-verb gate now checks from after the lead, and the fact-side filter now uses the whole-figure check.
  - **P27 is retired:** its lone-"$" guard was removed, because the whole-figure check rejects a lone "$" before a value is read.
- **New:**

| ID | Mutation |
|---|---|
| P28 | Signs and operators between words are not checked ("500M + 500M", "~500M") |
| P29 | A figure token need not be whole ("500M+500M" read as 500M) |
| P30 | Parentheses count as separators (a nested or unclosed aside passes) |
| P31 | A list marker is checked as clause wording (a bullet's repair is lost) |

**Result: 69 of 69 caught at `2465791`.** The run used ten foreground chunks ([output/mutations_2465791_chunk01.txt](output/mutations_2465791_chunk01.txt) … `chunk10.txt`), with 1.45–1.96 GB free before each chunk. There was no interruption this round.

Before committing, the new and re-anchored mutants were run alone on the same working-tree content, and all were caught ([output/mutations_targeted_new.txt](output/mutations_targeted_new.txt)). Its RAM line names `aa42a62` because the change was not yet committed.

Every restore was SHA-256 checked, and the three guard and pipeline files are identical before and after: [output/pre_mutation_hashes_2465791.txt](output/pre_mutation_hashes_2465791.txt), [output/post_mutation_hashes_2465791.txt](output/post_mutation_hashes_2465791.txt).

### Validation at `2465791`

`manage.py check`: no issues. `makemigrations --check --dry-run`: no changes ([output/check_and_migrations.txt](output/check_and_migrations.txt)).

| Batch | Free RAM before | Result |
|---|---|---|
| A | 1.40 GB | 364 OK (362 + the 2 new tests) |
| B | 1.38 GB | 415 OK |
| C | 1.40 GB | 430 OK |
| D | 1.44 GB | 186 OK |

**1,395 tests OK.** The batches ran sequentially in the foreground, with the watchdog running and the 1.2 GB gate. The watchdog logged nothing over 1,500 MB ([output/memwatch_g.log.txt](output/memwatch_g.log.txt)).

**Commands** are in `output/scripts/`:
- **Mutation runner:** `mutate_g.py.txt`, which carries `mutate_e29.py.txt` → `mutate_p.py.txt` → `mutate_b54.py.txt` → `mutate_review.py.txt` → `mutate_bridge.py.txt` → `mutate_ra109_review.py.txt`. It is driven by `mut_chunk.sh.txt`.
- **Batches:** `batch_one.sh.txt` and `t.sh.txt` (CI env, memory broker, `--parallel 1`).
- **Probes and replay:** `probe_g.py.txt` and `replay_memos.py.txt`, run through `shell.sh.txt`.

## Isolation and limits

- **Isolation:** test databases only. No network, provider or model call; no memo regenerated; no frozen artifact edited; no deployment; no paid-source Pass B. No credentials in this folder (leak-checked).
- **Bounded and lexical:**
  - Placing wording is now limited to the vocabulary, held figures, spaces, commas and full stops.
  - Harmless wording outside that, such as a hyphenated word, a quoted phrase or "(see slide 10)", now also keeps the sentence. That is the conservative fallback the reviews asked for.
- **Not proven live:** live behaviour still needs a post-merge sample after review.
