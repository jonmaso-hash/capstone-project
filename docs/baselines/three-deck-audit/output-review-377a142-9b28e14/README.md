# Review of `377a142` / `ee47a9a` addressed at `9b28e14`: whole-fragment continuation ownership

**This folder adds correction evidence and changes nothing else.** It edits nothing in `output-review-7fb484b-377a142/` or any earlier evidence, fixture, answer key, grade, recorded memo or raw response. No model was called; recorded memos were replayed, not regenerated. **This is correction evidence only. RA-109 live acceptance and overall hardening stay open, pending independent re-review and a later reviewed live sample.**

## The blocker

The independent review reproduced two inputs. Each follows the message-pair sentence `- The deck states 500M messages [S2] on page 10 and 500M messages/month [S3] on page 12.` At `377a142`, `basis_referent_judgment` replaced each final clause with the message-basis clarification, deleting its meaning:

- "These figures need clarification — misleading advertising is wrong."
- "These figures need clarification — inflation is affecting costs."

**Cause:** `_judged_segments` called `_CONTINUATION.match(segment)`. That accepted a judgment-like **first word** ("misleading", "inflation") and never read the rest of the fragment, which has its own subject.

## Version comparison

Each input was run through the full normalisation, time, funding and basis sequence on memo 101's payload, with the basis guard loaded from git at each commit and from the working tree at `9b28e14` (clean) ([output/version_comparison.txt](output/version_comparison.txt), [script](output/scripts/version_compare.py.txt)):

| Input | `0664563` | `7fb484b` | `377a142` | `9b28e14` |
|---|---|---|---|---|
| "… — misleading advertising is wrong." | kept | **rewritten** | **rewritten** | kept |
| "… — inflation is affecting costs." | kept | kept | **rewritten** | kept |
| 7 new controls with an independent subject, or with an unclassifiable fragment (below) | 7 kept | 3 kept, 4 rewritten | **7 rewritten** | 7 kept |
| 6 genuine continuations that must be repaired (below) | 1 repaired\* | 6 repaired | 6 repaired | **6 repaired** |
| 12 carried controls from the review of `7fb484b` | 12 kept | 3 kept, 9 rewritten | 12 kept | 12 kept |
| 14 carried controls from the review of `750de3f` | 14 kept | 14 kept | 14 kept | 14 kept |

\* At `0664563`, only the cited "— possibly overstated [S2, S3]." changed, by the general judgment rule (`basis_overstatement`), which replaced the whole sentence.

**The new controls** (after "These figures need clarification — "):

- **Independent subjects beginning with judgment-like words, kept:**
  - "wrong assumptions drive the model."
  - "overstated expectations are common."
  - "or inflation is affecting costs."
  - "suggesting inflation is affecting costs."
  - "possibly inflated expectations are common."
- **A bare judgment noun, kept:** "inflation." It does not say whose inflation.
- **An unfamiliar tail after a genuine judgment, kept:** "possibly inflated by bots." The tail is not classified, so the conservative direction applies.

**Genuine continuations, still repaired:**
- "or possibly inflated."
- "suggesting possible inflation."
- "misleading."
- "which may be overstated."
- "raising the possibility of metric inflation or imprecise reporting." (memo 101's risk shape)
- "possibly overstated [S2, S3]." (its citations stay with the clarification)

## The correction (`9b28e14`, `zelda_api/basis_fidelity.py`)

`_CONTINUATION` is now matched against the **whole** fragment (`fullmatch`). A fragment is a continuation only if it is exactly the following, in order:

1. **One of two forms:**
   - **a.** A listed participle (raising, suggesting, indicating, implying), optionally followed by "the possibility/prospect/risk of" or "concerns/questions of/about", then listed modifiers, then a judgment **noun**: overstatement, inflation, exaggeration, misrepresentation, error or inaccuracy.
   - **b.** Optionally "or/and/nor/which", then listed hedges or linking verbs, then a judgment **predicate**: overstated, inflated, exaggerated, misleading, misrepresented, incorrect, erroneous or wrong.
2. **Then only:**
   - coordinated judgments ("or imprecise reporting", "and inflated");
   - the fragment's own citations;
   - closing punctuation.

Each judgment slot takes one grammatical form, so a judgment word that begins a new noun phrase cannot fill it:

- "misleading advertising is wrong" has a predicate followed by an unparsed noun phrase.
- "inflation is affecting costs" has a noun with no participle.

Anything that does not parse starts a new chain and is kept: an unfamiliar tail, an unlisted start or a bare noun. No word or sentence is refused by name; the rule is a grammar for the whole fragment.

## Commits and what ran at each

| Commit | What | Checks |
|---|---|---|
| `377a142` (reviewed) | — | **Red**, with `377a142`'s `basis_fidelity.py` (verified identical) and the new tests: **10 assertion failures, 0 errors** ([output/red_run_on_377a142.txt](output/red_run_on_377a142.txt)). <br>9 kept cases failed through the full sequence (`Review377a142Tests`), and the memo writer failed with a mocked model response (`PipelineReview377a142Tests`, `_generate_memo`). <br>The genuine-continuation test passed there, as expected: those repairs already worked. |
| **`9b28e14`** (application and tests) | Whole-fragment `_CONTINUATION` and tests | Modules run one at a time at the committed, clean head: **167 + 77 + 67 = 311 OK** ([output/modules_9b28e14.txt](output/modules_9b28e14.txt)). <br>`check` and `makemigrations --check --dry-run` exit 0 ([output/check_and_migrations_9b28e14.txt](output/check_and_migrations_9b28e14.txt)). <br>Replay, probes, version comparison and all 57 mutations below |

## Replay of memos 96–101 and the 75 carried probes

- **Replay** ([output/replay_memos_96_to_101_9b28e14.json](output/replay_memos_96_to_101_9b28e14.json)): the same script as the previous two rounds. Each recorded reply goes through the full guard order with `0664563`'s basis guard (from git) and with the working tree's (clean at `9b28e14`).
- **Probes:** all 75 carried probes were rerun ([output/carried_probes_75_9b28e14.json](output/carried_probes_75_9b28e14.json)).
- **Against `377a142`:** both outputs are **identical to `377a142`'s committed outputs in every field except `head`** ([output/compare_with_377a142.txt](output/compare_with_377a142.txt)). There were no output differences to investigate.
  - Memos 96–100 are unchanged.
  - Memo 101 differs in exactly its four graded repairs: `business_model_analysis`, `base_scenario`, `risk_assessment` and `downside_scenario`.
- **Memo writer:** the memo-writer test also asserts those four repairs in the same write as the two kept clauses and one repaired continuation.

## Mutations: all 57 at `9b28e14`

[output/scripts/mutate_x.py.txt](output/scripts/mutate_x.py.txt) applies one mutant at a time and runs the three modules (311 tests). It then restores the original bytes and checks them with SHA-256 before the next mutant. A mutant counts as caught only by assertion failures.

**Every mutant ran against `9b28e14`'s application code, in chunks x1–x12** ([output/mutations_all57_9b28e14.txt](output/mutations_all57_9b28e14.txt)). The application code changed in this round, so no kill from an earlier round is counted.

| ID | Mutation | Result | Control that failed |
|---|---|---|---|
| X1 | prefix-only matching (`match`, not `fullmatch`) | caught, 7 failures, 0 errors | the reviewer's two inputs and the independent-subject controls; memo writer |
| X2 | anything may follow the judgment (the tail is not validated) | caught, 7, 0 | the same |
| X3 | the predicate slot accepts a bare judgment noun | caught, 1, 0 | "— inflation." |
| X4 | positive: no coordinated judgment after the first | caught, 8, 0 | memo 101 risk ("… or imprecise reporting") |
| X5 | positive: the fragment's own citations are not allowed | caught, 1, 0 | "— possibly overstated [S2, S3]." |
| X6 | positive: a participle's object must be a predicate, not a noun | caught, 11, 0 | memo 101 risk, "— suggesting possible inflation." |

- **Re-anchored mutants:** W1, W2, W3, W9, W10 and V3 were re-anchored to the new `_CONTINUATION` text, with the same meaning.
  - In W1–W3 the replacement ends in `.*` because the pattern is now matched whole.
  - All six were caught. For example, W2's failures include "— suggesting inflation is affecting costs."
- **Carried, unchanged anchors:** Q1–Q3, Q5–Q15, R1–R3, R5, R6, T1–T13, V1, V2, V5–V9, and W4–W8 and W11. All were caught.
- **Total: 57 of 57 caught at `9b28e14`, 0 crash-only, 0 survived, 0 errors in any run.**
- **Restores:** every restore matched. The [pre](output/pre_mutation_hashes_9b28e14.txt) and [post](output/post_mutation_hashes_9b28e14.txt) hashes are identical.
- **Leftovers:** no orphaned runner was left, and the working tree was clean afterwards.

## Running conditions

- **Watchdog:** started and verified at 12:24:26, before the red run, and kept running through every module run, replay, probe run and mutation chunk. It killed nothing ([output/memwatch.log.txt](output/memwatch.log.txt)).
- **Free RAM:** 1.38–2.06 GB before each chunk ([output/free_ram_before_mutation_chunks.txt](output/free_ram_before_mutation_chunks.txt)). Every chunk ran in the foreground, one per tool call, and none was moved to the background.

## Remaining limitations (not fixed here)

- **New continuation scope (narrower than `377a142`):** genuine judgments of the figures phrased outside the grammar are now **kept, not repaired**. Examples: "— possibly inflated by bots", "— inflating usage", or a judgment noun with no listed participle ("— inflation."). This is the conservative direction. `377a142` repaired some of them only because it never read the rest of the fragment.
- **Lexical extent of the grammar:** the participles, modifiers, hedges, judgment predicates and judgment nouns are fixed lists. Coordinated tails are limited to "or/and" plus a judgment or "reporting/measurement".
- **Carried from the review of `7fb484b`:**
  - The other-metric list and the attribution markers are still refusal lists.
  - On the path with the company's own reporting verb, the words before the subject are not checked ("Bob, the company states …").
  - On the no-verb path, a third party named after the citations with no attribution marker is not detected.
- **Carried from earlier rounds:**
  - independent ";" clauses are not continued;
  - "per" and "notes" are broad attribution markers;
  - a page-12 figure with its own mention, a context phrase inside a non-context parenthesis, or one mid-clause, is not moved;
  - the OF-904 upside hypothesis is kept;
  - OF-907 (P3) is not addressed;
  - the general judgment rule has no denial check of its own;
  - slash citations are not recognised by `claim_context._REF`.
- **Not live:** live behaviour requires a later reviewed live sample.

**Status:** branch `fix/basis-structural-of903-906`, unmerged and not deployed. RA-109 live acceptance, RA-108, RA-114 and overall hardening remain open.
