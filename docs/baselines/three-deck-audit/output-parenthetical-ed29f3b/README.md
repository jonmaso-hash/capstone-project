# Review of 191e627 addressed: parenthetical asides kept at `1bb993b` / `ed29f3b`

**Separate, additive evidence.** It edits nothing in `output-bounded-placement-d76237d/`, `output-bounded-placement-review-191e627/`, any earlier review or grade, the memo-99 run evidence, any historical memo, frozen fixture or ledger. No live model run was made.

**Status:** branch `fix/basis-label-source-context`, **unmerged**, with no PR. Main is still `64f9db5`.
- RA-109 live output acceptance stays open.
- RA-106's scoped acceptance is unchanged.
- RA-108 and overall hardening are out of scope and still open.

| Commit | What |
|---|---|
| `e9d6763` / `d76237d` / `191e627` | Location restatement bounded to its clause and subject, controls and evidence (reviewed: changes required) |
| `5748649` | The review, recorded additively (`output-bounded-placement-review-191e627/`) |
| `1bb993b` | **This correction:** asides are checked like the rest of the clause (`zelda_api/basis_fidelity.py`); regressions in `zelda_api/tests_output_fidelity.py` |
| `ed29f3b` | Citations are judged only by the citation check, plus a control (after P12 survived at `1bb993b`) |

## The finding and what changed

### P2: the location restatement deleted unrelated information inside parentheses

At `d76237d`, `_placing_words()` removed parenthetical text before checking the clause, and the restatement then discarded it. It now checks asides too:
- An aside whose words are not all figures, the cited figures' own words or placing words keeps the sentence as written.
- An outer or unclosed aside's words stay in the text that is checked with the clause.
- **The one aside it may drop** is the model's own measurement-basis remark ("measurement basis unresolved|questioned|unclear|ambiguous", optionally "; see open concerns"). It is dropped only when both sides of the pair are cited, so the pair's clarification is restated in its place. This is what memo 99's two accepted repairs do.

| Input | Output at `ed29f3b` |
|---|---|
| "The company states the message figures (revenue is $10M) on the same slide [S2, S3]." (**full sequence**, memo-99 payload, and helper) | unchanged |
| "The company states the message figures (unaudited) on the same slide [S2, S3]." | unchanged |
| "The figures (not independently verified) appear on the same slide [S2, S3]." | unchanged |
| "The company states 140,000+ bots and 500M messages (measurement basis questioned) on the same slide [S1, S3]." | unchanged (only one side is cited, so no clarification replaces the remark) |
| "The company states the message figures ((nested) 500M) on the same slide [S2, S3]." | unchanged |
| "The company states the message figures (500M [C3]) on the same slide [S2, S3]." | unchanged (`ed29f3b` control: another citation) |
| "The company states the message figures [S2] on the same slide [S2, S3]." | unchanged (`ed29f3b` control) |
| "The company states the message figures (500M, 500M/month) on the same slide [S2, S3]." | **still restated** (positive control kept): "The company states 500M messages with no explicit interval [S2] on page 10, under 'Traction by Apr-16', and separately 500M messages/month [S3] on page 12 (how … relied on)." |
| Memo 99's "… either 500M total or 500M/month (measurement basis unresolved; see open concerns) on the same traction slide [S2, S3]." (full sequence) | **still restated**, as accepted |

**Why `ed29f3b`:** P12 ("another citation inside the clause no longer keeps the sentence") survived the first mutation run at `1bb993b`. A citation's letters ("c", "s") failed the word check before the explicit citation check was reached, so the citation guard was never tested on its own. The word check now skips citations and leaves them to the citation check, and two controls cover it.

All emitted text is in [output/emitted_text_probes.json](output/emitted_text_probes.json): 35 cases at `ed29f3b`. The 28 carried from the previous round (funding/narrator, revenue, negation and the earlier reviews' denial, condition, order and memo-98 probes) emit **identical** text to `191e627`'s probes.

## Replay of the actual memo replies

[output/replay_memos_96_97_98_99_ed29f3b.json](output/replay_memos_96_97_98_99_ed29f3b.json): memos 96, 97, 98 and 99 are **identical** to the accepted replay (`e9d6763`, itself identical to `91a9071`).
- Memo 99 still changes only `open_concerns`, `supported_points` and `business_model_analysis`, with the same repaired text.
- Memo 98's accepted corrections are unchanged.

The module's memo-99 checks still pass:
- other fields are exactly as stored;
- citation order is kept;
- reversed item order gives the same output;
- a second pass changes nothing;
- the stored-section pass changes the same three sections;
- the memo writer stores the repairs.

## Evidence

### Red ([output/red_run_on_d76237d.txt](output/red_run_on_d76237d.txt))

The new test was run against the application code at `d76237d` (blob `4ad3318…`). It failed with **6 failures**, all five helper cases plus the exact full-sequence probe:
- "(revenue is $10M)", full sequence and helper;
- "(unaudited)";
- "(not independently verified)";
- the one-sided basis remark;
- the nested aside.

The basis-aside positive test passed on the old code too. The `ed29f3b` citation controls were added after the P12 survivor and also pass on old code; they exist for the mutation run.

### Green

**`ed29f3b`:** 102 OK ([output/green_module_ed29f3b.txt](output/green_module_ed29f3b.txt)).

### Mutations

Labels: `tests_output_fidelity`, `tests_funding_fidelity` and `tests_usage_basis` (246 tests at `ed29f3b`). The 58 from the previous round are carried; P15, P16 and P17 are re-anchored to the new `_placing_words(…, clarified)` signature with the same semantics. New:

| ID | Mutation |
|---|---|
| P20 | Asides not checked (stripped before the word check, as at `d76237d`) |
| P21 | The basis remark is dropped even when the pair's clarification is not restated |

The redundant nested/unbalanced guard was removed from `1bb993b` before it was pushed, not mutated. An outer aside's words are already checked with the clause, so no test could ever have caught its removal.

| Run | Head | Result |
|---|---|---|
| Targeted (console only) | `1bb993b` | P15, P16, P17, P20, P21 all caught |
| 1 ([output/mutations_run1_1bb993b.txt](output/mutations_run1_1bb993b.txt)) | `1bb993b` | **59 of 60 caught. P12 survived** (see above); hashes matched after the run |
| — | `ed29f3b` | Citations skipped in the word check, controls added; P12 rerun alone, caught (console output) |
| 2 ([part 1](output/mutations_run2_ed29f3b_part1.txt), [part 2](output/mutations_run2_ed29f3b_part2_interrupted.txt), [part 3](output/mutations_run2_ed29f3b_part3.txt)) | `ed29f3b` | **60 of 60 caught.** Part 1: 30 (O1–L1). Part 2: 18 (L2–P9). Claude Code then stopped it, and the watchdog, for low memory, *between* mutants: nothing was left applied and the hashes matched. After the owner approved, the watchdog was restarted and part 3 ran the remaining 12 (P10–P21) |

Every restore in run 2 was SHA-256 checked. The three guard/pipeline files matched before, at the interruption, and after: [output/pre_mutation_hashes_ed29f3b.txt](output/pre_mutation_hashes_ed29f3b.txt), [output/post_mutation_hashes_ed29f3b.txt](output/post_mutation_hashes_ed29f3b.txt). Free RAM before each part was 2.07, 1.92 and 2.00 GB.

### Validation at `ed29f3b`

`manage.py check`: no issues. `makemigrations --check --dry-run`: no changes ([output/check_and_migrations.txt](output/check_and_migrations.txt)).

The four established batches ran sequentially in the foreground with the watchdog running and a 1.2 GB gate:

| Batch | Free RAM before | Result |
|---|---|---|
| A | 2.13 GB | 361 OK (358 + the 3 new tests) |
| B | 2.16 GB | 415 OK |
| C | 2.17 GB | 430 OK |
| D | 2.12 GB | 186 OK |

**1,392 tests OK.** The watchdog logged nothing over 1,500 MB ([output/memwatch_p2.log.txt](output/memwatch_p2.log.txt)).

**Commands:** `scripts/batch_one.sh.txt` through `scripts/t.sh.txt` (CI env, memory broker, `--parallel 1`). The mutation runner is `scripts/mutate_p.py.txt`, which carries `mutate_b54.py.txt` → `mutate_review.py.txt` → `mutate_bridge.py.txt` → `mutate_ra109_review.py.txt`. Probes and replay: `scripts/probe_p.py.txt`, `scripts/replay_memos.py.txt` through `scripts/shell.sh.txt`.

## Isolation and limits

- **Isolation:** test databases only. No network, provider or model call; no memo regenerated; no frozen artifact edited; no deployment; no paid-source Pass B. No credentials in this folder (leak-checked).
- **Bounded and lexical:**
  - **Asides:** classified only by the same small word list as the clause, plus one measurement-basis remark pattern.
  - **Anything else in parentheses:** keeps the sentence as written, so some safe asides ("(see slide 10)") now block a restatement. That is the conservative fallback the review asked for.
- **Not proven live:** live behaviour still needs a post-merge sample after review.
