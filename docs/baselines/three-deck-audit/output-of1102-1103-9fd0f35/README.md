# OF-1102 / OF-1103 correction: review of eee2bc3 (unknown trailing clauses default to preservation)

Additive correction evidence for branch `fix/basis-date-transfer-of1102-1103`. Earlier evidence folders are unchanged.
No memo was regenerated, no model was called, nothing was merged or deployed, and no live run was made. All validation
below is Claude's own, run locally. None of it is independent review.

## What the review found (eee2bc3)

**P2: unrecognised trailing conditions still got the date correction.** `_rest_free` let any clause after the
consequence through unless it held a listed blocking word. The reviewer reproduced the insertion with "— on the
footing that this holds." (disclosed in the eee2bc3 README) and "— premised on this holding.". They asked that
unknown trailing clauses default to preservation, with insertion allowed only after narrowly recognised harmless
continuations, keeping memo 103's "— consistent with a business approaching scale".

The reviewer passed 84 focused basis-guard cases, the five earlier examples and the memo-103 repairs. They did not
rerun the Django suite, the replays or the mutations.

## Commit

| Commit | Content |
|---|---|
| `9fd0f3553300ee8b4575a2261439d9d174e26455` | app and tests; **validation head** |
| this commit | evidence only (this folder) |

## The change

- **`_harmless_continuation(rest)` replaces `_rest_free`.** `rest` is whatever follows the dash, ";" or ":" that
  closes the consequence's clause. It must be either:
  - nothing, because the sentence ends with the heading phrase; or
  - `consistent with` followed only by letters, spaces and hyphens, every word from a 15-word allowlist: a, an,
    network, effect, driven, software, technology, messaging, business, company, platform, approaching, nearing,
    reaching, scale.

  Anything else keeps the sentence unchanged, whatever its words.
- **Removed as dead:** the old blocklist (`_LATER_HYPOTHESIS`, `_REST_FIGURE_WORDS` and the digit, denial and
  attribution checks on `rest`). Nothing outside the allowlist can pass now.
- **Behaviour change in one control.** "…slide; growth would follow." was a repaired control at c49cb4d and eee2bc3.
  It is now kept unchanged, which is under-correction. Memo 103's own continuation, "— consistent with a
  network-effect-driven software business approaching scale.", is now a repaired control of its own.
- **Unchanged:** both memo-103 repairs, the clause-close requirement, the subject and predicate allowlists, the
  consequence denial check, the antecedent rules, the note's wording and the OF-1102 rule.

## Validation (Claude's own)

| Check | Result | File |
|---|---|---|
| Final tests against the eee2bc3 guard | 7 assertion failures, 0 errors: both reviewer examples, "barring surprises", "; growth would follow.", ": a plausible reading.", and two "consistent with" openings with non-allowlisted words; guard restored and hash checked | `output/red_final_tests_on_eee2bc3.txt` |
| Green at clean 9fd0f35, modules run serially | 259 + 77 + 67 = **403 OK**; free RAM 2.15–2.28 GB | `output/modules_9fd0f35.txt` |
| `manage.py check`, `makemigrations --check --dry-run` at 9fd0f35 | both exit 0, no changes | `output/check_and_migrations_9fd0f35.txt` |
| Replay of memos 96–103 (recorded replies, full time → funding → basis sequence) | identical to the eee2bc3 replay in every field of every memo, with identical rule lists; against base c6c3d1b only memo 103's `base_scenario` and `upside_scenario` differ; idempotent and order-stable; every citation supplied; memo 103's base replay equals its stored memo | `output/replay_memos_96_to_103_9fd0f35.json`, `output/replay_summary.txt` |
| 75 carried probes | identical to eee2bc3 apart from the head | `output/carried_probes_compare.txt` |
| Exact expected outputs | 110/110, 0 diff lines from eee2bc3 | `output/exact_and_boundaries_9fd0f35.txt` |
| All reviewer examples (three rounds), c8a0336 / c49cb4d / eee2bc3 / 9fd0f35 | all twelve kept at 9fd0f35; both memo-103 repairs byte-identical across the four versions | `output/review_cases_through_9fd0f35.txt` |
| Targeted mutations | **26/29 caught** by assertion failures; 0 execution errors; every restore SHA-checked; free RAM 1.50–2.03 GB | `output/mutations_all29_9fd0f35.txt`, `output/mutation_ram.txt` |

### Mutations

The set has 29 mutants: J1–J9, K1–K5 and K7–K11, L1 and L6–L9, M5 and M6, and N1–N3.

- **Retired with their code:** L3, L4, L5 and M0–M4 (the blocklist).
- **Re-anchored:** K7.
- **New:** N1 accepts any later clause; N2 accepts "consistent with" followed by any words; N3 rejects a sentence
  that ends at the heading.

Three survived. All look equivalent under the current checks; this is not proven:

- **K5 and K8:** the reasons are unchanged from `output-of1102-1103-c49cb4d/README.md`.
- **L6** (narrator checked up to the heading only, not the whole sentence). After the heading only nothing or
  allowlisted continuation words may stand, so no narrator's name can appear there, and both versions behave the
  same. The whole-sentence check is kept as the safer form.

## Limitations

These leave text unchanged; none adds a note to a sentence that should be kept, as far as this round tested.

- **Any other continuation is kept.** That includes harmless ones such as "; growth would follow.",
  "— a plausible reading", and "consistent with" followed by words outside the 15-word allowlist.
- **Allowlists:**
  - unlisted consequence wordings are kept;
  - so are lower-case subjects other than "the company", "the platform", "the business" or "it";
  - a capitalised subject is not checked against the company's name.
- **Typographic quotes:** a heading in curly quotes is not read by any heading rule.
- **Carried, unchanged:**
  - the OF-1003 condition rule does not read the verification qualifier;
  - only one heading phrase per consequence is read;
  - slash and "vs." citations are not read;
  - the note uses the deck's spelling ("140 000+").

## Not claimed

RA-109 live acceptance, RA-108, RA-114 and overall hardening remain open, and so do Q-2–Q-4. No new live run is to be
made until this correction is independently reviewed and merged.
