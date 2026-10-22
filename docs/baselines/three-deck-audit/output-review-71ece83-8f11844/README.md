# Review of `71ece83` / `7490245` addressed at `43a1b2d` and `8f11844`: comparisons with pages and intervals that are not the pair's

**This folder adds correction evidence and changes nothing else.** It edits nothing in `output-review-72418e2-71ece83/` or any earlier evidence, fixture, answer key, grade, recorded memo or raw response. No model was called; recorded memos were replayed, not regenerated. **This is correction evidence only. RA-109 live acceptance and overall hardening stay open, pending independent re-review and a later reviewed live sample.**

## The blocker

`_replaceable` (the tail allowlist added at `71ece83`) accepted **any** `page-N` and **any** basis word after the judgment, without checking them against the pair. On memo 101's payload (pages 10 and 12; one side with no stated interval, one monthly), both reported cases became the neutral clarification, so the comparison was deleted:

- "The monthly figure is overstated compared with the page-99 count [S2, S3]." (general rule)
- "These figures are overstated compared with the yearly count [S2, S3]." (referent rule)

Both also fail at `72418e2`, so this is an incomplete fix, not a new regression. [output/reported_cases_on_71ece83.txt](output/reported_cases_on_71ece83.txt) ([script](output/scripts/repro.py.txt)) reproduces them and their variants at `71ece83`, through the normalisation → time → funding → basis sequence. In that file the `pair` line prints empty sets because `Pair.pages` and `Pair.intervals` did not exist yet.

## The correction (`zelda_api/basis_fidelity.py`, `43a1b2d`)

`Pair` now records two more fields, both filled in `basis_facts`:
- **`pages`:** the pages its members are on.
- **`intervals`:** its sides' bases. A rated side gives its interval ("month"). A cumulative side, and a side with no stated interval, give "cumulative", because the memos call the unstated figure "the cumulative figure" and `_referent` already rewrites it that way (memo 98, UB-604).

In `_replaceable`:
- **`_pair_page`:** a `page-N` or `slide-N` after the judgment must be one of `pair.pages`. "page 10" and "slide 12" are joined to their hyphenated forms first.
- **`_pair_basis`:** a basis word after the judgment must be one of `pair.intervals`. That covers "monthly", "/month" and "per month" for a monthly side, and "cumulative" only for a pair that has a cumulative or unstated side. "interval" names no other figure and is accepted. Any other basis wording (for example "run-rate") is no longer accepted, so the clause is kept.

This is still an allowlist, read the same way by the general and the referent rule. Subjects are not changed (see the limitations).

## Changed outputs from `71ece83`

These come from [output/exact_and_boundaries.txt](output/exact_and_boundaries.txt) ([script](output/scripts/exact.py.txt)), on memo 101's payload after `PAIR_LEAD`.

**Now kept** (rewritten to the clarification at `71ece83`; `Review71ece83Tests`, exact outputs):

| Input | Rule at `71ece83` |
|---|---|
| The monthly figure is overstated compared with the page-99 count [S2, S3]. | general |
| The monthly figure is overstated compared with the slide-7 figure [S2, S3]. | general |
| The monthly figure is overstated compared with the weekly figure [S2, S3]. | general |
| The monthly figure is overstated compared with the daily count [S2, S3]. | general |
| The monthly figure is overstated compared with the run-rate [S2, S3]. | general |
| These figures are overstated compared with the yearly count [S2, S3]. | referent |
| One or both figures may be overstated compared with the yearly count [S2, S3]. | referent |
| One or both figures may misrepresent the page-99 count [S2, S3]. | referent |
| These figures may overstate the weekly activity [S2, S3]. | referent |

"… compared with the page 99 count …" (spaced) was already kept at `71ece83` and still is; it is a control.

**Now repaired** (kept at `71ece83`, because the spaced or "per" form was not read):
- "The monthly figure is overstated compared with the page 10 count [S2, S3]."
- "The page-10 figure is overstated compared with the per month figure [S2, S3]."

**Still repaired** (exact outputs asserted):
- "… compared with the page-10 count", "… the slide-12 figure", "… the monthly count", "… the cumulative figure".
- "One or both figures may overstate the page-12 count".
- "These figures may overstate the monthly activity".
- "… relative to its stated interval".
- Memo 100's "One or both figures may misrepresent the scale of actual activity".
- Memo 98's conditional, and every earlier round's kept and repaired groups (`test_earlier_rounds_are_unchanged`).

**Per pair** (`test_pages_and_intervals_are_each_pairs_own`, three pairs on pages 5/6, 7/9 and 10/12):
- Another pair's page or interval keeps the sentence: "The daily bot figure [C6] is overstated compared with the page-12 bot count [C5]", "… the monthly bot count", "The weekly figure [C9] … compared with the daily figure [C7]" and "… the page-10 figure [C7]".
- The pair's own are repaired: "… the page-5 bot count [C5]", "… the cumulative figure [C7]" and "… the page-7 figure [C7]".

**A pair of two stated rates** (`test_a_pair_of_two_stated_rates_has_no_cumulative_side`, monthly on page 3 and daily on page 4; [output/two_rate_pair_8f11844.txt](output/two_rate_pair_8f11844.txt)):
- "… compared with the cumulative activity [C10]" is kept.
- "… compared with the monthly activity [C10]" is repaired.

**Boundary probes that changed** (not tests):

| Input | `71ece83` | `43a1b2d` |
|---|---|---|
| … compared with the monthly run-rate [S2, S3]. | repaired | kept |
| … compared with the slide 12 figure [S2, S3]. | kept | repaired |

**Exact outputs:** 91 of 91 at `43a1b2d`, against 80 at `71ece83`, 68 at `72418e2`, 59 at `a6dcddf`, 29 at `8d7f8dc`, 27 at `9b28e14` and 24 at `0664563`.

## Commits and what ran at each

| Commit | What | Checks |
|---|---|---|
| `71ece83` (reviewed) | — | **Red.** The final tests (at `8f11844`) were run against the `71ece83` bytes of `basis_fidelity.py`, then the guard was restored and hash-checked: **17 assertion failures, 0 errors**, across all six new tests, including the memo writer with a mocked model (`PipelineReview71ece83Tests`, `_generate_memo`) ([output/red_run_on_71ece83.txt](output/red_run_on_71ece83.txt)). An earlier red run, before the "interval" control and the two-rate test existed, gave 16 failures over 5 tests; it is superseded. |
| **`43a1b2d`** (final application commit) | `Pair.pages`, `Pair.intervals`, `_pair_page`, `_pair_basis`; tests | Modules one at a time: **189 + 77 + 67 = 333 OK** ([output/modules_43a1b2d.txt](output/modules_43a1b2d.txt)). <br>`check` and `makemigrations --check --dry-run` exit 0, run with `PYTHONDONTWRITEBYTECODE=1`; the tree was clean afterwards ([output/check_and_migrations_43a1b2d.txt](output/check_and_migrations_43a1b2d.txt)). <br>The replay, probes and exact outputs ran here. |
| **`8f11844`** (final head; test only) | The two-rate-pair control (pins L4) | Modules: **190 + 77 + 67 = 334 OK** ([output/modules_8f11844.txt](output/modules_8f11844.txt)). <br>All 118 mutations ran here. The application code is byte-identical to `43a1b2d`. |

## Replay of memos 96–101 and the 75 carried probes (at `43a1b2d`)

- **Replay:** [output/replay_memos_96_to_101_43a1b2d.json](output/replay_memos_96_to_101_43a1b2d.json).
- **Probes:** [output/carried_probes_75_43a1b2d.json](output/carried_probes_75_43a1b2d.json).
- **Against `71ece83`:** both are identical to `71ece83`'s committed outputs (in `7490245`) in every field except `head` ([output/compare_with_71ece83.txt](output/compare_with_71ece83.txt)). Memo 98's and memo 100's repairs are reproduced, and memo 101 keeps its four graded repairs.

## Mutations: all 118 at `8f11844`

[output/scripts/mutate_x.py.txt](output/scripts/mutate_x.py.txt) applies one mutant at a time to `basis_fidelity.py` and runs the three modules (334 tests). It then restores the original bytes and checks them with SHA-256 before the next mutant. A mutant counts as caught only by assertion failures.

**All 118 ran against `8f11844`, in chunks m01–m02 and c01–c18** ([output/mutations_all118_8f11844.txt](output/mutations_all118_8f11844.txt)). **118 were caught, each by assertion failures. None survived, none were crash-only and no run had errors.**

| ID | Mutation | Failures |
|---|---|---|
| L1 | any basis word is the pair's (the `71ece83` behaviour) | 9 |
| L2 | any rate is the pair's | 8 |
| L3 | any page or slide is the pair's (the `71ece83` behaviour) | 7 |
| L4 | "cumulative" is always the pair's | 1 |
| L5 | positive: no page is the pair's | 8 |
| L6 | positive: no basis word is the pair's | 9 |
| L7 | positive: "page 10" is not joined | 1 |
| L8 | positive: "per month" is not joined | 1 |
| L9 | positive: `Pair.pages` is never filled | 8 |
| L10 | positive: the unstated side is not "cumulative" (memo 101's "compared with the cumulative figure") | 2 |
| L11 | positive: "interval" is not the pair's | 1 |
| L12 | positive: adjective rates ("monthly") are not read | 4 |
| K11 | positive: the pair's own words are not object vocabulary (re-anchored) | 3 |
| K12 | positive: a page or slide is not object vocabulary (re-anchored) | 8 |

- **Re-anchored** (same meaning): K11 and K12, to the new tail predicates.
- **Retired:** N9, which survived at `71ece83` and was disclosed there. The comma check it guarded no longer exists.
- **Carried:** every other mutant, with unchanged anchors. All were caught.
- **Discovery at `43a1b2d`:** L1–L7 ran once before the full pass ([output/mutations_discovery_L1-L7_43a1b2d.txt](output/mutations_discovery_L1-L7_43a1b2d.txt)). **L4 survived there**: every fixture pair had a cumulative or unstated side. The two-rate control in `8f11844` was added for it, and L4 is caught in the full pass. These discovery runs are not counted in the 118.
- **Discarded run (my error):** the first attempt at that discovery chunk ran no tests. The runner calls `t.sh` from its own directory, and I had not copied it into this round's scratch folder, so every mutant was reported SURVIVED with no test counts ([output/mutations_DISCARDED_no_tests_ran_43a1b2d.txt](output/mutations_DISCARDED_no_tests_ran_43a1b2d.txt)). Restores were still verified. The runner now reports `NO-RUN` when no test ran ([output/scripts/fix_norun.py.txt](output/scripts/fix_norun.py.txt)).
- **Restores:** the [pre](output/pre_mutation_hashes_8f11844.txt) and [post](output/post_mutation_hashes_8f11844.txt) hashes are identical. The working tree was clean afterwards.

## Running conditions

- **Memory:** free RAM before each chunk ranged from 1.31 to 2.25 GB ([output/free_ram_before_mutation_chunks.txt](output/free_ram_before_mutation_chunks.txt)). The chunk runner's 0.9 GB floor refused nothing.
- **Chunk size:** m02 held 7 mutants and took 9 min 6 s, so the later chunks held 6. Every chunk ran in the foreground, and none passed the tool timeout.
- **One stuck command (my error):** an inline `python -` heredoc meant for a one-line test edit hung on the wrong interpreter and was stopped. It wrote nothing (`git status` showed only the intended change), and the edit was made with the editor.

## Remaining limitations (not fixed here)

- **Subjects still accept any page or basis word.** "The page-99 figure is overstated [S2, S3]", "The yearly figure is overstated [S2, S3]" and "The weekly figure is overstated compared with the monthly figure [S2, S3]" are still repaired (boundary probes).
  - The tail and the subject now apply different standards. That is deliberate in this round: accepted controls repair subjects that list other intervals ("The cumulative, monthly, and daily figures are overstated [S2, S3]", in `REVIEW_A6D` and `REVIEW_724`).
  - Applying the pair-specific rule to subjects would reverse those accepted outputs, so it is left for the reviewer to decide.
- **A pre-existing relabel for two-rate pairs.** For a monthly/daily pair, "compared with the cumulative figure [C10]" is relabelled "the figure stated without an explicit interval", but that pair has no such figure ([output/two_rate_pair_8f11844.txt](output/two_rate_pair_8f11844.txt)). This is `_referent`'s rewrite (`basis_cumulative_referent`), which this round does not change. It was found while writing the L4 control and is not fixed here.
- **Fixed vocabularies:** the tail allowlist is still a fixed list, and text outside it keeps the sentence. Examples: "the count on page 10", "the monthly run-rate", "overstated by a factor of 30". "slide N" is treated as page N.
- **Carried from `71ece83` and earlier:**
  - a modifier needs a determiner;
  - lead-ins before a referent are not read;
  - the remaining limitations of earlier rounds.

  See the earlier READMEs.
- **Not live:** live behaviour requires a later reviewed live sample.

**Status:** branch `fix/basis-structural-of903-906`, unmerged and not deployed. RA-109 live acceptance, RA-108, RA-114 and overall hardening remain open.
