# Review of `8f11844` / `2cb6879` addressed at `064e4ea`, `65a7077` and `c7d4607`: subjects read against the pair; only unstated sides relabelled

Additive evidence. No application code, test expectation, frozen fixture, answer key, grading, recorded memo or earlier evidence folder was changed in this evidence commit. No live model was called and no memo was regenerated.

## The two blockers

1. **Unrelated subjects were rewritten.** At `8f11844`, `_owns_subject` accepted any page or basis word in the judged subject. So "The page-99 figure is overstated [S2, S3]" and "The yearly figure is overstated [S2, S3]" became the pair's neutral clarification on memo 101's pair (pages 10 and 12; one side unstated, one monthly) ([output/reported_cases_on_8f11844.txt](output/reported_cases_on_8f11844.txt)).
2. **Two-rate pairs gained an invented unspecified interval.** For a monthly/daily pair, `_referent` changed "the cumulative figure [C10]" to "the figure stated without an explicit interval [C10]". However, C10 states monthly. `_cumulative_presupposed` did the same to "the cumulative and daily figures" ("the unspecified-interval and daily figures"), so both were fixed.

**Reviewer decision applied:**
- Subjects use the same pair ownership as comparisons.
- Earlier expectations that rewrote unrelated intervals are corrected.
- Unspecified-interval relabelling is restricted to evidence that has an unspecified interval.

## The correction (`zelda_api/basis_fidelity.py`, `064e4ea`)

- **`_pair_placing(word, pair)`:** a subject qualifier must belong to the pair, or be in the existing `_SUBJECT_QUALIFIERS` allowlist.
  - Every basis word in a qualifier must be one of `pair.intervals` (`_pair_basis`). Whatever is left must be the pair's own noun or figure (`_pair_word`).
  - A qualifier with no basis word must be the pair's word or one of `pair.pages` (`_pair_page`).
  - This applies the same rules the `43a1b2d` tail check uses.
- **`_referent` and `_cumulative_presupposed`** now require `pair.unspecified_members`, so a side with no stated interval must exist. A pair with an admitted cumulative side is still never relabelled.
- **Unchanged:** the condition path (`_names_pair`, the measure head).

## Changed outputs from `8f11844`

All exact outputs below are asserted through the full normalisation → time → funding → basis sequence (`replay`). The two `PipelineReview8f11844Tests` also run through the memo writer with a mocked model.

**Now kept** (`REVIEW_8F1_KEPT`):
- the page-99, yearly, slide-7 and run-rate figures;
- "The weekly figure is overstated compared with the monthly figure";
- "The page-99 monthly figure";
- "The 500M messages/week figure";
- "The costs/month figure" (added in `65a7077`);
- "If the figures are monthly, the implied weekly activity is overstated";
- "The monthly figure is accurate [S2], and the daily figure [S3] is overstated."

**Still repaired** (`REVIEW_8F1_REPAIRED`):
- the page-10, slide-12 monthly, cumulative and "500M messages/month" figures;
- "the implied monthly activity";
- in "…accurate [S2], and the larger figure [S3] is overstated.", only the second clause is replaced.

**Corrected expectations (reviewer decision).** Three earlier controls expected a subject list containing "daily" to be rewritten. "Daily" is not one of memo 101's pair's intervals, so all three are now expected to be kept:
- "The cumulative, monthly, and daily figures are overstated [S2, S3]." (`Review8d7f8dc`, `ReviewA6dcddf`, `Review72418e2`, `Review71ece83`)
- "The cumulative, monthly, and daily figures are overstated [S2, S3], but the definitions remain unclear." (`REVIEW_A6D`)
- "The reported, monthly, and daily figures are overstated [S2, S3], but the definitions remain unclear." (`REVIEW_724`)

Each of these had also guarded the serial-list split. Beside each I added a list made only of the pair's own words, which must still be repaired as one clause:
- "…cumulative, monthly, and page-10 figures…"
- the page-12 variant
- "reported, monthly, and cumulative"

**Two-rate pairs** (`TWO_RATE_ITEMS`: C10 "4M messages/month" on page 3, C11 "4M messages/day" on page 4). All four cumulative referent and presupposed sentences are now kept. As a positive control, the writer still repairs the pair's own judgment: "How the monthly figure relates to the daily figure needs clarification before either is relied on [C11] [C10]."

**Unchanged repairs:**
- memo 98's pair (one unstated side) is still relabelled;
- an admitted cumulative side beside an unstated one is never relabelled (pinned in `c7d4607`);
- memo 100's and memo 101's graded repairs are reproduced.

## Commits and what ran at each

| Commit | What | Checks |
|---|---|---|
| `8f11844` (reviewed) | — | **Red, two runs**, each with the guard swapped to the `8f11844` working-tree bytes (sha256 `85d77b32…`) and then restored and hash-checked. <br>**First tests** (before `65a7077`/`c7d4607`), 22 selected tests: **29 assertion failures, 0 errors** ([output/red_run_first_tests_on_8f11844.txt](output/red_run_first_tests_on_8f11844.txt)). <br>**Final tests** (`c7d4607`), whole `tests_output_fidelity` module, 199 tests: **30 assertion failures, 0 errors** ([output/red_run_final_tests_on_8f11844.txt](output/red_run_final_tests_on_8f11844.txt)). The 30th is the costs/month case. Both runs include both memo-writer tests. The `c7d4607` test passes on `8f11844`, as expected, because it pins behaviour `8f11844` already had. |
| **`064e4ea`** (final application commit) | `_pair_placing`; unstated-only relabels; tests | Modules one at a time: **198 + 77 + 67 = 342 OK** ([output/modules_064e4ea.txt](output/modules_064e4ea.txt)). <br>`check` and `makemigrations --check --dry-run` exit 0 ([output/check_and_migrations_064e4ea.txt](output/check_and_migrations_064e4ea.txt)). <br>The replay, probes and first exact table ran here. |
| `65a7077` (test only) | "The costs/month figure" kept (pins S3) | Covered by the `c7d4607` runs. |
| **`c7d4607`** (final head; test only) | An admitted cumulative side beside an unstated one (pins T11) | Modules: **199 + 77 + 67 = 343 OK** ([output/modules_c7d4607.txt](output/modules_c7d4607.txt)). <br>`check` and `makemigrations --check --dry-run` exit 0, with `PYTHONDONTWRITEBYTECODE=1`; the tree was clean afterwards ([output/check_and_migrations_c7d4607.txt](output/check_and_migrations_c7d4607.txt)). <br>The final exact table and all 127 mutations ran here. The application code is byte-identical to `064e4ea` (sha256 `ccfe74b7…`). |

## Replay of memos 96–101 and the 75 carried probes (at `064e4ea`)

- **Replay:** [output/replay_memos_96_to_101_064e4ea.json](output/replay_memos_96_to_101_064e4ea.json).
- **Probes:** [output/carried_probes_75_064e4ea.json](output/carried_probes_75_064e4ea.json).
- **Against `8f11844`:** both are identical in every field except `head` to the outputs committed in `2cb6879` (`8f11844`'s guard is byte-identical to `43a1b2d`'s) ([output/compare_with_8f11844.txt](output/compare_with_8f11844.txt)).
- **No recorded memo output changed.** The application is unchanged after `064e4ea`, so this holds at `c7d4607`.

## Exact outputs per version

[output/scripts/exact.py.txt](output/scripts/exact.py.txt) runs every round's exact cases through the full sequence with each version's guard.

- **At `c7d4607`:** **110/110** ([output/exact_and_boundaries_c7d4607.txt](output/exact_and_boundaries_c7d4607.txt)).
  - Earlier versions: `0664563` 29, `9b28e14` 32, `8d7f8dc` 35, `a6dcddf` 65, `72418e2` 74, `71ece83` 86, `8f11844` 97.
- **At `064e4ea`:** 109/109 ([output/exact_and_boundaries_064e4ea.txt](output/exact_and_boundaries_064e4ea.txt)), before the costs/month case existed.
- **Differences between the two runs** ([output/exact_diff_064e4ea_vs_c7d4607.txt](output/exact_diff_064e4ea_vs_c7d4607.txt)):
  - one new row, "The costs/month figure is overstated [S2, S3].", which is exact only at `c7d4607`;
  - the totals.
  - Nothing else differs. The raw diff also shows the boundary-probe lines because the `064e4ea` file was saved with the clarification sentence shortened to "CLARIFY". With that substitution undone, the probe outputs are identical.
- **Boundary probes** (recorded, not asserted by tests):

| Probe | `8f11844` | `c7d4607` |
|---|---|---|
| "The page 99 figure" (spaced) | kept | kept |
| "The figure on page 99" | kept | kept |
| "The annual figure" | kept | kept |
| "The quarterly figure" | kept | kept |
| "The per-day figure" | kept | kept |
| "The monthly-basis figure" | repaired | **kept** (changed) |
| "The monthly and daily figures" | repaired | **kept** (changed) |
| "The page-12 figure … compared with the page-10 count" | repaired | repaired |

## Mutations

[output/scripts/mutate_x.py.txt](output/scripts/mutate_x.py.txt) applies one mutant at a time to `basis_fidelity.py`. It runs the three modules (343 tests), restores the original bytes and checks them with SHA-256 before the next mutant.

A mutant counts as caught only by assertion failures (`failures=N`, N > 0) in a run of all 343 tests with `restored=True`. Errors, timeouts, memory refusals and skipped runs do not count.

### Final-head pass: all 127 at `c7d4607`

- **Result:** **127 of 127 caught, each by assertion failures, with no errors.** None survived, none were crash-only, and every chunk's restore was confirmed ([output/mutations_all127_c7d4607.txt](output/mutations_all127_c7d4607.txt); checked by [output/scripts/combine.py.txt](output/scripts/combine.py.txt) → [output/mutations_all127_summary_c7d4607.txt](output/mutations_all127_summary_c7d4607.txt)).
- **How it ran:** 22 foreground chunks (c01–c22, [output/scripts/chunks.txt](output/scripts/chunks.txt)).
  - **c01–c16** (96 mutants) ran first.
  - The pass then paused (see *Running conditions*).
  - **c17–c22** (31 mutants: K6–K14, L1–L12, S1–S10) ran in a later session.
  - Before resuming I confirmed:
    - HEAD was `c7d4607`;
    - the tree was clean and all four guarded files matched their pre-run hashes;
    - no runner was left;
    - `mutate_x.py` had not been modified since before c01 started, so both parts use the same HEAD and the same mutation definitions.
- **Restores:** the [pre](output/pre_mutation_hashes_c7d4607.txt) and [post](output/post_mutation_hashes_c7d4607.txt) hashes are identical.

**This round's mutants:**

| ID | Mutation | Failures |
|---|---|---|
| S1 | any basis word in the subject is the pair's (the `8f11844` behaviour) | 20 |
| S2 | any page in the subject is the pair's (the `8f11844` behaviour) | 5 |
| S3 | the rest of a word around its basis is not read ("The costs/month figure") | 1 |
| S4 | positive: no word with a basis and more is the pair's ("The 500M messages/month figure") | 1 |
| S5 | positive: no page in the subject is the pair's | 16 |
| S6 | positive: no basis word in the subject is the pair's | 142 |
| S7 | "the cumulative figure" relabelled for two stated rates (the `8f11844` behaviour) | 3 |
| S8 | "the cumulative and daily …" presupposition relabelled for two stated rates | 3 |
| S9 | positive: "the cumulative figure" is never relabelled (memo 98's pair) | 5 |
| S10 | positive: "the cumulative and monthly …" is never relabelled (memo 101, OF-906) | 18 |
| T11 | an admitted cumulative side is neutralised too (re-anchored) | 1 |
| Z6 | the subject's qualifiers are not read (re-anchored) | 39 |
| N1 | a condition overrides foreign qualifiers (re-anchored) | 10 |

- **Re-anchored** (same meaning, [output/scripts/patch_mut2.py.txt](output/scripts/patch_mut2.py.txt)): T11, Z6 and N1, whose anchor lines moved.
- **Retired:** Z19, which became the same mutation as S5.
- **Carried:** every other mutant, with unchanged anchors.

### Earlier discovery runs (at `65a7077`; not counted in the 127)

- **d1 and d2** ran S1–S10 plus the re-anchored T11 and Z6 against 342 tests, before the final head existed ([output/mutations_discovery_d1_65a7077.txt](output/mutations_discovery_d1_65a7077.txt), [output/mutations_discovery_d2_65a7077.txt](output/mutations_discovery_d2_65a7077.txt)).
- **T11 survived there.** The new unstated-side check masked it, because every test pair that admits "cumulative" had no unstated side.
- The `c7d4607` test (C7 "3M messages to date" on page 7, C8 "3M messages" on page 8) was added for it. T11 is caught in the final-head pass.

## Running conditions

- **Free RAM before each chunk** ([output/free_ram_before_mutation_chunks.txt](output/free_ram_before_mutation_chunks.txt)): 0.89–1.51 GB in the first session; 1.70–2.11 GB for c17–c22.
- **Refusals by the 0.9 GB floor:**
  - c06 was refused at 0.89 GB and later ran at 1.29 GB.
  - c17 was refused at 0.83 GB.
  - A refusal runs no test and is not counted; each chunk counted is its successful run.
- **The pause:** after the c17 refusal, Claude Code stopped my background wait-for-memory loop under memory pressure, and it was not restarted. The pass resumed in a later session, at 1.92 GB free, without lowering the floor or starting a persistent wait.
- **Chunk size:** chunks were 6 mutants (c22: 1), each run in the foreground and none past the tool timeout.
- **First exact-table rerun (my error):** the first rerun at `c7d4607` used `manage.py shell <` without the CI environment and failed at settings import before producing any table. It was rerun with [output/scripts/shell.sh.txt](output/scripts/shell.sh.txt), and only that run is recorded.

## Remaining limitations (not fixed here)

- **Wording without a test.** These are boundary probes only, with no test asserting them:
  - "The monthly-basis figure" and "The monthly and daily figures" are now kept.
  - "The figure on page 99" and the spaced "The page 99 figure" were already kept.
- **Fixed word lists.** The subject qualifier allowlist (`_SUBJECT_QUALIFIERS`), the basis words and the tail allowlist are fixed lists. Wording outside them keeps the sentence unrepaired. Examples:
  - "annual" or "quarterly";
  - "the count on page 10";
  - "the monthly run-rate".
- **"slide N" is treated as page N.**
- **The condition path still reads any basis word in the condition.** Only the subject's qualifiers are pair-checked there.
- **Carried from `8f11844` and earlier:**
  - a modifier needs a determiner;
  - lead-ins before a referent are not read;
  - the remaining limitations of earlier rounds (see the earlier READMEs).
- **Not live.** Live behaviour requires a later reviewed live sample.

**Status:** branch `fix/basis-structural-of903-906`, unmerged and not deployed. RA-109 live acceptance, RA-108, RA-114 and overall hardening remain open, pending independent review and the later reviewed live sample.
