# OF-1102 / OF-1103 correction: review of c49cb4d (later date contingencies, capitalised denials)

Additive correction evidence for branch `fix/basis-date-transfer-of1102-1103`. Earlier evidence folders
(`output-of1102-1103-b16d3c1/`, `output-of1102-1103-c49cb4d/`) are unchanged. No memo was regenerated, no model was
called, nothing was merged or deployed, and no live run was made. All validation below is Claude's own, run locally.
None of it is independent review.

## What the review found (c49cb4d)

1. **Trailing date conditions still triggered a rewrite.** A consequence followed by "— subject to the monthly figure
   referring to that period" got the page note, and so did "contingent on …" and "only when …". These clauses suppose
   the date, so the sentence should stay unchanged. The check on later clauses was a short list of connectives.
2. **Capitalised denials bypassed protection, a new regression at c49cb4d.** "No platform would have significant
   throughput …" and "Neither platform …" got the note. The subject matcher consumed "No" or "Neither", and the denial
   check only examined the rest of the consequence. c8a0336 had kept these sentences.

The reviewer ran 20 focused tests, the four earlier examples and memo replays 96 and 98–103. They did not rerun the
403 tests or the mutations.

**Correction to the c49cb4d README.** That README listed its limitations as all erring towards leaving text unchanged.
That was wrong: finding 1 rewrote sentences that should have been kept, and finding 2 was a regression. This folder
replaces that statement; the earlier file is not edited.

## Commits

| Commit | Content |
|---|---|
| `9cc86476741317f59f55c3f1270f54973e683231` | app and tests: both fixes, with the reviewer's cases and variants as controls |
| `eee2bc30bd56fa19fe94a8a54d84c70bcd6d4bd1` | app and tests: removes checks the new ones make dead (no output change) and adds 3 controls so each remaining check decides a case alone; **validation head** |
| this commit | evidence only (this folder) |

## The change

- **Later clause, `_rest_free`.** This is what follows the dash, ";" or ":" after the heading. It must contain:
  - no condition, supposition or contingency. `_LATER_HYPOTHESIS` now also lists "subject to", "contingent",
    "conditional", "dependent", "depending", "only when", "insofar", "in (the) event", "in case", "should",
    "given that", "on the basis/understanding", "refer…", "relate…", "apply…" and "cover…";
  - no speaker and no denial, including "-n't" words;
  - **no mention of the figures, their basis, a place or a time.** That covers figure, period, time, when, then,
    month(ly), interval, basis, page, slide, heading, April and similar words, plus the pair's categories and bases and
    the cited statements' words;
  - no digit and no quoted span. A digit covers figures and citations ("[S2]"), so the separate citation check
    became dead and was removed.

  So a date supposition worded in a way no list holds ("— with the monthly figure from that period") is still kept,
  because it names the figure and a time.
- **Consequence denial.** Denial and near-denial words (`_DENIAL` plus few, hardly, barely, scarcely, nobody,
  nowhere) are refused anywhere in the consequence, the subject included. That catches "No platform", "Neither
  platform", "Few would …", and "3M bots with no explicit interval" borrowed from a statement. The vocabulary's own
  `- _DENIAL` became dead and was removed. A "-n't" word is not an allowlisted predicate word, so the allowlist still
  refuses it.
- **Unchanged:** both memo-103 repairs, the antecedent rules, the clause-close requirement, the subject and predicate
  allowlists, the note's wording and the OF-1102 rule.

## Validation (Claude's own)

| Check | Result | File |
|---|---|---|
| New controls (tests at 9cc8647) against the c49cb4d guard | 12 assertion failures, 0 errors: the 10 later-clause variants (incl. the reviewer's three) and "No" / "Neither"; guard restored and hash checked | `output/red_new_controls_9cc8647_on_c49cb4d.txt` |
| Final tests (eee2bc3) against the c49cb4d guard | 14 assertion failures, 0 errors | `output/red_final_tests_on_c49cb4d.txt` |
| Green at clean eee2bc3, modules run serially | 259 + 77 + 67 = **403 OK**; free RAM 1.23–1.29 GB | `output/modules_eee2bc3.txt` |
| `manage.py check`, `makemigrations --check --dry-run` at eee2bc3 | both exit 0, no changes | `output/check_and_migrations_eee2bc3.txt` |
| Replay of memos 96–103 (recorded replies, full time → funding → basis sequence) | identical to the c49cb4d replay in every field of every memo, with identical rule lists; against base c6c3d1b only memo 103's `base_scenario` and `upside_scenario` differ; idempotent and order-stable; every citation supplied; memo 103's base replay equals its stored memo | `output/replay_memos_96_to_103_eee2bc3.json`, `output/replay_summary.txt` |
| 75 carried probes | identical to c49cb4d apart from the head | `output/carried_probes_compare.txt` |
| Exact expected outputs | 110/110, 0 diff lines from c49cb4d | `output/exact_and_boundaries_eee2bc3.txt` |
| All reviewer examples, c8a0336 / c49cb4d / eee2bc3 | all nine kept at eee2bc3; both memo-103 repairs byte-identical across the three versions | `output/review_cases_c8a0336_c49cb4d_eee2bc3.txt` |
| Targeted mutations | **32/34 caught** by assertion failures; 0 execution errors; every restore SHA-checked; free RAM 1.40–1.82 GB | `output/mutations_all34_eee2bc3.txt`, `output/mutation_ram.txt` |

### Mutations

The set has 34 mutants: J1–J9, K1–K5 and K7–K11, L1 and L3–L9, and M0–M6.

- **Retired with their code:** L2 (citation after the clause) and L10 (vocabulary minus `_DENIAL`).
- **Re-anchored:** K7, L3, L4 and L5.
- **New, one per new protection:** M0 (no later-clause check at all), M1 (the contingency wordings), M2 (figure and
  time words), M3 (digits and quoted spans), M4 (later "-n't"), M5 (consequence denial) and M6 (the near-denial
  extras).

K5 and K8 survived again. The reasons are unchanged from `output-of1102-1103-c49cb4d/README.md`: they look
equivalent under the subject check and the clause-close check, though this is not proven.

## Limitations

**Can still rewrite a sentence that should be kept.** A clause after the dash, ";" or ":" that supposes the date while
naming neither the figures nor any time, in a connective no list holds, still gets the note. "— on the footing that
this holds" does (`output/limitation_probe_eee2bc3.txt`). The connective list and the figure and time words narrow
this, but do not close it.

**Under-correction**, where a sentence is left unchanged:

- **Later clauses:** any later clause mentioning the figures, a time or a page keeps the sentence, even a harmless
  one ("— the messages included").
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
