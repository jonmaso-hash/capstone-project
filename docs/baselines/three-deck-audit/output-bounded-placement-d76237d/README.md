# Review of b54d82b addressed: the location restatement bounded to its own clause and subject at `e9d6763` / `d76237d`

**Separate, additive evidence.** It edits nothing in `output-fact-placement-91a9071/`, `output-fact-placement-review-b54d82b/`, any earlier review or grade, the memo-99 run evidence, any historical memo, frozen fixture or ledger. No live model run was made.

**Status:** branch `fix/basis-label-source-context`, **unmerged**, with no PR. Main is still `64f9db5`.
- RA-109 live output acceptance stays open.
- RA-106's scoped acceptance is unchanged.
- RA-108 and overall hardening are out of scope and still open.

| Commit | What |
|---|---|
| `8dfe5f5` / `91a9071` / `b54d82b` | Fact-by-fact placement, its controls and evidence (reviewed: changes required) |
| `f7145d1` | The review, recorded additively (`output-fact-placement-review-b54d82b/`) |
| `e9d6763` | **This correction:** `zelda_api/basis_fidelity.py`; regressions in `zelda_api/tests_output_fidelity.py` |
| `d76237d` | Question and condition controls after the first mutation run (tests only; `basis_fidelity.py` blob `4ad3318…` identical to `e9d6763`) |

## The two findings and what changed

### 1. P2: an unrelated clause, its narrator and its citation were swallowed

At `91a9071`, the clause started only after `;`, `:` or a dash. The rewrite therefore replaced everything between the first reporting verb and the citation group.

**Clause start.** The clause now also starts after a clause-linking comma: ", while", ", whereas", ", and" or ", but", outside parentheses. Other commas (in "140,000+", in lists, inside parentheses) do not end it, so no comma-as-boundary rule was introduced.

**When the clause is rewritten.** Only when it is known; otherwise the sentence is kept as written:

| Check | Kept when |
|---|---|
| Other citation | the clause contains any citation besides the shared-place group |
| Narrator | a cited figure is reported by a narrator (`narrator` on its item), not by the company |
| Subject | with a reporting verb, the subject is not the company's own ("the company", "the deck", "the pitch deck", "the presentation", "the founder(s)", "management") |
| Predicate | with no reporting verb, there is no linking verb ("appear(s)", "is", "are", "was", "were", "sit(s)") |
| Wording | any word outside parentheses is not a figure, one of the cited figures' own words, or a short list of placing words ("the", "both", "figures", "metric", "usage", "message", "total", "of", "that", …) |

A clause without a subject still becomes "the deck states", but only that clause, never the whole sentence.

| Input | Output |
|---|---|
| "Pitch Deck Hunt reports $23.1M raised [S4], while the usage figures appear on the same slide [S2, S3]." (full sequence, memo-99 payload) | "Pitch Deck Hunt reports $23.1M raised [S4], while the deck states 500M messages with no explicit interval [S2] on page 10, under 'Traction by Apr-16', and separately 500M messages/month [S3] on page 12 (how the figure stated without an explicit interval relates to the monthly figure needs clarification before either is relied on)." |
| "The company reports revenue of $10M [C8], while the message figures appear on the same slide [S2, S3]." | "The company reports revenue of $10M [C8], while the deck states 500M messages … [S2] … [S3] on page 12 (…)." |
| "Revenue is $10M [C8], and the message figures appear on the same slide [S2, S3]." | "Revenue is $10M [C8], and the deck states 500M messages … [S2] … [S3] on page 12 (…)." |
| "Pitch Deck Hunt reports $23.1M raised [S4], while the company states the message figures on the same slide [S2, S3]." | "…[S4], while the company states 500M messages … [S2] … [S3] on page 12 (…)." |
| "The company states the message figures on the same slide [S2, S3], while Pitch Deck Hunt reports $23.1M raised [S4]." | "The company states 500M messages … [S3] on page 12 (…), while Pitch Deck Hunt reports $23.1M raised [S4]." |
| "Pitch Deck Hunt states the message figures on the same slide [S2, S3]." | location rule: unchanged. In the full sequence only the merged narrator-provenance guard's accepted note is added ("(not Pitch Deck Hunt's: [S2, S3] are the company's own traction statements)") |

The funding/narrator probe is also covered through the memo writer (`PipelineReviewB54d82bTests`).

### 2. P2: the object of a negation was changed

A denial is no longer a known affirmative placing clause: "does not" breaks the company-subject check, and "not", "never", "do" and "places" are not placing words.

| Input | Output |
|---|---|
| "The company does not state that the figures appear on the same slide [S2, S3]." | unchanged (helper and full sequence) |
| "The company states that the figures do not appear on the same slide [S2, S3]." | unchanged |
| "The figures do not appear on the same slide [S2, S3]." | unchanged |
| "The deck never places the figures on the same slide [S2, S3]." | unchanged |

### Conservative fallbacks (all unchanged)

| Input | Why kept |
|---|---|
| "Revenue is $10M, the message figures appear on the same slide [S2, S3]." | the comma links no clause, so "revenue" is in the clause |
| "Revenue is $10M while the message figures appear on the same slide [S2, S3]." | no comma: one clause, with "revenue" |
| "Revenue and the message figures appear on the same slide [S2, S3]." | "revenue" |
| "The company states revenue and the message figures on the same slide [S2, S3]." | "revenue" |
| "The company states the message figures (see revenue [C8]) on the same slide [S2, S3]." | another citation in the clause |
| "Message figures on the same slide [S2, S3] need clarification." | no predicate |
| "Are the figures on the same slide [S2, S3]?" | a question (`d76237d` control) |
| "If management confirms the interval, and the figures appear on the same slide [S2, S3], the deck should say so." | a condition (`d76237d` control) |
| narrated S3: "The company states the message figures on the same slide [S2, S3]." / "The figures appear on the same slide [S2, S3]." | a narrated cited figure |

"The company states the message figures (500M, 500M/month) on the same slide [S2, S3]." is still restated: a comma inside parentheses doesn't end the clause.

All emitted text is in [output/emitted_text_probes.json](output/emitted_text_probes.json). It includes the earlier review's probes (denials, conditions, interleaved order S1, S3, S2 and memo 98's conditional overstatement), whose outputs are unchanged.

## Replay of the actual memo replies

[output/replay_memos_96_97_98_99_e9d6763.json](output/replay_memos_96_97_98_99_e9d6763.json): memos 96, 97, 98 and 99 are **identical** to the accepted `91a9071` replay. Memo 99 still changes only `open_concerns`, `supported_points` and `business_model_analysis`, with the same repaired text. `d76237d` changes tests only, so the replay holds there too.

The memo-99 module checks are unchanged and pass:
- every other field is exactly as stored;
- citation order is kept;
- reversed item order gives the same output;
- a second pass changes nothing;
- the stored-text pass changes the same three sections;
- the memo writer stores the repairs.

The new probe tests add idempotence and reversed-item checks for the restated funding/narrator sentences.

## Evidence

### Red ([output/red_run_on_91a9071.txt](output/red_run_on_91a9071.txt))

The new test classes, at `e9d6763`'s test module, were run against the application code at `91a9071` (blob `696cbc5…`, restored afterwards and hash-checked): **10 tests, 9 failing (20 failure entries)**.
- Reviewer's probes: funding/narrator, both revenue probes, negated placement and the memo writer.
- Added controls: other negations, unresolved boundary/subject, narrators on either side, narrated figure, no predicate, idempotence.

The tenth test (the parenthetical comma, a positive control) passed on the old code too. The `d76237d` question/condition controls also pass on old code; they exist for the mutation run.

**Test correction:** at first the narrator control expected the whole sentence unchanged in the full sequence. The merged narrator-provenance guard correctly adds its accepted note there, so the test now asserts that the location rule leaves the clause alone and that no `basis_` change fires.

### Green

- **`e9d6763`:** 98 OK.
- **`d76237d`:** 99 OK ([output/green_module_d76237d.txt](output/green_module_d76237d.txt)).

### Mutations

Labels: `tests_output_fidelity`, `tests_funding_fidelity` and `tests_usage_basis` (243 tests at `d76237d`). The 49 from the previous round are carried; P8 is re-anchored to the moved head line with the same semantics.

| ID | Mutation |
|---|---|
| P11 | A clause-linking comma no longer starts the clause (the funding clause is swallowed) |
| P12 | Another citation inside the clause no longer keeps the sentence |
| P13 | A narrated cited figure is restated under the clause subject |
| P14 | Any subject is used (a narrator's, or a denial's) |
| P15 | The object after the reporting verb may hold other facts or a denial |
| P16 | A clause without a reporting verb may hold other facts or a denial |
| P17 | A clause with no predicate is restated |
| P18 | Denial words count as placing words (the negation guard negated) |
| P19 | The reconstruction guard is inverted |

| Run | Head | Result |
|---|---|---|
| 1 ([output/mutations_run1_e9d6763.txt](output/mutations_run1_e9d6763.txt)) | `e9d6763` | **56 of 58 caught.** P5 (question rewritten) and P6 (conditions ignored) **survived**: their controls were already kept by the new clause/word checks, so the two guards were never reached alone. Hashes matched after the run |
| — | `d76237d` | Controls added (tests only); P5 and P6 rerun alone, both caught (console output; not saved to a file) |
| 2 ([output/mutations_run2_d76237d_interrupted.txt](output/mutations_run2_d76237d_interrupted.txt)) | `d76237d` | **Interrupted.** 29 caught and restored (O1–B2). Claude Code then stopped the run (and the watchdog) because the machine was low on memory. That left mutant L1 applied in `basis_fidelity.py`; it was restored with `git checkout` and its SHA-256 matched the pre-run hash. Not counted as a result |
| 3 ([output/mutations_run3_d76237d.txt](output/mutations_run3_d76237d.txt)) | `d76237d` | **58 of 58 caught**, rerun from the start in two halves of 29 with a restarted watchdog (free RAM 1.11 and 1.77 GB, [output/free_ram_before_mutation_halves.txt](output/free_ram_before_mutation_halves.txt)) |

For run 3, every restore was SHA-256 checked. The three guard/pipeline files matched before and after: [output/pre_mutation_hashes_d76237d.txt](output/pre_mutation_hashes_d76237d.txt), [output/post_mutation_hashes_d76237d.txt](output/post_mutation_hashes_d76237d.txt).

### Validation at `d76237d`

`manage.py check`: no issues. `makemigrations --check --dry-run`: no changes ([output/check_and_migrations.txt](output/check_and_migrations.txt)).

The first attempt at the batches stopped before batch A, because free RAM was 1.12 GB, under the 1.2 GB gate. The watchdog and the wait loop were then stopped by Claude Code for low memory. After Chrome was closed, the watchdog was restarted and the batches ran sequentially in the foreground, one per call:

| Batch | Free RAM before | Result |
|---|---|---|
| A | 1.84 GB | 358 OK (347 + the 11 new tests) |
| B | 2.05 GB | 415 OK |
| C | 2.11 GB | 430 OK |
| D | 2.09 GB | 186 OK |

**1,389 tests OK.** The watchdog logged nothing over 1,500 MB ([output/memwatch_b54_batches.log.txt](output/memwatch_b54_batches.log.txt)).

**Commands:** `scripts/batch_one.sh.txt` (the established labels, with a 1.2 GB gate) through `scripts/t.sh.txt` (CI env, memory broker, `--parallel 1`). The mutation runner is `scripts/mutate_b54.py.txt`, which carries `mutate_review.py.txt` → `mutate_bridge.py.txt` → `mutate_ra109_review.py.txt`. Probes and replay: `scripts/probe_b54.py.txt`, `scripts/replay_memos.py.txt` through `scripts/shell.sh.txt`.

## Isolation and limits

- **Isolation:** test databases only. No network, provider or model call; no memo regenerated; no frozen artifact edited; no deployment; no paid-source Pass B. No credentials in this folder (leak-checked).
- **Bounded and lexical:**
  - **Clause start:** recognises only the four linking conjunctions after a comma, plus `;`, `:` and dashes.
  - **Company subject:** a fixed list. A company named by name ("ManyChat states …") is kept as written, a conservative loss.
  - **Wording:** the placing-word list is small. A placing clause with any other word is kept as written. So the rule repairs less than before and never deletes an unrelated clause.
  - **Narrated figures:** never restated.
- **Not proven live:** live behaviour still needs a post-merge sample after review.
