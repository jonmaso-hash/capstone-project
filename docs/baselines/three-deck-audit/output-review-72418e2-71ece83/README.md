# Review of `72418e2` / `94c6ecc` addressed at `71ece83`: participle compound subjects and attributions after the judgment

**This folder adds correction evidence and changes nothing else.** It edits nothing in `output-review-a6dcddf-72418e2/` or any earlier evidence, fixture, answer key, grade, recorded memo or raw response. No model was called; recorded memos were replayed, not regenerated. **This is correction evidence only. RA-109 live acceptance and overall hardening stay open, pending independent re-review and a later reviewed live sample.**

## The two blockers

Both reproduce at `a6dcddf` as well as `72418e2`, so both are incomplete fixes, not regressions. Every case follows memo 101's `PAIR_LEAD` and runs on memo 101's payload through the time → funding → basis guards.

1. **Compound subjects with "reported", "stated" or "claimed" were still garbled.** For example, "The reported monthly figure [S2], and the larger figure [S3] are overstated." had its second half replaced with the clarification. The compound-subject check and the serial-list guard used `_ITEM_VERB`, which treats any "-ed" word as a verb.
2. **Attributions after the judgment were deleted unless a comma introduced them.** "The monthly figure is overstated (in management's view) [S2, S3]." and "… overstated according to management …" became the neutral clarification. `_owns_subject` only looked for a comma after the judgment; it never established whether the trailing text could be removed. The referent rule had the same gap: "These figures may be inflated (in management's view)" and "One or both figures may be overstated according to management" lost their attributions too.

Found while comparing versions: `72418e2` had also broken "The reported, monthly, and daily figures are overstated [S2, S3], but …", which `a6dcddf` repaired correctly. The cause was the same "-ed" verb reading in the list guard, and it is fixed by the same change.

## The correction (`zelda_api/basis_fidelity.py`, `958d9ad` and `71ece83`)

**A modifier is not a verb** (`_has_verb`, which replaces `_ITEM_VERB.search` in the list guard and the compound-subject check). A participle or judgment word is read as a modifier, not a verb, when only placing words (`_SUBJECT_QUALIFIERS`, basis words) stand between it and its determiner:
- "the reported", "the company's reported", "the inflated monthly figure" are modifiers;
- "Management reported the monthly figure [S2], and the larger figure [S3] is overstated." still has a verb ("reported" with no determiner), so it is two clauses, and the second (the pair's) is repaired.

**Trailing text must be replaceable** (`_replaceable`, read in `_judged_segments` for both the general and the referent rule; it replaces the comma-only check in `_owns_subject`). This is an allowlist. From the judgment to the end of its clause, the clause may hold only:
- coordinated judgments and their hedges ("overstated and possibly misleading");
- an object or comparison naming only the pair's measure or figures: determiners, measure and figure heads, basis words, the pair's own words, placing qualifiers, page/slide places, and the connectives of/as/than/compared/with/to/relative/against/versus. Examples: memo 100's "misrepresent the scale of actual activity" and the earlier frozen forms "overstates the page-10 count", "overstated compared with the bare bot count" and "overstated as a monthly figure";
- citations and closing punctuation.

Anything else is text the clarification would delete, so the chain is not the pair's and the sentence is kept. Examples: "(in management's view)", "according to management", "in management's view", "by management", "compared with the hiring plan", "the scale of hiring". Continuation fragments (after a dash or linking comma) are not read this way: they already have to fullmatch the fixed `_CONTINUATION` grammar.

**`958d9ad` was incomplete.** Its first allowlist accepted no comparisons. The three-module run at `958d9ad` failed four frozen earlier controls (`BasisGuardTests`, `BasisContainmentTests`, `PipelineContainmentTests`, `Review1801ec5Tests`; [output/modules_958d9ad.txt](output/modules_958d9ad.txt)). `71ece83` adds the comparison vocabulary and page/slide places, plus controls that a comparison with anything else keeps the clause.

## Changed outputs from `72418e2`

These come from [output/exact_and_boundaries.txt](output/exact_and_boundaries.txt) ([script](output/scripts/exact.py.txt)).

**Cases this round tests** (`Review72418e2Tests`, exact outputs):

| Input (after `PAIR_LEAD`) | `72418e2` | `71ece83` |
|---|---|---|
| The reported monthly figure [S2], and the larger figure [S3] are overstated. | second half replaced (garbled) | kept |
| The stated monthly figure [S2], and the larger figure [S3] are overstated. | the same | kept |
| The claimed figure [S2], and the larger figure [S3] are overstated. | the same | kept |
| The company's reported monthly figure [S2], and the larger figure [S3] are overstated. | the same | kept |
| The monthly figure is overstated (in management's view) [S2, S3]. | rewritten | kept |
| The monthly figure is overstated according to management [S2, S3]. | rewritten | kept |
| The monthly figure is overstated in management's view [S2, S3]. | rewritten | kept |
| The monthly figure is overstated [S2, S3] (in management's view). | rewritten | kept |
| These figures may be inflated (in management's view) [S2, S3]. | rewritten (referent rule) | kept |
| One or both figures may be overstated according to management [S2, S3]. | rewritten (referent rule) | kept |
| One or both figures may misrepresent the scale of hiring [S2, S3]. | rewritten (referent rule) | kept |
| The monthly figure is overstated compared with the hiring plan [S2, S3]. | rewritten | kept |
| The reported, monthly, and daily figures are overstated [S2, S3], but the definitions remain unclear. | garbled (split inside the list) | the list clause repaired, ", but …" kept (as at `a6dcddf`) |

**Repairs that still happen** (exact outputs asserted):
- "Management reported the monthly figure [S2], and the larger figure [S3] is overstated." and "The reported figure is monthly [S2], and …": the second clause is repaired and the first kept.
- "The monthly figure is overstated and possibly misleading [S2, S3]." and "One or both figures may be overstated or misleading [S2, S3]." are repaired.
- "One or both figures may misrepresent the scale of actual activity [S2, S3]." (memo 100's form) is repaired.
- "The monthly figure is overstated compared with the cumulative figure [S2, S3]." is repaired.
- Memo 98's conditional and every earlier round's kept and repaired groups are unchanged.

**Boundary probes that changed** (not tests):

| Input | `72418e2` | `71ece83` |
|---|---|---|
| The monthly figure is overstated by management [S2, S3]. | rewritten | kept |
| The inflated monthly figure [S2], and the larger figure [S3] are overstated. | second half replaced (garbled) | kept |

Unchanged probes include "…, as compared with the cumulative figure" (only the cumulative referent relabelled, as before), "… relative to the larger figure" (repaired) and "Without clarification, one or both figures may be overstated" (kept).

**Exact outputs:** 73 of 73 at `71ece83`, against 60 at `72418e2`, 51 at `a6dcddf`, 21 at `8d7f8dc`, 19 at `9b28e14` and 18 at `0664563`.

## Commits and what ran at each

| Commit | What | Checks |
|---|---|---|
| `72418e2` (reviewed) | — | **Red.** The final tests (at `71ece83`) were run against `git show 72418e2:zelda_api/basis_fidelity.py`, with the guard then restored and hash-checked: **14 assertion failures, 0 errors** ([output/red_run_on_72418e2.txt](output/red_run_on_72418e2.txt)). They cover both blockers, the list regression, the object controls and the memo writer with a mocked model (`PipelineReview72418e2Tests`, `_generate_memo`). Before committing, a first red run of the then-current tests gave 12 failures; it is superseded. |
| `958d9ad` | `_has_verb`, `_replaceable`; the referent rule reads ownership; tests | **Not green:** 184 tests in `tests_output_fidelity` with 4 failures (frozen comparison forms); 77 + 67 OK ([output/modules_958d9ad.txt](output/modules_958d9ad.txt)). |
| **`71ece83`** (final application commit and final head) | Comparison vocabulary and page/slide places; comparison controls | Modules one at a time: **184 + 77 + 67 = 328 OK** ([output/modules_71ece83.txt](output/modules_71ece83.txt)). <br>`check` and `makemigrations --check --dry-run` exit 0 ([output/check_and_migrations_71ece83.txt](output/check_and_migrations_71ece83.txt)). <br>The replay, probes, exact outputs and all 107 mutations ran here. |

## Replay of memos 96–101 and the 75 carried probes (at `71ece83`)

- **Replay** ([output/replay_memos_96_to_101_71ece83.json](output/replay_memos_96_to_101_71ece83.json)) and **probes** ([output/carried_probes_75_71ece83.json](output/carried_probes_75_71ece83.json)) were run with the working tree clean.
- **Against `72418e2`:** both are **identical to `72418e2`'s committed outputs (in `94c6ecc`) in every field except `head`** ([output/compare_with_72418e2.txt](output/compare_with_72418e2.txt)). Memo 98's and memo 100's repairs are reproduced, and memo 101 differs from the base replay in exactly its four graded repairs.
- **Disclosed intermediate result:** a working-tree replay before `958d9ad` was committed lost memo 100's `open_concerns` referent repair ("one or both figures may misrepresent the scale of actual activity"), because the first allowlist accepted no object. The object vocabulary was added before the commit; the committed versions reproduce the repair.

## Mutations: all 107 at `71ece83`

[output/scripts/mutate_x.py.txt](output/scripts/mutate_x.py.txt) applies one mutant at a time to `basis_fidelity.py` and runs the three modules (328 tests). It then restores the original bytes and checks them with SHA-256 before the next mutant. A mutant counts as caught only by assertion failures.

**All 107 ran against `71ece83`, in chunks f01–f14** ([output/mutations_all107_71ece83.txt](output/mutations_all107_71ece83.txt)). **106 were caught and 1 survived (N9); 0 were crash-only and no run had errors.**

| ID | Mutation | Failures |
|---|---|---|
| K1 | every "-ed" word is a verb (the `72418e2` behaviour) | 6 |
| K2 | placing words between the determiner and the participle are not skipped | 1 |
| K3 | positive: no word is ever a verb | 23 |
| K4 | the list guard reads "-ed" modifiers as verbs | 1 |
| K5 | the compound-subject check reads "-ed" modifiers as verbs | 5 |
| K6 | the text after the judgment is not read | 14 |
| K7 | the referent rule ignores the tail | 4 |
| K8 | positive: continuation fragments are read as tails too | 13 |
| K9 | positive: no object after the judgment is replaceable (memo 100) | 14 |
| K10 | any object is replaceable | 14 |
| K11 | positive: the pair's own words are not object vocabulary | 2 |
| K12 | positive: a page or slide is not object vocabulary | 1 |
| K13 | positive: coordinated judgments are not replaceable | 2 |
| K14 | positive: comparison connectives are not object vocabulary | 4 |

- **N9 survived** (it was caught with 2 failures at `72418e2`). It reads ownership over the joined chain, separators included, instead of per segment. It existed to stop the separator in "…, and possibly inflated" from tripping the old comma-aside check in `_owns_subject`; `71ece83` removes that check, because `_owns_subject` no longer reads text after the judgment. The only remaining difference found is a verbless fragment after a dash ("The monthly figure — possibly inflated [S2, S3].": kept at `71ece83`, repaired by N9), where both outputs are defensible. **No control was added to pin it, and N9 is reported as a survivor, not as caught;** it is retired from later passes for that reason.
- **Re-anchored** (same meaning): Y2, Z4, N2 and N10, to `_has_verb` and the tail-aware ownership. All were caught.
- **Retired:** N3, whose comma check is replaced by `_replaceable` (K6 removes that read).
- **Carried:** every other mutant, with unchanged anchors. All were caught.
- **Discovery:** K1–K14 also ran once before the full pass (all caught; [output/mutations_discovery_K_71ece83.txt](output/mutations_discovery_K_71ece83.txt)). These runs are not counted twice.
- **Restores:** the [pre](output/pre_mutation_hashes_71ece83.txt) and [post](output/post_mutation_hashes_71ece83.txt) hashes are identical. No orphaned runner was left, and the working tree was clean afterwards.

## Running conditions (disclosed)

- **Watchdog:** ran from 2026-10-20 19:00:24 to 21:53:45 and killed nothing ([output/memwatch.log.txt](output/memwatch.log.txt)).
- **Memory:** free RAM before chunks ranged from 1.13 to 1.73 GB ([output/free_ram_before_mutation_chunks.txt](output/free_ram_before_mutation_chunks.txt)). No chunk was refused.
- **Chunk past the tool timeout:** f01 held 20 mutants on an estimate of about 15 s each, but each takes about 70 s of wall time, mostly Django startup. It exceeded the 600 s tool timeout and was moved to the background, where it completed with verified restores. Nothing else ran until it finished. Later chunks held 7 mutants.
- **Bytecode written by the Django check (my error):** `manage.py check` and `makemigrations` ran without `PYTHONDONTWRITEBYTECODE`. They rewrote tracked `__pycache__/*.pyc` files and created untracked ones. Once f01 finished, the tracked files were restored with `git checkout` and the untracked `.pyc` files removed. The tree was clean before these runs; afterwards there were no non-`.pyc` changes and the four guarded files' hashes still matched. The mutation runs set `PYTHONDONTWRITEBYTECODE=1`.

## Remaining limitations (not fixed here)

- **Fixed vocabularies:** the modifier rule, the tail allowlist and its object vocabulary are fixed lists. Text outside them keeps the sentence unrepaired, which is the conservative direction: "overstated by a factor of 30", "overstated relative to last year's plan".
- **Modifiers need a determiner:** a participle with no determiner ("Reported figures [S2], and …") still counts as a verb, so that sentence can still be split.
- **Lead-ins before a referent:** the referent rule still does not read words before the referent; "Without clarification, one or both figures may be overstated" is kept for other reasons.
- **Carried from `72418e2` and earlier:**
  - lead-ins and asides keep the sentence;
  - other verbs ("need") count as verbless;
  - compound subjects are kept, not repaired;
  - a bare "The claim" counts as the pair's;
  - topics come from evidence categories;
  - the rest of the earlier rounds' limitations.

  See the earlier READMEs.
- **Not live:** live behaviour requires a later reviewed live sample.

**Status:** branch `fix/basis-structural-of903-906`, unmerged and not deployed. RA-109 live acceptance, RA-108, RA-114 and overall hardening remain open.
