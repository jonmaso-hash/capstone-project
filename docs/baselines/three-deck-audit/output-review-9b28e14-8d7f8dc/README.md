# Review of `9b28e14` / `e16ad6a` addressed at `8d7f8dc`: judgment ownership and the general rule's fallback

**This folder adds correction evidence and changes nothing else.** It edits nothing in `output-review-377a142-9b28e14/` or any earlier evidence, fixture, answer key, grade, recorded memo or raw response. No model was called; recorded memos were replayed, not regenerated. **This is correction evidence only. RA-109 live acceptance and overall hardening stay open, pending independent re-review and a later reviewed live sample.**

## The blocker

The re-review used memo 101's payload and the existing `PAIR_LEAD` ("- The deck states 500M messages [S2] on page 10 and 500M messages/month [S3] on page 12."). Two inputs must stay unchanged:

1. "These figures need clarification — misleading advertising is wrong [S2, S3]."
2. "These figures need clarification — inflation is affecting costs [S2, S3]."

At `9b28e14`, each lost its whole second sentence through `basis_overstatement`.

**Cause:** `_CONTINUATION.fullmatch` correctly rejected the independent fragment, so no pair referent governed it. `_judgment`, the general judgment rule, then replaced the **whole sentence** because pair citations were present. Its only ownership test was "a basis word or a citation anywhere in the sentence". A sentence's final citations sit at the end of its last clause, so they say nothing about which clause they support.

**This is an incomplete fix, not a new regression.** Both inputs were rewritten at `0664563`, `7fb484b`, `377a142` and `9b28e14` (table below). The previous round's controls had no citations, so they never reached the fallback.

## Version comparison

Each input was run through the full normalisation, time, funding and basis sequence on memo 101's payload. The basis guard was loaded from git at each earlier commit, and from the clean working tree at `8d7f8dc` ([output/version_comparison.txt](output/version_comparison.txt), tally in [output/version_comparison_tally.txt](output/version_comparison_tally.txt), [script](output/scripts/version_compare.py.txt)).

| Input group | `0664563` | `7fb484b` | `377a142` | `9b28e14` | **`8d7f8dc`** |
|---|---|---|---|---|---|
| The reviewer's 2 cited inputs (must keep) | rewritten | rewritten | rewritten | rewritten | **2 kept** |
| 5 new keep-controls (below) | rewritten | rewritten | rewritten | rewritten | **5 kept** |
| 7 new repair-controls (below) | 7 changed | 7 changed | 7 changed | 7 changed | **7 repaired as asserted** |
| Memo 98's conditional overstatement | repaired | repaired | repaired | repaired | **repaired** |
| Carried from `377a142`'s review: 2 reviewer inputs + 7 controls (must keep) | 9 kept | 4 kept, 5 rewritten | 9 rewritten | 9 kept | **9 kept** |
| Carried from `377a142`'s review: 6 genuine continuations (must repair) | 1 repaired | 6 repaired | 6 repaired | 6 repaired | **6 repaired** |
| Carried from `7fb484b`'s review: 12 controls (must keep) | 12 kept | 3 kept, 9 rewritten | 12 kept | 12 kept | **12 kept** |
| Carried from `750de3f`'s review: 14 controls (must keep) | 14 kept | 14 kept | 14 kept | 14 kept | **14 kept** |

"Changed" in the repair row only means the text was rewritten. The tests assert the exact output, and before this fix 3 of the 7 were wrong: the two mixed sentences lost their independent clause, and the referent sentence got the wrong rule label (red run below).

**The new keep-controls** (all after `PAIR_LEAD`):

- **Cited, after "These figures need clarification — ":** "wrong assumptions drive the model [S2, S3]." and "or inflation is affecting costs [S2, S3]."
- **A ";" clause:** "These figures need clarification; misleading advertising is wrong [S2, S3]."
- **A standalone sentence:** "Misleading advertising is wrong [S2, S3]." Citations alone do not say what a judgment is about.
- **A basis word outside the judging clause:** "The monthly figure needs clarification — misleading advertising is wrong." This one is uncited. It reached the fallback through the sentence-wide basis-word test.

**The new repair-controls** (exact outputs asserted in `Review9b28e14Tests`):

| Input (after `PAIR_LEAD`) | Output | Rule |
|---|---|---|
| "These figures need clarification — the cumulative figure is overstated [S2, S3]." | the clarification, whole sentence, [S2, S3] | `basis_overstatement` |
| "The 500M messages figure is overstated [S2, S3]." | the same | `basis_overstatement` |
| "These figures need clarification — the larger figure is overstated [S2, S3]." | the same | `basis_overstatement` |
| "The cumulative figure is overstated [S2, S3] — misleading advertising is wrong." | the clarification [S2, S3] — **misleading advertising is wrong.** | `basis_overstatement` |
| "Misleading advertising is wrong; the monthly figure is inflated [S2, S3]." | **Misleading advertising is wrong;** the clarification (lower-cased) [S2, S3]. | `basis_overstatement` |
| "These figures may be inflated — misleading advertising is wrong [S2, S3]." | the clarification — **misleading advertising is wrong [S2, S3].** | `basis_referent_judgment` |
| "These figures need clarification — possibly overstated [S2, S3]." | … — the clarification [S2, S3]. | `basis_referent_judgment` |

## The correction (`zelda_api/basis_fidelity.py`)

**Ownership.** `_judged_segments(sentence, pair)` now also reports, for each judging segment, whether the judgment is the pair's:

- **Governed:** a pair referent governs it ("these figures", "one or both figures"; unchanged rule); or
- **Named:** its own chain names the pair (`_names_pair`) with a basis word, a figure referent ("the larger figure") or the pair's counted noun ("the 500M messages figure").

Citations are not read for ownership. Any other judgment has a subject of its own. The check is an allowlist of what names the pair; no word or sentence is refused by name.

**Dispatch.**

- **Referent rule decides:** `_referent_judged` hands the sentence to the referent rule only when every judgment that is the pair's is governed. A judgment that is not the pair's goes to neither rule, so a sentence whose judgments are all someone else's is kept.
- **Every judging clause is the pair's:** `_judgment` replaces the whole sentence, exactly as before. Memo 98's correction is unchanged.
- **Mixed sentence:** only the chains holding the pair's judgments are replaced, each keeping its citations and end punctuation. The clarification is lower-cased after the first clause. The other chains are kept as written.

The sentence-level gate (a judgment, not a question, with a basis word or citation) is unchanged.

## Commits and what ran at each

| Commit | What | Checks |
|---|---|---|
| `9b28e14` (reviewed) | — | **Red.** The final tests were run against `git show 9b28e14:zelda_api/basis_fidelity.py`, with the guard then restored and hash-checked: **11 assertion failures, 0 errors** ([output/red_run_on_9b28e14.txt](output/red_run_on_9b28e14.txt)). <br>The failures were 7 keep-controls through the full sequence, 3 repair-controls (both mixed sentences, plus the mixed referent sentence's rule label) and the memo writer with a mocked model response (`PipelineReview9b28e14Tests`, `_generate_memo`). <br>Memo 98, the whole-sentence repairs, the cited continuation and the earlier controls passed there, as expected. |
| `a6b3edc` | Ownership, dispatch and tests | Modules one at a time: 172 + 77 + 67 = 316 OK ([output/modules_a6b3edc.txt](output/modules_a6b3edc.txt)). Superseded by `8d7f8dc`. |
| **`8d7f8dc`** (final application commit) | Drops a no-op citation strip in `_names_pair`: none of its patterns can match a citation, so the line could only show up as an equivalent mutant | Modules one at a time at the committed, clean head: **172 + 77 + 67 = 316 OK** ([output/modules_8d7f8dc.txt](output/modules_8d7f8dc.txt)). <br>`check` and `makemigrations --check --dry-run` exit 0 ([output/check_and_migrations_8d7f8dc.txt](output/check_and_migrations_8d7f8dc.txt)). <br>The replay, probes, version comparison and all 66 mutations below ran here. |

## Replay of memos 96–101 and the 75 carried probes (at `8d7f8dc`)

- **Replay** ([output/replay_memos_96_to_101_8d7f8dc.json](output/replay_memos_96_to_101_8d7f8dc.json)): the same script as the previous rounds. Each recorded reply goes through the full guard order with `0664563`'s basis guard (from git) and with the working tree's, which was clean at `8d7f8dc`.
- **Probes:** all 75 carried probes were rerun ([output/carried_probes_75_8d7f8dc.json](output/carried_probes_75_8d7f8dc.json)).
- **Against `9b28e14`:** both outputs are **identical to `9b28e14`'s committed outputs in every field except `head`** ([output/compare_with_9b28e14.txt](output/compare_with_9b28e14.txt)). There were no output differences to investigate.
  - Memos 96–100 are unchanged.
  - Memo 101 still differs from the base replay in exactly its four graded repairs: `business_model_analysis`, `base_scenario`, `risk_assessment` and `downside_scenario`.
- **Memo writer:** `PipelineReview9b28e14Tests` asserts the four repairs in the same mocked write as the two kept cited clauses and the repaired mixed sentence.

## Mutations: all 66 at `8d7f8dc`

[output/scripts/mutate_x.py.txt](output/scripts/mutate_x.py.txt) applies one mutant at a time to `basis_fidelity.py` and runs the three modules (316 tests). It then restores the original bytes and checks them with SHA-256 before the next mutant. A mutant counts as caught only by assertion failures.

**Every mutant ran against `8d7f8dc`, in foreground chunks y1–y14** ([output/mutations_all66_8d7f8dc.txt](output/mutations_all66_8d7f8dc.txt)). The application code changed in this round, so no earlier kill is counted.

| ID | Mutation | Result | Controls that failed |
|---|---|---|---|
| Y1 | **the `9b28e14` fallback:** a judging chain holding citations is the pair's | caught, 8 failures, 0 errors | both reviewer inputs, the cited keep-controls, the mixed referent sentence, the memo writer |
| Y2 | every judgment is the pair's (ownership not read) | caught, 11, 0 | every keep-control, both mixed sentences, the memo writer |
| Y3 | a mixed sentence is replaced whole | caught, 2, 0 | both mixed sentences |
| Y4 | the referent rule's dispatch counts judgments that are not the pair's | caught, 8, 0 | the reviewer inputs and keep-controls (a spurious `basis_overstatement`), the mixed referent sentence |
| Y5 | positive: a basis word does not name the pair | caught, 1, 0 | "The page-10 figure is overstated as a monthly figure [C2, C3]; one or both figures may mislead." (carried) |
| Y6 | positive: a figure referent does not name the pair | caught, 2, 0 | "— the larger figure is overstated [S2, S3]." |
| Y7 | positive: the pair's counted noun does not name the pair | caught, 1, 0 | "The 500M messages figure is overstated [S2, S3]." |
| Y8 | positive: a later clause's clarification is not lower-cased | caught, 1, 0 | "Misleading advertising is wrong; the monthly figure is inflated [S2, S3]." |
| Y9 | positive: the pair's clause loses its citations in a mixed sentence | caught, 2, 0 | both mixed sentences |

- **Re-anchored mutants:** R1, R2 and T8 were re-anchored to the ownership-aware code, with the same meaning. All three were caught. R1's failures include the reviewer's two inputs; R2's include the cited keep-controls.
- **Carried mutants:** Q1–Q3, Q5–Q15, R3, R5, R6, T1–T7, T9–T13, V1–V3, V5–V9, W1–W11 and X1–X6, with unchanged anchors. All were caught.
- **Total: 66 of 66 caught at `8d7f8dc`, 0 crash-only, 0 survived, 0 not applied, 0 errors in any run.**
- **Restores:** every restore matched. The [pre](output/pre_mutation_hashes_8d7f8dc.txt) and [post](output/post_mutation_hashes_8d7f8dc.txt) hashes are identical.
- **Leftovers:** no orphaned runner was left, and the working tree was clean afterwards.

## Running conditions

- **Watchdog:** started at 16:17:49, before the red run, and kept running through every module run, replay, probe run and mutation chunk until 18:00:59. It killed nothing ([output/memwatch.log.txt](output/memwatch.log.txt)).
- **Free RAM:** 1.61–2.07 GB before each chunk ([output/free_ram_before_mutation_chunks.txt](output/free_ram_before_mutation_chunks.txt)). Every chunk ran in the foreground, one per tool call.
- **One module run went to the background:** a first run of the usage-basis and funding modules on the uncommitted working tree passed the 120 s tool timeout and was moved to the background. It completed OK. It is not part of this evidence: the recorded module runs at `a6b3edc` and `8d7f8dc` are separate and complete.

## Remaining limitations (not fixed here)

The first three examples below were checked at `9b28e14` and `8d7f8dc` ([output/limitation_examples.txt](output/limitation_examples.txt), [script](output/scripts/limits.py.txt)).

- **Ownership vocabulary:** a clause is the pair's when it names a basis word, a figure referent from the fixed `_FIGURE_REFERENT` list, or the pair's counted noun.
  - **Kept, not repaired:** a genuine judgment that names none of them, such as "The key traction claim may be overstated [S2, S3]." `9b28e14` rewrote it through the citations. None of memos 96–101 or the 75 probes contains such a sentence, so the replay is unchanged.
  - **Still treated as the pair's:** a new subject that uses the pair's noun or a basis word, such as "— misleading messages are wrong" or "— monthly costs are inflated".
- **Mixed sentences:** the mixed path splits only at ";" and at dashes, as `_judged_segments` always has. A comma-joined independent clause ("…, but misleading advertising is wrong") is still in the same chain and is replaced with it.
- **No denial check of its own:** the general rule still has none (carried).
- **Carried from the review of `377a142`:** genuine continuations outside the whole-fragment grammar are kept, not repaired; the grammar's word lists are fixed.
- **Carried from earlier rounds:** see `output-review-377a142-9b28e14/README.md`.
  - The other-metric list and the attribution markers are refusal lists.
  - Two third-party gaps remain: on the reporting-verb path and on the no-verb path.
  - Independent ";" clauses are not continued.
  - The context-placement limits remain.
  - The OF-904 upside hypothesis is kept, and OF-907 (P3) is not addressed.
  - Slash citations are not recognised by `claim_context._REF`.
- **Not live:** live behaviour requires a later reviewed live sample.

**Status:** branch `fix/basis-structural-of903-906`, unmerged and not deployed. RA-109 live acceptance, RA-108, RA-114 and overall hardening remain open.
