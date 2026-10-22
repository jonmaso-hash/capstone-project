# Review of `8d7f8dc` / `eca3d8c` addressed at `688f638` (validated at `a6dcddf`): clause preservation, judged subject, pair-directed claims

**This folder adds correction evidence and changes nothing else.** It edits nothing in `output-review-9b28e14-8d7f8dc/` or any earlier evidence, fixture, answer key, grade, recorded memo or raw response. No model was called; recorded memos were replayed, not regenerated. **This is correction evidence only. RA-109 live acceptance and overall hardening stay open, pending independent re-review and a later reviewed live sample.**

## The three blockers

Every case follows memo 101's `PAIR_LEAD` ("- The deck states 500M messages [S2] on page 10 and 500M messages/month [S3] on page 12.") and runs on memo 101's payload.

1. **Whole-sentence replacement dropped independent clauses with no judgment word.** "The monthly figure is overstated [S2, S3]; management has not clarified the definitions." and the reverse order both lost the management clause. At `8d7f8dc`, `_judgment` replaced the whole sentence whenever every *judging* clause was the pair's, so a clause with no judgment word was replaced along with it. The same loss happened after a dash and after a linking comma, which did not split clauses at all.
2. **Ownership read incidental vocabulary.** At `8d7f8dc` a clause was the pair's if it contained a basis word, a figure referent or the pair's noun anywhere. So "— monthly costs are inflated" and "— misleading messages are wrong" were rewritten, although their subjects are costs and messages that are sent.
3. **A clearly pair-directed claim lost its repair.** "The key traction claim may be overstated [S2, S3]." was kept at `8d7f8dc`, because no word in it was a basis word, a figure referent or the pair's noun. `9b28e14` had repaired it only through the citations.

## The correction (`zelda_api/basis_fidelity.py`)

**Clauses.**
- **Splitting:** `_clauses` splits a sentence at ";", at a spaced dash and, new, at a comma before a clause-linking conjunction (and, but, while, whereas, yet, although, though, so, because, which).
- **Continuations:** a coordinated judgment after the comma ("…, and possibly inflated") still parses as a continuation and stays in its clause's chain.
- **Serial lists:** the comma closing a serial list does not split. When the text after the last bare comma before it has no verb ("The cumulative, monthly, and daily figures"), that comma closes a list. Citations are removed first, so "[S2, S3]" is not read as a list.

**Replacement.** `_judgment` now replaces only the chains holding the pair's judgments. Adjacent pair chains get one clarification, each keeping its citations and its end; the clarification is lower-cased after the first clause. Every other clause stays as written, whether it judges something else or states a fact. The whole-sentence branch is gone, and a sentence that is all the pair's still comes out as one clarification.

**Ownership by the judged subject** (`_owns_subject`). The judged subject is the noun phrase before the judgment's verb group, back to its determiner, a comma or the clause start. The judgment is the pair's when:

- **The subject is the pair's.** Two conditions, both required:
  - **Head:** the head is a figure or claim noun (figure, total, count, number, metric, value, statistic, claim, rate). Or it is one of the pair's **topics**, the words of its own evidence items' categories ("usage", "traction"). Or it is the pair's noun together with one of the pair's **figures** ("the 500M messages").
  - **Qualifiers:** every other word places or qualifies the pair's figure: a basis word, the pair's noun, topic or figure, a page or slide, an own source ("the deck's"), a placing word (key, headline, larger, …), or "and"/"or".
- **Or it follows a condition about the pair.** The judgment is the consequence of a condition (`_CONDITION`: if, whether, unless, assuming, …) whose text names the pair by a basis word, a figure referent or the pair's noun. Its subject must be:
  - a figure or claim, as in memo 98: "If the cumulative figure is being presented as a monthly figure, the key traction claim is materially overstated"; or
  - a measure (activity, volume, scale, engagement, growth) carrying the pair's basis or vocabulary, as in memo 100: "…, the implied monthly activity would be materially overstated".

A pair referent ("these figures") still governs its chain as before. **Citations still never own a clause.**

`Pair` gains `topics` and `figures`, both computed from the pair's own items in `basis_facts`. No example word is refused by name.

## Exact outputs, per version ([output/exact_and_boundaries.txt](output/exact_and_boundaries.txt), [script](output/scripts/exact.py.txt))

The table counts exact output and rule label for the 37 cases of this round and the previous round, through the full sequence on memo 101's payload. Each basis guard was loaded from git; the final one is the clean working tree at `a6dcddf`.

| | `0664563` | `9b28e14` | `8d7f8dc` | **`a6dcddf`** |
|---|---|---|---|---|
| Exact | 10/37 | 11/37 | 13/37 | **37/37** |

Some of the cases, at `a6dcddf`:

| Input (after `PAIR_LEAD`) | Output at `a6dcddf` |
|---|---|
| The monthly figure is overstated [S2, S3]; management has not clarified the definitions. | *Clarification* [S2, S3]; **management has not clarified the definitions.** |
| Management has not clarified the definitions; the monthly figure is overstated [S2, S3]. | **Management has not clarified the definitions;** *clarification* [S2, S3]. |
| …the same after " — ", ", but", ", and", ", which" | the clause kept, the pair's clause repaired, citations kept |
| These figures may be inflated, but management has not clarified the definitions [S2, S3]. | *Clarification*, **but management has not clarified the definitions [S2, S3].** (referent rule) |
| The key traction claim may be overstated [S2, S3]. | *Clarification* [S2, S3]. |
| The key traction claim may be overstated [S2, S3], and monthly costs are inflated. | *Clarification* [S2, S3], **and monthly costs are inflated.** |
| These figures need clarification — monthly costs are inflated [S2, S3]. | kept |
| These figures need clarification — misleading messages are wrong [S2, S3]. | kept |
| These figures need clarification — the messages are misleading [S2, S3]. | kept (the pair's noun without one of its figures) |
| The hiring claim is overstated [S2, S3]. | kept |
| If the figures are monthly, monthly costs are inflated [S2, S3]. | kept |
| The cumulative, monthly, and daily figures are overstated [S2, S3]. | *Clarification* [S2, S3]. (one clause, not split mid-list) |
| The monthly figure is overstated, and possibly inflated [S2, S3]. | *Clarification* [S2, S3]. |
| The monthly figure is overstated [S2]; the cumulative figure is inflated [S3]. | *Clarification* [S2] [S3]. |

**Two earlier expectations changed.** These are the review-of-`9b28e14` cases "These figures need clarification — the cumulative figure is overstated [S2, S3]." and "— the larger figure is overstated [S2, S3]." Both now keep "These figures need clarification — " before the clarification; at `8d7f8dc` the whole sentence was replaced. This is the behaviour blocker 1 asks for. The tests were updated in `6ced273` and the change is stated there.

**Carried groups** ([output/version_comparison_tally.txt](output/version_comparison_tally.txt), [output/version_comparison.txt](output/version_comparison.txt)): every carried keep-control is kept at `a6dcddf`:

- 2 reviewer inputs and 5 controls from the review of `9b28e14`;
- 2 inputs and 7 controls from the review of `377a142`;
- 12 controls from the review of `7fb484b`;
- 14 controls from the review of `750de3f`.

The 6 genuine continuations from the review of `377a142` and memo 98's conditional are still repaired; the tests assert their exact outputs.

## Commits and what ran at each

| Commit | What | Checks |
|---|---|---|
| `8d7f8dc` (reviewed) | — | **Red.** The final tests were run against `git show 8d7f8dc:zelda_api/basis_fidelity.py`, with the guard then restored and hash-checked: **25 assertion failures, 0 errors** ([output/red_run_on_8d7f8dc.txt](output/red_run_on_8d7f8dc.txt)). <br>The failures cover the three blockers, the memo writer with a mocked model response (`PipelineReview8d7f8dcTests`, `_generate_memo`) and the 2 changed expectations. |
| `6ced273` | Clause split, per-chain replacement, judged subject, pair topics and figures; tests | 176 + 77 + 67 = 320 OK ([output/modules_6ced273.txt](output/modules_6ced273.txt)). <br>Boundary probes then found the serial-list garbling, the dropped ", which" clause and a too-loose condition path. |
| **`688f638`** (final application commit) | Serial lists kept whole, ", which" starts a clause, condition path tightened; tests | 320 OK ([output/modules_688f638.txt](output/modules_688f638.txt)) |
| `dcbf8c1` | Tests only: two kept-controls | 320 OK ([output/modules_dcbf8c1.txt](output/modules_dcbf8c1.txt)). <br>A first mutation pass of 25 mutants ran here: Y5, Y6 and Y7 **survived** ([output/mutations_partial_dcbf8c1_superseded.txt](output/mutations_partial_dcbf8c1_superseded.txt)). That pass is superseded and none of its kills is counted. |
| **`a6dcddf`** (final head) | Tests only: one control for each way a condition names the pair, plus a negative. Application bytes identical to `688f638` | Modules one at a time: **176 + 77 + 67 = 320 OK** ([output/modules_a6dcddf.txt](output/modules_a6dcddf.txt)). <br>`check` and `makemigrations --check --dry-run` exit 0 ([output/check_and_migrations_a6dcddf.txt](output/check_and_migrations_a6dcddf.txt)). <br>The replay, probes, comparisons and all 85 mutations ran here. |

**Why Y5–Y7 survived.** They remove one check each from `_names_pair`: a basis word, a figure referent or the pair's noun. This round, `_names_pair` reads only the condition before a judgment. Every existing condition named the pair in more than one of those ways, so no single check decided any test. `a6dcddf` adds one condition for each check alone ("If the deck counts weekly, …", "If the larger figure is restated, …", "If the messages are restated, …"), plus a condition that names nothing of the pair ("If the hiring plan slips, …", kept).

## Replay of memos 96–101 and the 75 carried probes (at `a6dcddf`)

- **Replay:** memos 96–101 were replayed through the full guard order ([output/replay_memos_96_to_101_a6dcddf.json](output/replay_memos_96_to_101_a6dcddf.json)), with the working tree clean.
- **Probes:** all 75 carried probes were rerun ([output/carried_probes_75_a6dcddf.json](output/carried_probes_75_a6dcddf.json)).
- **Against `8d7f8dc`:** both outputs are **identical to `8d7f8dc`'s committed outputs in every field except `head`** ([output/compare_with_8d7f8dc.txt](output/compare_with_8d7f8dc.txt)). There were no differences to investigate.
  - Memos 96–100 are unchanged.
  - Memo 100's recorded overstatement repair is reproduced exactly.
  - Memo 101 differs from the base replay in exactly its four graded repairs.
- **Memo writer:** the memo-writer test asserts those four repairs in the same mocked write as the kept management clause, the kept "— monthly costs are inflated" and the repaired "key traction claim".

## Mutations: all 85 at `a6dcddf`

[output/scripts/mutate_x.py.txt](output/scripts/mutate_x.py.txt) applies one mutant at a time to `basis_fidelity.py` and runs the three modules (320 tests). It then restores the original bytes and checks them with SHA-256 before the next mutant. A mutant counts as caught only by assertion failures.

**All 85 ran against `a6dcddf`, in foreground chunks f1–f17** ([output/mutations_all85_a6dcddf.txt](output/mutations_all85_a6dcddf.txt)).

| ID | Mutation | Failures | Controls that failed |
|---|---|---|---|
| Z1 | the whole sentence is one run (whole-sentence replacement) | 15 | the management clause in every order and separator |
| Z2 | a linking comma does not separate clauses | 6 | ", but"/", and" management and "monthly costs" clauses |
| Z3 | ", which" does not start a clause | 1 | "…, which management has not explained." |
| Z4 | a serial list is split at its last comma | 1 | "The cumulative, monthly, and daily figures …" |
| Z5 | a citation's commas count as a list's | 3 | the comma clauses after "[S2, S3]" |
| Z6 | the subject's qualifiers are not read | 1 | "The hiring claim is overstated" |
| Z7 | the subject's head is not read | 11 | "monthly costs", the condition controls, the 9b28e14 inputs |
| Z8 | the pair's noun heads without a pair figure | 1 | "— the messages are misleading" |
| Z9 | a condition owns any consequence | 3 | "If the figures are monthly, misleading advertising / monthly costs / hiring growth …" |
| Z10 | after a condition, a measure needs no pair basis | 1 | "…, hiring growth is overstated" |
| Z11 | after a condition, a basis word alone owns it | 1 | "…, monthly costs are inflated" |
| Z12 | the subject runs past its determiner | 31 | memo 98 forms and many repairs |
| Z13 | the verb group is not skipped | 56 | nearly every general-rule repair |
| Z14 | positive: topics are not pair vocabulary | 3 | "The key traction claim …", memo writer |
| Z15 | positive: a topic is not a pair head | 1 | "The reported usage is overstated" |
| Z16 | positive: no condition path | 7 | memo 100 replay and stored memo, the three condition controls |
| Z17 | positive: no measure head after a condition | 7 | the same |
| Z18 | positive: adjacent pair clauses each get a clarification | 2 | "[S2]; … [S3]", the carried ";" case |
| Z19 | positive: a page is not a placing qualifier | 1 | "The page-10 figure is overstated as a monthly figure …" |
| Z20 | positive: the pair's figures are not its vocabulary | 1 | "The 500M messages are overstated" |

- **Re-anchored mutants:** Q5, Q13, T8, Y1 and Y2 were re-anchored to the new code, with the same meaning.
  - Q5 and T8 now mutate `_clauses` and `_CLAUSE_SPLIT`.
  - Q13's old anchor occurred twice, so it was given unique context.
  - Y1 is the `9b28e14` fallback, where citations own a clause; it was caught with 26 failures.
- **Retired:** Y3 is retired, because the whole-sentence branch it mutated no longer exists; Z1 puts that behaviour back.
- **Relabelled:** Y5–Y7 were relabelled to what they now pin, the condition path.
- **Total: 85 of 85 caught at `a6dcddf`, 0 crash-only, 0 survived, 0 not applied, 0 errors in any run.**
- **Restores:** the [pre](output/pre_mutation_hashes_a6dcddf.txt) and [post](output/post_mutation_hashes_a6dcddf.txt) hashes are identical.
- **Leftovers:** no orphaned runner was left, and the working tree was clean afterwards.

## Running conditions

- **Watchdog:** started at 2026-10-19 22:13:30, before the first red run, and kept running through every run until 2026-10-20 01:42:35. It killed nothing ([output/memwatch.log.txt](output/memwatch.log.txt)).
- **Free RAM:** 1.46–1.76 GB before each final chunk ([output/free_ram_before_mutation_chunks.txt](output/free_ram_before_mutation_chunks.txt)). Every chunk ran in the foreground, one per tool call.

## Remaining limitations (not fixed here)

These were probed at `a6dcddf` ([output/exact_and_boundaries.txt](output/exact_and_boundaries.txt), "BOUNDARY probes") unless marked carried.

- **Subject grammar is a fixed vocabulary.** The heads, measures, placing qualifiers, the verb group and the clause conjunctions are fixed lists. Anything outside them is **kept, not repaired**. This is the conservative direction, and three of these were rewritten at `8d7f8dc` and earlier:
  - an unlisted adverb in the verb group: "The monthly figure is **clearly** overstated [S2, S3]." is kept;
  - a judgment noun with no subject before it: "There is a risk of overstatement in the monthly figure [S2, S3]." is kept;
  - a denial: "The monthly figure is not overstated [S2, S3]." is now kept, because "not" ends the subject search. The general rule still has no denial check of its own.
- **Attribution before the subject is not read.** "Management says the monthly figure is overstated [S2, S3]." is replaced whole, including "Management says". This is carried from earlier rounds; the attribution markers are still a refusal list.
- **A bare generic claim is the pair's.** "The claim is overstated [S2, S3]." is repaired, because a figure or claim head with no foreign qualifier is taken to be the pair's when the sentence resolves to the pair. `8d7f8dc` kept it.
- **Topics come from evidence categories.** "traction" counts because memo 101's statements carry the category "Traction". With other category labels, a "traction claim" is the pair's only through a condition.
- **The serial-list check is heuristic.** It looks for a verb after the last bare comma before the conjunction. A list item containing a verb, or a clause on the left whose verb is not recognised and which has an earlier comma, is joined rather than split.
- **Comma splitting is limited to the listed conjunctions.** A comma without one ("…, management has not clarified …") and a parenthetical clause still stay in one chain.
- **Carried:**
  - the whole-fragment continuation grammar's fixed lists (`377a142` review);
  - the other-metric refusal list and the third-party gaps (`7fb484b` review);
  - the context-placement limits, the OF-904 upside hypothesis, OF-907 (P3) and slash citations in `claim_context._REF`.

  See `output-review-377a142-9b28e14/README.md`.
- **Not live:** live behaviour requires a later reviewed live sample.

**Status:** branch `fix/basis-structural-of903-906`, unmerged and not deployed. RA-109 live acceptance, RA-108, RA-114 and overall hardening remain open.
