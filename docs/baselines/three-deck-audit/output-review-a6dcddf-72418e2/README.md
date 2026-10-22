# Review of `a6dcddf` / `9532c46` addressed at `72418e2`: qualifiers after a condition, attributions, asides and compound subjects

**This folder adds correction evidence and changes nothing else.** It edits nothing in `output-review-8d7f8dc-a6dcddf/` or any earlier evidence, fixture, answer key, grade, recorded memo or raw response. No model was called; recorded memos were replayed, not regenerated. **This is correction evidence only. RA-109 live acceptance and overall hardening stay open, pending independent re-review and a later reviewed live sample.**

## The two blockers, plus one found during validation

Every case follows memo 101's `PAIR_LEAD` and runs on memo 101's payload.

1. **A condition overrode foreign qualifiers.** "If the figures are monthly, the hiring claim is overstated [S2, S3]." and "…, the hiring growth rate is overstated …" were rewritten at `a6dcddf`. After a condition naming the pair, a figure or claim head was enough, and the subject's qualifier ("hiring") was never read.
2. **The serial-list guard merged an aside and a clause.** "The monthly figure is inflated, in management's view, but the definitions remain unclear [S2, S3]." lost both the attribution and the clause at `a6dcddf`. The guard looked only at the text after the last bare comma (", in management's view"), found no verb there, and read it as a list item. It therefore merged the ", but" clause, and the whole chain was replaced.
3. **Found during this round's validation: a compound subject split as two clauses.** The final mutation pass at `afbf715` left Z5 surviving. Probing that boundary showed a real defect: "The monthly figure [S2], and the larger figure [S3] are overstated." was split at the linking comma, and its second half was replaced with the clarification. The same happened at `a6dcddf`.

## The correction (`zelda_api/basis_fidelity.py`, `2471eb3` and `72418e2`)

**Qualifiers are always read** (`_owns_subject`).
- Every qualifier must place or qualify the pair's figure, with or without a condition.
- A condition naming the pair now only lets a *measure* head (activity, volume, scale, engagement, growth) carrying the pair's basis stand in for a figure or claim head. Memo 100's form is "the implied monthly activity".
- Words that say how a figure is read (implied, resulting, apparent, effective, underlying, overall, combined) join the placing qualifiers, so memo 100's "implied" is accepted.

**A clause holding anything besides the subject and its judgment is kept.** In that case the judgment's owner cannot be established. Such a clause is not the pair's when it has:
- words before the subject that are not a condition: "Management says …", "In management's view, …", "According to management, …";
- a comma-set aside after the judgment: "…, in management's view";
- a condition holding more than its one closing comma.

A list marker or number before the subject is not counted as such a word.

**The serial-list guard reads the whole clause** (`_clauses`). A linking comma closes a serial list only when the clause before it contains a bare comma and *no verb at all*. A serial-list subject ("The cumulative, monthly, and daily figures") collects its earlier items across the list's commas.

**Compound subjects are kept whole** (`_judgment`, `72418e2`). Sometimes the pair's clause would be split off at a linking comma whose left side has no verb. That comma joins a compound subject, not two clauses, so the extent of the pair's clause cannot be established and the sentence is kept as written. With this check in place, the list guard no longer needs to strip citations, so it no longer does; Z5 is retired because its outcome can no longer differ.

Ownership is now read per clause segment, not over the joined chain, so continuation separators are not read as asides.

## Changed outputs from `a6dcddf`

These come from [output/exact_and_boundaries.txt](output/exact_and_boundaries.txt) ([script](output/scripts/exact.py.txt)). All are changes toward keeping text whose owner cannot be established.

**Cases this round tests** (10, each kept unchanged at `72418e2`, rewritten at `a6dcddf`):

| Input (after `PAIR_LEAD`) | `a6dcddf` | `72418e2` |
|---|---|---|
| If the figures are monthly, the hiring claim is overstated [S2, S3]. | rewritten | kept |
| If the figures are monthly, the hiring growth rate is overstated [S2, S3]. | rewritten | kept |
| The monthly figure is inflated, in management's view, but the definitions remain unclear [S2, S3]. | rewritten whole | kept |
| The monthly figure is inflated, in management's view [S2, S3]. | rewritten | kept |
| In management's view, the monthly figure is inflated [S2, S3]. | rewritten | kept |
| Management says the monthly figure is overstated [S2, S3]. | rewritten | kept |
| If the figures are monthly, in management's view, the claim is overstated [S2, S3]. | rewritten | kept |
| The monthly figure [S2, S3], and the larger figure are overstated. | first half kept, second half replaced (garbled) | kept |
| The monthly figure [S2], and the larger figure [S3] are overstated. | the same | kept |
| Management has not clarified the definitions, in its view, but the monthly figure is overstated [S2, S3]. | rewritten whole | the pair's clause repaired, the rest kept |

**Boundary probes that changed** (not tests):

| Input | `a6dcddf` | `72418e2` |
|---|---|---|
| Moreover, the monthly figure is overstated [S2, S3]. | rewritten | kept |
| The monthly figure is overstated, as noted earlier [S2, S3]. | rewritten | kept |
| According to management, the monthly figure is overstated [S2, S3]. | rewritten | kept |
| If the cumulative figure is presented as monthly, in management's view, the claim is overstated [S2, S3]. | rewritten whole (`basis_overstatement`) | judgment kept; the existing cumulative-referent rule relabels "the cumulative figure" as "the figure stated without an explicit interval" (`basis_cumulative_referent`) |

**Repairs that still happen** (exact outputs asserted):
- "The monthly figure is inflated [S2, S3], but the definitions remain unclear." becomes the clarification, then ", but the definitions remain unclear."
- "The cumulative, monthly, and daily figures are overstated [S2, S3], but …" is repaired as one list clause, with the ", but" clause kept.
- "If the figures are monthly, the key traction claim is overstated [S2, S3]." is repaired.
- Memo 100's form "If the cumulative figure was restated as a monthly figure, the implied monthly activity would be materially overstated" is repaired.
- A bulleted list item, "- The monthly figure is overstated [S2, S3].", is repaired.
- Memo 98's conditional is repaired.

**Exact outputs:** 54 of 54 at `72418e2`, against 44 at `a6dcddf`, 17 at `8d7f8dc`, 15 at `9b28e14` and 14 at `0664563`. Every carried group is unchanged at `72418e2` ([output/version_comparison_tally.txt](output/version_comparison_tally.txt)).

## Commits and what ran at each

| Commit | What | Checks |
|---|---|---|
| `a6dcddf` (reviewed) | — | **Red.** The final tests were run against `git show a6dcddf:zelda_api/basis_fidelity.py`, with the guard then restored and hash-checked: **11 assertion failures, 0 errors** ([output/red_run_on_a6dcddf.txt](output/red_run_on_a6dcddf.txt)). <br>The failures cover the reviewer's cases, the aside and attribution controls, the compound subjects, the list-guard control and the memo writer with a mocked model (`PipelineReviewA6dcddfTests`, `_generate_memo`). |
| `2471eb3` | Qualifiers after a condition, owner-open clauses, list guard, per-segment ownership; tests | 180 + 77 + 67 = 324 OK ([output/modules_2471eb3.txt](output/modules_2471eb3.txt)) |
| `77fe460` | Tests only: one-comma condition and measure-basis controls | 324 OK ([output/modules_77fe460.txt](output/modules_77fe460.txt)). A discovery mutation pass ran 40 mutants here; **N2 and N6 survived** ([output/mutations_discovery_77fe460.txt](output/mutations_discovery_77fe460.txt)). |
| `afbf715` | Tests only: controls for N2 (a clause with a verb is not a list item) and N6 (a list item's marker) | 324 OK ([output/modules_afbf715.txt](output/modules_afbf715.txt)). A full pass of 94 ran here; **Z5 survived** ([output/mutations_discovery_afbf715.txt](output/mutations_discovery_afbf715.txt)), which led to blocker 3. |
| **`72418e2`** (final application commit and final head) | Compound subjects kept whole; list guard no longer strips citations; compound controls | Modules one at a time: **180 + 77 + 67 = 324 OK** ([output/modules_72418e2.txt](output/modules_72418e2.txt)). <br>`check` and `makemigrations --check --dry-run` exit 0 ([output/check_and_migrations_72418e2.txt](output/check_and_migrations_72418e2.txt)). <br>The replay, probes, comparisons and all 94 mutations ran here. |

The discovery passes at `77fe460` and `afbf715` are superseded; none of their kills is counted.

## Replay of memos 96–101 and the 75 carried probes (at `72418e2`)

- **Replay:** memos 96–101 were replayed through the full guard order ([output/replay_memos_96_to_101_72418e2.json](output/replay_memos_96_to_101_72418e2.json)), with the working tree clean.
- **Probes:** all 75 carried probes were rerun ([output/carried_probes_75_72418e2.json](output/carried_probes_75_72418e2.json)).
- **Against `a6dcddf`:** both outputs are **identical to `a6dcddf`'s committed outputs in every field except `head`** ([output/compare_with_a6dcddf.txt](output/compare_with_a6dcddf.txt)). There were no recorded-memo or probe differences to investigate.
  - Memo 98's and memo 100's repairs are reproduced.
  - Memo 101 differs from the base replay in exactly its four graded repairs.
- **Memo writer:** the memo-writer test asserts those four repairs in the same mocked write as the kept "hiring claim", the kept management-view sentence and the repaired ", but" sentence.

## Mutations: all 94 at `72418e2`

[output/scripts/mutate_x.py.txt](output/scripts/mutate_x.py.txt) applies one mutant at a time to `basis_fidelity.py` and runs the three modules (324 tests). It then restores the original bytes and checks them with SHA-256 before the next mutant. A mutant counts as caught only by assertion failures.

**All 94 ran against `72418e2`, in chunks k00–k18** ([output/mutations_all94_72418e2.txt](output/mutations_all94_72418e2.txt)).

| ID | Mutation | Failures |
|---|---|---|
| N1 | a condition overrides foreign qualifiers (the `a6dcddf` behaviour) | 3 |
| N2 | the list guard reads only the text after the last comma (the `a6dcddf` behaviour) | 10 |
| N3 | a comma-set aside after the judgment does not open the owner | 3 |
| N4 | words before the subject do not open the owner | 4 |
| N5 | a condition may hold an aside | 1 |
| N6 | positive: a list marker is read as a word before the subject | 1 |
| N7 | positive: a serial-list subject does not collect its earlier items | 3 |
| N8 | positive: "implied" is not a placing qualifier (memo 100) | 11 |
| N9 | positive: ownership is read over the joined chain | 2 |
| N10 | a compound subject is split as two clauses | 1 |

- **Re-anchored:** Y1, Z4, Z6, Z7, Z9–Z12, Z15–Z17 and Z20 were re-anchored to the rewritten `_owns_subject`, `_clauses` and ownership code, with the same meaning. Z9 and Z10 now pin the measure path. All were caught.
- **Retired:** Z5 (see the correction).
- **Carried:** every other mutant, with unchanged anchors. All were caught.
- **Total: 94 of 94 caught at `72418e2`, 0 crash-only, 0 survived, 0 not applied, 0 errors in any run.**
- **Restores:** the [pre](output/pre_mutation_hashes_72418e2.txt) and [post](output/post_mutation_hashes_72418e2.txt) hashes are identical. Every mutant ran exactly once.
- **Leftovers:** no orphaned runner was left, and the working tree was clean afterwards.

## Running conditions (disclosed)

- **Watchdog:** started 2026-10-20 01:52:31 and stopped 17:08:24. It killed nothing ([output/memwatch.log.txt](output/memwatch.log.txt)).
- **Low memory:** free RAM before chunks ranged from 0.72 to 1.81 GB ([output/free_ram_before_mutation_chunks.txt](output/free_ram_before_mutation_chunks.txt)). The machine was under pressure from other processes.
  - **Refused chunks:** k07–k09 and later k12–k18 were refused by the runner's 0.9 GB floor before applying anything. Each was rerun after memory recovered. The refusals appear in the RAM log as lines with no result.
  - **Chunks past the tool timeout:** two chunk calls exceeded the 600 s tool timeout and were moved to the background. k11 completed normally there. k13's first attempt stalled on its RAM query and then refused. While k11 ran in the background, a k12 attempt was refused by the hash check (a mutant was applied), so nothing ran concurrently.
  - **Multi-chunk call (my error):** in the `77fe460` discovery pass, one call held three chunks and was backgrounded. It completed with verified restores and is superseded.
- **Verification:** every restore was hash-checked.

## Remaining limitations (not fixed here)

- **More text is kept unrepaired.** Requiring the clause to hold only the subject and its judgment means any lead-in or aside keeps the sentence unchanged. That is the conservative direction. Examples: "Moreover, …", "…, as noted earlier", "Clearly, …" and attributions in any position.
- **Verb detection is a fixed pattern.** The list guard and the compound-subject check use `_ITEM_VERB`: auxiliaries, "not", "-ed" forms and judgment words. A clause whose only verb is something else ("These figures need clarification") counts as verbless.
  - A verbless left side before ", but" is **not** merged unless it also has a bare comma, so "These figures need clarification, but monthly costs are inflated" stays split, as tested.
  - If the pair's clause would be split off after such a left side, the sentence is kept unchanged rather than repaired.
- **Compound and listed subjects are partly handled.** A compound subject joined by ", and" is kept unchanged, not repaired. A serial list with three or more items is repaired as one clause.
- **A bare generic claim is the pair's.** "The claim is overstated [S2, S3]." is repaired (carried).
- **Topics come from evidence categories** (carried).
- **Carried from earlier rounds:**
  - the fixed vocabularies;
  - the general rule's lack of a denial check (a denial now keeps the clause through the subject search);
  - the other-metric refusal list and the third-party gaps;
  - the context-placement limits, the OF-904 upside hypothesis, OF-907 (P3) and slash citations.

  See the earlier READMEs.
- **Not live:** live behaviour requires a later reviewed live sample.

**Status:** branch `fix/basis-structural-of903-906`, unmerged and not deployed. RA-109 live acceptance, RA-108, RA-114 and overall hardening remain open.
