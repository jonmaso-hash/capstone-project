# Review of `b040c23` / `750de3f` addressed at `7fb484b`: scope regressions in the OF-903..906 rules

**Separate, additive correction evidence.** It edits nothing in `output-structural-of903-906-b040c23/` or any earlier evidence, grade, memo, raw response, ledger, frozen key or fixture. No model was called; recorded memos are replayed, not regenerated. **Correction evidence only; RA-109 live acceptance requires a later reviewed live sample.**

## The review's four regressions, and two more found while isolating them

All four were unchanged at `0664563` and changed at `b040c23`. Below, through the full normalisation, time, funding and basis sequence on memo 101's payload ([before](output/reviewer_cases_b040c23.txt), [after](output/reviewer_cases_7fb484b.txt)):

| # | Input | `b040c23` | `7fb484b` |
|---|---|---|---|
| 1 | (after the message-pair sentence) "Nothing suggests these figures are wrong — or inflated." | "… are wrong — how the figure stated without an explicit interval … relied on." (`basis_referent_judgment`) | **unchanged**, no rule |
| 2 | (after the message-pair sentence) "These figures need clarification — an analyst is wrong." | "… — how the figure … relied on." (`basis_referent_judgment`) | **unchanged**, no rule |
| 3 | "The cumulative and monthly revenue differ while the message counts remain ambiguous [C2, C3]." | "The unspecified-interval and monthly revenue …" (`basis_cumulative_presupposed`) | **unchanged**, no rule |
| 4 | "According to an analyst, 500M messages [S2, S3] sit in a slide context headed 'Traction by Apr-16'." | "… [S2] sit in …; the deck separately states 500M messages/month [S3] on page 12 (…)." (`basis_source_context`) | **unchanged**, no rule |
| 5 (found here) | "The cumulative and monthly **figures** differ while the message counts remain ambiguous [C2, C3]." | rewritten: a citation blocked by "while" fell back to the sentence's pair | **unchanged** (red at `ffb08ae`: 1 failure) |
| 6 (found here) | "These figures need clarification — **perhaps the deck** is inflating usage." | rewritten: "perhaps" counted as a continuation | **unchanged** (red at `abb2b56`: 1 failure) |

## The corrections (`zelda_api/basis_fidelity.py`)

- **Denials across a dash (1):** `_judged_segments` now tracks a chain per clause. A denial before the referent ("Nothing suggests these figures …"), or of an earlier judgment in the chain ("These figures are not wrong — …"), covers the judgments coordinated with it after a dash. Coordinated undenied judgments of the same figures become **one** clarification, not two ("These figures are wrong — or inflated." becomes the clarification once).
- **New subjects (2, 6):** a dash carries the referent only into a continuation fragment: a participle ("— raising …"), or "or/and/nor/possibly/potentially/perhaps" followed by a predicate, never by a determiner or pronoun ("— or inflated", "— possibly inflated"), or "which …". Anything else after a dash ("— an analyst is wrong", "— and the analyst …", "— perhaps the deck is …") starts a new chain, which needs its own referent.
- **Other metrics (3, 5):**
  - "the cumulative and monthly …" changes only when its own noun is a figure noun (presentations, figures, numbers, counts, totals, rates, bases, readings, versions, metrics, values, statements, measures) or the pair's noun, never another metric.
  - A later citation owns the phrase only with no comma, ";" or clause connector ("while", "whereas", "but", …) between them.
  - A citation behind such a boundary means ownership is unknown, with no fallback to the sentence's pair.
- **Third-party attribution (4):**
  - The context split keeps any statement with an attribution marker before the context phrase ("according to", "per", "as reported/stated/listed/cited/noted/described by", "says/said", "claims", "notes", "writes", "estimates", "believes", "argues", "told").
  - With no reporting verb, it acts only when the clause names the company's own source ("self-reported", "the deck", "the company", …).
  - Memo 101's base scenario ("the self-reported traction metrics") is still repaired.

## Commits and what ran at each

| Commit | What | Checks at that commit |
|---|---|---|
| `b040c23` (reviewed) | — | **Red** for the review's cases and variants, run with `b040c23`'s application code ([output/red_run_on_b040c23.txt](output/red_run_on_b040c23.txt)): **10 assertion failures, 0 errors**, through the full sequence (`Review750de3fTests`) and the memo writer (`PipelineReview750de3fTests`, `_generate_memo`) |
| `ffb08ae` | Corrections 1–4; two earlier controls' inputs gain "self-reported" (below) | `tests_output_fidelity` 161, `tests_usage_basis` 77, `tests_funding_fidelity` 67, run one after another: OK. Replay of memos 96–101 ([ffb08ae json](output/replay_memos_96_to_101_ffb08ae.json)), identical to `b040c23`'s. 75 probes identical |
| `abb2b56` | A blocked citation means unknown ownership (case 5); isolating controls | Red at `ffb08ae`: 1 failure ([output/red_run_ffb08ae_connector.txt](output/red_run_ffb08ae_connector.txt)). 161 + 77 + 67 OK |
| `b37aa7b` | The new-subject lookahead covers "possibly/potentially/perhaps" (case 6); ";" control | Red at `abb2b56`: 1 failure ([output/red_run_abb2b56_perhaps.txt](output/red_run_abb2b56_perhaps.txt)). 161 + 77 + 67 OK. **First mutation run**: 40 of 41 caught; **T2 survived** ([output/mutations_first_run_b37aa7b.txt](output/mutations_first_run_b37aa7b.txt)) |
| **`7fb484b`** (final application head) | Test only: a control only the clause-end check keeps | T2 caught. **All 41 mutants: 41 caught** ([output/mutations_final_all41_7fb484b.txt](output/mutations_final_all41_7fb484b.txt)). Modules one after another after restoration: **161 + 77 + 67 = 305 OK**. `check` and `makemigrations --check` clean. Replay and probes repeated |

**Two earlier controls' inputs were changed, disclosed:**
- `Of903SharedContextTests`: the no-verb positive case now reads "Taking the **self-reported** figures at face value …", because a no-verb clause must name the company's own source.
- `Of903SharedContextTests`: the parenthesis control now reads "- The **self-reported** 500M messages [S2, S3] (within …)", so that only the parenthesis check keeps it.

Their expected outputs are otherwise unchanged.

## Replay of memos 96–101

[output/replay_memos_96_to_101_7fb484b.json](output/replay_memos_96_to_101_7fb484b.json): each recorded reply goes through the full guard order with `0664563`'s basis guard (from git) and with `7fb484b`'s.
- **Memos 96–100:** no field differs.
- **Memo 101:** exactly `business_model_analysis`, `base_scenario`, `risk_assessment` and `downside_scenario` differ, the four graded repairs. The `0664563` replay reproduces memo 101's stored text.
- **Stability:** reversed items give the same output, a second pass changes nothing, and citations stay in order.
- **Against `b040c23`:** every memo's result is **identical** to the `b040c23` replay, so the scope corrections change no recorded output.
- **Probes:** the 75 carried probes give identical output ([output/carried_probes_75_7fb484b.json](output/carried_probes_75_7fb484b.json)).

## Mutations

[output/scripts/mutate_v.py.txt](output/scripts/mutate_v.py.txt) applies one mutant at a time, runs the three affected modules (305 tests), and restores the original bytes with a SHA-256 check before the next. **A mutant counts as caught only by assertion failures.**

| ID | Mutation (review of `750de3f`) | `7fb484b` | Intended control that failed |
|---|---|---|---|
| V1 | a denial before the referent does not cover the chain | caught, 4 failures, 0 errors | "Nothing in the deck suggests that these figures, taken together on both pages, are wrong — or inflated." and the OF-806 denial |
| V2 | a denied judgment does not cover the judgments coordinated with it | caught, 1, 0 | "These figures are not wrong — or inflated." |
| V3 | a dash carries the referent into a part with its own subject | caught, 4, 0 | "— an analyst is wrong", "— and the analyst is wrong", "— perhaps the deck is …" |
| V4 | the continuation fragment needs no new-subject check | caught, 2, 0 | "— and the analyst is wrong", "— perhaps the deck is …" |
| V5 | coordinated judgments each get a clarification | caught, 1, 0 | "These figures are wrong — or inflated." |
| V6 | an attribution does not keep the citations | caught, 1, 0 | "According to an analyst, the self-reported 500M messages …" |
| V7 | without a reporting verb, no own source is needed | caught, 1, 0 | "500M messages [S2, S3] sit in a slide context headed …" |
| V8 | the cumulative phrase need not be about a figure noun | caught, 1, 0 | "The cumulative and monthly revenue [C2, C3] differ." |
| V9 | a later citation owns the phrase across a clause connector | caught, 1, 0 | "The cumulative and monthly figures differ while …" |

- **Carried:** T1–T13, R1, R2, R3, R5, R6, and Q1–Q3, Q5–Q15, all caught at `7fb484b`. Q4 is retired: the denial check it removed is now computed per chain and mutated as V1/V2. R2, T9 and T12 are re-anchored to the moved code with the same meaning.
- **Total: 41 of 41 caught, 0 crash-only, 0 survived.** No run had any errors.
- **Restores:** every restore matched; the [pre](output/pre_mutation_hashes_7fb484b.txt) and [post](output/post_mutation_hashes_7fb484b.txt) hashes are identical.
- **Memory:** free RAM was 1.50–2.05 GB before each chunk.
- **T2 at `b37aa7b`:** it survived, because its control is also kept by the own-source requirement. `7fb484b` adds a mid-clause control that names the company's source, and T2 is caught there.

## Memory watchdog: disclosed

- **Gap:** the watchdog from the previous round was stopped when that round finished. This round's red run at `b040c23` and the module runs up to `ffb08ae` ran **without it**, serially and with free RAM checked before them (2.1 GB).
- **Restored:** it was restarted and verified (start line logged, 00:26:41) before the replay, every mutation chunk and every later module run, and ran until the evidence was assembled. Nothing crossed 1,500 MB ([output/memwatch.log.txt](output/memwatch.log.txt)).

## Remaining limitations (not fixed here)

- **Lexical extents:** the lists of continuation starters, attribution markers, own-source words, figure nouns and clause connectors are fixed. Phrasings outside them keep their text (the conservative direction).
- **Broad attribution markers:** "per" and "notes" are among the attribution markers, so a context phrase after "per month" or "The deck notes …" keeps the sentence.
- **Independent ";" clauses:** a fragment after ";" ("; possibly inflated") is treated as an independent clause and kept.
- **Carried from earlier rounds:**
  - a page-12 figure with its own mention, a context phrase inside a non-context parenthesis, or one mid-clause is not moved;
  - the OF-904 upside hypothesis is kept;
  - OF-907 (P3) is not addressed;
  - the general judgment rule has no denial check of its own when a judgment is not governed by a referent;
  - slash citations are not recognised by `claim_context._REF`.
- **Not live:** live behaviour requires a later reviewed live sample.

**Status:** branch `fix/basis-structural-of903-906`, unmerged and not deployed. RA-109 live acceptance, RA-108, RA-114 and overall hardening remain open.
