# OF-1102 / OF-1103 correction: review of c8a0336 (consequence scope)

Additive correction evidence for branch `fix/basis-date-transfer-of1102-1103`. Earlier evidence
(`output-of1102-1103-b16d3c1/`, commit c8a0336) is unchanged. No memo was regenerated, no model was called, nothing
was merged or deployed, and no live run was made. All validation below is Claude's own, run locally. None of it is
independent review.

## What the review found (c8a0336)

The reviewer independently reproduced two scope problems in `_consequence_context`:

1. **Protections stopped before the heading.** The rule checked only `sentence[split:at]`, so it inserted its page note
   even when the sentence went on with "according to an analyst", "only if the monthly figure dates from that period"
   or a citation belonging to the consequence.
2. **An unrelated consequence triggered the repair.** "If the figures [S1, S3] are accurate, revenue would be $10M at
   the time of the 'Traction by Apr-16' slide." got the messaging-figure note, because the rule never established
   that the dated consequence concerned the cited figures.

The reviewer ran 19 focused tests in an isolated harness and confirmed that memo 103 changes only `base_scenario` and
`upside_scenario`. They did not rerun the 403 tests or the 21 mutations.

## Commits

| Commit | Content |
|---|---|
| `9d73c8f334088f789b9d354c6741b59f2cd60759` | app and tests: `zelda_api/basis_fidelity.py`, `zelda_api/tests_output_fidelity.py` |
| `c49cb4d05ea0363e5053f3b1600e121dc5871d69` | tests only: three controls only the later-citation, later-narrator and borrowed-denial checks decide; **validation head** |
| this commit | evidence only (this folder) |

`basis_fidelity.py` is byte-identical at 9d73c8f and c49cb4d.

## The change (`_consequence_context`)

- **The heading must close the consequence's clause.** After the heading phrase there must be the sentence's end, a
  dash, ";" or ":" (`_CONSEQUENCE_CLOSE`). Anything else (", according to an analyst", ", only if …", " [S1, S3]",
  ", when page 12 was written") belongs to the consequence, so the sentence is kept.
- **Nothing after that clause may qualify it.** Whatever follows the dash, ";" or ":" may hold no condition or
  supposition ("if", "provided", "presumes"), no date wording ("dates"), no citation, no attribution and no denial
  (`_LATER_HYPOTHESIS`, `_REF`, `_ATTRIBUTION`, `_DENIAL`). A narrator named anywhere in the sentence now keeps it,
  not only one named before the heading.
- **The consequence must concern the cited figures** (`_figures_consequence`). Before the heading it must be a
  subject followed by a predicate.
  - **Subject:** the company named with capitals, "the company", "the platform", "the business" or "it".
  - **Predicate:** allowlisted words only. That means scale words, the cited statements' own words and figures, and
    the pair's categories, never a denial word, even one a statement contains ("3M bots with no explicit interval").
  - **Scale named:** the consequence must name a scale noun, the pair's category or a statement noun ("platform",
    "bots", "traction").
  - So "revenue would be $10M", "revenue would be significant", "ManyChat would have had 40 staff", "the company's
    margins would be large", "ManyChat would be large" and "the analyst would represent …" are all kept.
- **Unchanged:** both memo-103 repairs, the antecedent rules, the pair and page checks, the note's wording and the
  OF-1102 source-context rule.

## Validation (Claude's own)

| Check | Result | File |
|---|---|---|
| New controls against the c8a0336 guard (focused classes, 20 tests) | 22 assertion failures, 0 errors; guard restored and hash checked | `output/red_new_controls_on_c8a0336.txt` |
| Final `tests_output_fidelity` against the c8a0336 guard | 24 assertion failures, 0 errors (20 consequence-kept sub-cases, 4 second-pair) | `output/red_final_tests_on_c8a0336.txt` |
| Green at c49cb4d, modules run serially | 259 + 77 + 67 = **403 OK**; free RAM 1.55–1.58 GB | `output/modules_c49cb4d.txt` |
| `manage.py check`, `makemigrations --check --dry-run` (app code as at 9d73c8f = c49cb4d) | both exit 0, no changes | `output/check_and_migrations_wip.txt` |
| Replay of memos 96–103 (recorded replies, full time → funding → basis sequence) | identical to the c8a0336 replay in every field of every memo, with identical rule lists; against base c6c3d1b only memo 103's `base_scenario` and `upside_scenario` differ; idempotent and order-stable everywhere; every citation supplied; memo 103's base replay equals its stored memo | `output/replay_memos_96_to_103_c49cb4d.json`, `output/replay_summary.txt` |
| 75 carried probes | identical to b16d3c1 apart from the head | `output/carried_probes_compare.txt` |
| Exact expected outputs | 110/110, unchanged from b16d3c1 | `output/exact_and_boundaries_c49cb4d.txt` |
| Reviewer's examples, c8a0336 vs c49cb4d | all four now kept unchanged; both memo-103 repairs byte-identical | `output/review_cases_c8a0336_vs_c49cb4d.txt` |
| Targeted mutations | **27/29 caught** by assertion failures; 0 execution errors; every restore SHA-checked; free RAM 1.30–1.53 GB | `output/mutations_all29_c49cb4d.txt`, `output/mutation_ram.txt` |

The memo-103 changed outputs are byte-identical to those reported at c8a0336 (see
`output-of1102-1103-b16d3c1/output/memo103_changed_outputs.txt`).

### Mutations

The set has 29 mutants.

- **J1–J9 (OF-1102):** unchanged from the previous round.
- **K1–K5 and K7–K11 (OF-1103):** carried over.
  - K6 (consequence denial) and K12 (consequence attribution) were retired. Their checks became part of the
    consequence allowlist.
  - K7's anchor was updated.
- **L1–L10 (new):** one per new protection.

Two survived. Both look equivalent under the new checks; this is not a proof:

- **K5** (a further condition's comma ends the antecedent). With the mutation, the split falls before ", and if …". The
  consequence then starts with a lower-case "and", "or" or "if", which the subject check refuses. Without the mutation,
  the antecedent holds "if", which the accepting-antecedent check refuses. Either way the sentence is kept.
- **K8** (skip the "already placed" check). An existing note "('X' heads page …)" directly follows the heading phrase,
  so `_CONSEQUENCE_CLOSE` does not match and the sentence is returned unchanged. The idempotence tests pass with the
  mutation.

The code for both is kept as defence in depth.

## Limitations

These all err towards under-correction, which is safer than a wrong rewrite.

- **Allowlists:**
  - A consequence in unlisted words is kept, for example "ManyChat would boast a vast installed base". So is one whose
    subject is lower-case other than "the company", "the platform", "the business" or "it".
  - A dash clause using unlisted condition wordings is not examined further.
- **Narrators:** a narrator named anywhere in the sentence keeps it.
- **Citations:** a citation anywhere after the consequence's clause keeps the sentence, even one belonging to an
  unrelated clause.
- **Subjects:** a capitalised subject is not checked against the company's name, because `BasisFacts` carries none. The
  predicate must still describe the cited figures' scale.
- **Typographic quotes:** a heading written in curly quotes ('Traction by Apr-16' with ‘ ’) is not read by any heading
  rule, at c8a0336 or now. The reviewer's example as typed is kept for that reason.
- **Carried from c8a0336, unchanged:**
  - the OF-1003 condition rule does not read the verification qualifier;
  - only one heading phrase per consequence is read;
  - slash and "vs." citations are not read;
  - the note uses the deck's spelling ("140 000+").

## Not claimed

RA-109 live acceptance, RA-108, RA-114 and overall hardening remain open, and so do Q-2–Q-4. No new live run is to be
made until this correction is independently reviewed and merged.
