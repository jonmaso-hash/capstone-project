# Review of `7fb484b` / `bbe0ec4` addressed at `377a142`: subject, metric and speaker ownership

**This folder adds correction evidence and changes nothing else.** It edits nothing in `output-review-750de3f-7fb484b/` or any earlier evidence, grade, memo, raw response, ledger, frozen key or fixture. No model was called; recorded memos were replayed, not regenerated. **This is correction evidence only. RA-109 live acceptance needs a later reviewed live sample.**

## Correction to the previous evidence

`output-review-750de3f-7fb484b/README.md` says: "Phrasings outside them keep their text (the conservative direction)." **That was wrong.** The lists it describes were refusal lists, such as subjects that may not follow "or" and markers of attribution. A phrasing missing from such a list was **rewritten**, not kept. The review's three cases are counterexamples. This round turns each of those checks into an allowlist (below), and the limitations section here restates the claim correctly.

## The review's three regressions

Every case was unchanged at `0664563` and changed at `7fb484b`. Each was run through the full normalisation, time, funding and basis sequence on memo 101's payload, with the basis guard loaded from git at each commit ([output/reviewer_cases_0664563_7fb484b_377a142.txt](output/reviewer_cases_0664563_7fb484b_377a142.txt)):

| # | Input | `7fb484b` | `377a142` |
|---|---|---|---|
| 1a | (after the message-pair sentence) "These figures need clarification — or Bob is wrong." | "… — how the figure stated without an explicit interval … relied on." (`basis_referent_judgment`) | **unchanged**, no rule |
| 1b | (same) "These figures need clarification — marketing is misleading." | same rewrite: "marketing" counted as a participle | **unchanged** |
| 2 | "The cumulative and monthly figures for revenue differ from message counts [C2, C3]." | "The unspecified-interval and monthly figures for revenue …" (`basis_cumulative_presupposed`) | **unchanged** |
| 3 | "An analyst describes the deck's 500M messages [S2, S3] in a slide context headed 'Traction by Apr-16'." | "… [S2] …; the deck separately states 500M messages/month [S3] on page 12 (…)." (`basis_source_context`) | **unchanged** |

This round adds eight controls of its own: "— pricing is wrong", "— suggesting marketing is misleading", "figures for bots", "figures differ from revenue", "An analyst's reading of the deck's …", the narrator, attribution and figure-noun controls. All eight are kept at `0664563` and `377a142`. At `7fb484b` the first five were rewritten. The last three were kept there too; they exist only to pin a single check each (see mutations).

## The corrections (`zelda_api/basis_fidelity.py`)

- **1. A dash carries "these figures" only into a fragment on an allowlist** (`_CONTINUATION`):
  - **Allowed:** a listed participle (raising, suggesting, indicating, implying) whose object is the judgment, for example "raising the possibility of metric inflation" (memo 101's risk) or "suggesting possible inflation".
  - **Allowed:** "or/and/nor/which" and listed hedges or linking verbs leading straight into the judgment: "or inflated", "possibly inflated", "or possibly inflated", "which may be overstated".
  - **Everything else starts a new subject**, for example "— or Bob is wrong", "— marketing is misleading" and "— suggesting marketing is misleading".
  - **What it replaces:** `7fb484b` accepted any `\w+ing` word and any word after "or" that was not on a refusal list.
- **2. A generic figure noun needs metric ownership** (`_cumulative_presupposed`): the phrase "the cumulative and monthly <figures|presentations|…>" changes only when both of these hold:
  - any qualifier straight after the noun (for/of/on/about/in/from/across) names the pair's own noun ("figures for messages", "presentations of the 500M messages figure");
  - no other metric is named between the clause start and the owning citation.
- **3. A clause with no reporting verb needs the company's own head** (`_own_head`):
  - **Rule:** every word before the moved citations must be one of the placing words, the company's own source words ("the deck's", "self-reported", "company", …), the "taking … at face value" frame, or a word or figure from the cited statements.
  - **Effect:** a third party is kept whatever verb it uses, because the check no longer depends on a list of attribution verbs.
  - **"describes":** not added to the attribution list; the allowlist makes the addition unnecessary.
- **Cleanup (`7015ca5`):** `_JUDGMENT` and `_CONTINUATION` now share one `_JUDGMENT_WORD` pattern (same alternation). One parenthesis check was dropped: `_plain_words` already refuses a parenthesis, so the check could not change an outcome, and a mutant of it would have been equivalent.

## Commits and what ran at each

| Commit | What | Checks |
|---|---|---|
| `7fb484b` (reviewed) | — | **Red**, with `7fb484b`'s application code (`basis_fidelity.py` identical to `7fb484b`; the new tests applied): **10 assertion failures, 0 errors**, through the full sequence (`Review7fb484bTests`) and the memo writer (`PipelineReview7fb484bTests`, `_generate_memo`) ([output/red_run_on_7fb484b.txt](output/red_run_on_7fb484b.txt)) |
| `2ccb886` | Corrections 1–3 with their tests | 164 + 77 + 67 = 308 OK, run on the tree before the commit, content identical ([output/modules_2ccb886_tree.txt](output/modules_2ccb886_tree.txt)) |
| `7015ca5` | Cleanup (above) | `tests_output_fidelity` 164 OK. Mutation chunks w1–w3 and c1–c6 |
| `54664fa` | Test only: narrator control (T3 survived at `7015ca5`) | chunks c7–c8 |
| **`377a142`** (final head) | Test only: attribution and figure-noun controls (V6 and V8 survived at `54664fa`) | chunk c9 (T3, V6, V8 caught). Modules one after another: **164 + 77 + 67 = 308 OK** ([output/modules_377a142.txt](output/modules_377a142.txt)). `check` and `makemigrations --check` exit 0 ([output/check_and_migrations_377a142.txt](output/check_and_migrations_377a142.txt)). Replay, probes and reviewer cases |

## Replay of memos 96–101 and the carried probes

- **Replay** ([output/replay_memos_96_to_101_377a142.json](output/replay_memos_96_to_101_377a142.json)): this uses the same script as last round. It runs each recorded reply through the full guard order, once with `0664563`'s basis guard (loaded from git) and once with the working tree's, which was clean at `377a142`. The result is **identical to `7fb484b`'s committed replay in every field except `head`** ([output/compare_with_7fb484b.txt](output/compare_with_7fb484b.txt)).
  - Memos 96–100 are unchanged.
  - Memo 101 still differs in exactly its four graded repairs: `business_model_analysis`, `base_scenario`, `risk_assessment` and `downside_scenario`.
  - The memo writer test also asserts those four repairs in the same write.
- **Probes:** all 75 carried probes give output identical to `7fb484b`'s ([output/carried_probes_75_377a142.json](output/carried_probes_75_377a142.json)).

## Mutations

[output/scripts/mutate_w.py.txt](output/scripts/mutate_w.py.txt) applies one mutant at a time and runs the three affected modules (308 tests). It then restores the original bytes and checks them with SHA-256 before the next mutant. **A mutant counts as caught only by assertion failures.** Each chunk refused to start unless the hashes matched and free RAM was at least 0.9 GB.

| ID | Mutation (review of `7fb484b`) | Result | Control that failed |
|---|---|---|---|
| W1 | any `\w+ing` word continues (the old rule) | caught, 4 failures, 0 errors | "— marketing is misleading", "— pricing is wrong", "— suggesting marketing is misleading" |
| W2 | a listed participle continues whatever its object | caught, 1, 0 | "— suggesting marketing is misleading" |
| W3 | "or/and/nor/which" continues whatever follows | caught, 3, 0 | "— or Bob is wrong", "— and the analyst is wrong" |
| W4 | no qualifier check | caught, 1, 0 | "figures for bots" |
| W5 | a qualifier may name any noun | caught, 1, 0 | "figures for bots" |
| W6 | no other-metric check before the owning citation | caught, 1, 0 | "figures differ from revenue [C2, C3]" |
| W7 | no own-head check | caught, 3, 0 | "An analyst describes …", "An analyst's reading of …" |
| W8 | any word is an own-head word | caught, 3, 0 | the same |
| W9 | positive: no participle continues | caught, 8, 0 | memo 101 risk, "— suggesting possible inflation" |
| W10 | positive: no "or"/hedge continues | caught, 3, 0 | "— or inflated", "— possibly inflated", "— or possibly inflated" |
| W11 | positive: own-head vocabulary lacks the own-source words | caught, 9, 0 | memo 101 base, "The deck's 500M messages …", "The self-reported figures …" |

- **Carried:** Q1–Q3, Q5–Q15, R1–R3, R5, R6, T1–T13, V1–V3 and V5–V9 were all caught.
  - **V4 retired:** the new-subject lookahead it mutated has been replaced by the allowlist, which W1–W3 mutate.
  - **V3 kept:** a dash always continuing remains a meaningful mutant.
- **Survivors, then fixed:** three carried mutants first survived because the new allowlists also kept their old controls. Each got a control only it keeps, verified both ways by a probe:
  - **T3** (narrator check, survived at `7015ca5`): new control "The company states 500M messages [S2, S3] from the Pitch Deck Hunt copy in …". Without the name, the same sentence is split.
  - **V6** (attribution check, survived at `54664fa`): new control "The self-reported 500M messages [S2, S3], an analyst says, sit in …". With ", in short," in its place, it is split.
  - **V8** (figure-noun check, survived at `54664fa`): new control "The cumulative and monthly bots [C2, C3] differ." The same sentence with "monthly messages" is rewritten.
  - **After the controls:** all three were caught at `377a142`.
- **Total: 51 of 51 caught, 0 crash-only, 0 survivors left.** Across all 54 runs no mutant produced an error ([output/mutations_all_chunks.txt](output/mutations_all_chunks.txt)).
- **Restores and heads:** every restore matched, and the [pre](output/pre_mutation_hashes_377a142.txt) and [post](output/post_mutation_hashes_377a142.txt) hashes are identical.
  - `basis_fidelity.py`'s hash was the same (`f5e73d12…`) in every chunk from `7015ca5` to `377a142`.
  - Between those heads only tests were added. An added assertion cannot uncatch a mutant, so the 48 kills recorded at `7015ca5` and `54664fa` were **not re-run** at `377a142`. Only T3, V6 and V8 were.

## Running conditions, disclosed

- **Watchdog:** a memory watchdog (kill any python.exe over 1,500 MB) was started and verified at 02:55:37, before the red run. It ran through every module run, mutation chunk and replay, and killed nothing ([output/memwatch.log.txt](output/memwatch.log.txt)).
- **Free RAM:** it was 0.97–1.64 GB before each chunk ([output/free_ram_before_mutation_chunks.txt](output/free_ram_before_mutation_chunks.txt)). That is lower than the 1.5–2.05 GB last round, so the chunk floor was lowered from 1.2 to 0.9 GB. The first module run started at 0.97 GB.
- **Backgrounded runs:** two tool calls (chunks c1–c3, then c4–c5) ran past the 600 s tool limit and were moved to the background. They ran to completion unattended. Two other chunk calls sent while c1–c3 was running **refused to start** on the hash check, because a mutant was applied at that moment. Nothing was killed, no orphaned runner or mutant was left, and later chunks ran one per call.
- **Commit history:** a local soft reset briefly folded `bbe0ec4`'s evidence files into the fix commit. It was re-parented onto `bbe0ec4` before anything else ran. Nothing was pushed in between.

## Remaining limitations (not fixed here)

- **What allowlists do:** a phrasing outside the new allowlists (continuation, figure-noun qualifier, own-head words) keeps its text, which is the conservative direction. Two kinds of check are still refusal lists, where an unlisted phrasing is **not** kept:
  - the other-metric list (`_OTHER_METRIC`);
  - the attribution markers, on the verb path and after the citations.
- **Verb path:** with the company's own reporting verb, the words before the subject are not checked against an allowlist. "Bob, the company states …" still counts as the company's statement.
- **No-verb path:** only the words *before* the moved citations are checked. A third party named after them with no attribution marker ("…, which an analyst describes, …") is not detected.
- **Region check:** another metric is looked for only between the clause start and the owning citation.
- **Carried from earlier rounds:**
  - independent ";" clauses;
  - "per" and "notes" as broad attribution markers;
  - a page-12 figure with its own mention, a context phrase inside a non-context parenthesis, or one mid-clause, is not moved;
  - the OF-904 upside hypothesis is kept;
  - OF-907 (P3);
  - the general judgment rule has no denial check of its own;
  - slash citations are not recognised by `claim_context._REF`.
- **Not live:** live behaviour needs a later reviewed live sample.

**Status:** branch `fix/basis-structural-of903-906`, unmerged and not deployed. RA-109 live acceptance, RA-108, RA-114 and overall hardening remain open.
