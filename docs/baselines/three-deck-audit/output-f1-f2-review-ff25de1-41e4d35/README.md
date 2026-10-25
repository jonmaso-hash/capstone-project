# F-2 correction, review of ff25de1: unsupported intervals and other speakers stay unchanged

This folder adds correction evidence for branch `fix/funding-word-heading-scope-f1-f2`.
- **Earlier folders are unchanged:** `output-f1-f2-ff25de1/` (`2d0b0e9`) and the run evidence `f73bef5` stay as they were.
- **Nothing else was touched:** no memo was regenerated, no model was called, and no database or MFA was changed. The worker stayed stopped, and nothing was merged or deployed.
- **Validation status:** all validation is my own. None of it is independent review.
- **Still open:** RA-108, RA-109, RA-114, Q-2–Q-4 and overall acceptance.

## What the review found (ff25de1)

The reviewer reproduced two F-2 regressions. The merged baseline (5120190) keeps all three examples unchanged; `ff25de1` rewrote them.

1. **An unsupported interval was erased.** "140,000+ bots/month [S1]" became "140 000+ bots [S1]".
   - The rule turned every word/word slash into a space before its word check.
   - So "month", taken from page 12's statement, licensed "bots/month".
2. **Other speakers triggered the rewrite.** Both "An analyst's interpretation of the company's traction figures — …" and "An analyst describes the company's traction figures — …" were rewritten. Any mention of "company" passed the source check.

The reviewer also confirmed that F-1 passed their targeted checks.

## Commits

| Commit | Content |
|---|---|
| `41e4d3513f946aa71ed612f31ed9da83b802b462` | app and tests. **Validation head** (parent `2d0b0e9`) |
| this commit | evidence only (this folder) |

**Code diff `ff25de1..41e4d35`** ([output/diff_stat_ff25de1_41e4d35.txt](output/diff_stat_ff25de1_41e4d35.txt)):

| File | Lines |
|---|---|
| `zelda_api/basis_fidelity.py` | +46 / −5 |
| `zelda_api/tests_output_fidelity.py` | +30 |

The whole branch against 5120190 is 5 files, +749 / −2 ([output/diff_stat_5120190_41e4d35.txt](output/diff_stat_5120190_41e4d35.txt)). F-1 is unchanged since `ff25de1`.

## The change

- **`_slash_forms_stated(text, statements)`** runs before any slash is treated as a word gap.
  - Every `<figure> <noun>/<interval>` in the list must be a form that one cited statement states for that same figure. "500M messages/month" passes because page 12's statement says exactly that.
  - These keep the sentence unchanged: "140,000+ bots/month", "500M messages/week", "500M messages/bots", "250M messages/month", and a slash pair with no figure.
  - A "+" that the statement leaves out may still be written.
- **`_OWN_FIGURES`, the appositive list's subject (dash form).** The subject must be the company's own figures, named as the clause's last noun phrase:
  - accepted forms: "the company's self-reported traction figures", "the company's unverified traction figures", "the self-reported figures";
  - optionally after a short lead-in, made only of allowlisted words and ending in a linking verb, such as memo 104's "The only indicators of commercial activity are";
  - any other lead-in keeps the sentence. Examples: an analyst's interpretation, reading or view; "investors think …"; "as an analyst summarises them"; another firm's comparison.
  - The comma form already required "the company" (or the deck, etc.) right before its reporting verb. That is unchanged.
- **Unchanged:** memo 104's corrected sentence, the other F-2 corrections, and F-1. Every output shared with the `ff25de1` exact run is identical.

## Validation at 41e4d35

**The new tests fail on `ff25de1`.** I put `ff25de1`'s `basis_fidelity.py` back with the new tests in place ([output/red_on_ff25de1.txt](output/red_on_ff25de1.txt)):
- 10 assertion failures: the reviewer's three cases and seven variants;
- 1 error: the new helper doesn't exist at `ff25de1`;
- the fixed files were then restored and checked against [output/guard_hashes_41e4d35.txt](output/guard_hashes_41e4d35.txt).

**The reviewer's cases and variants** ([output/review_cases_41e4d35.txt](output/review_cases_41e4d35.txt); exact text in [output/review_cases_ff25de1.json](output/review_cases_ff25de1.json) and [output/review_cases_41e4d35.json](output/review_cases_41e4d35.json)):

| Case | 5120190 | ff25de1 | 41e4d35 |
|---|---|---|---|
| R1 "140,000+ bots/month [S1]" | kept | **rewritten** | kept |
| R2 "An analyst's interpretation of the company's …" | kept | **rewritten** | kept |
| R3 "An analyst describes the company's …" | kept | **rewritten** | kept |
| V2 bots/month (comma form); V4 messages/bots; V5 analyst reads; V6 analyst's view; V7 investors think; V8 as an analyst summarises; V9 another firm's comparison | kept | **rewritten** | kept |
| V1 "500M messages/week"; V3 "140,000+/month bots" | kept | kept | kept |
| K1 memo 104's sentence; K2 self-reported; K3 unverified; K4 "The company states …" | kept (defect) | corrected | corrected, same output as ff25de1 |

All 12 preservation cases are now test cases in `HEADING_KEPT`. There is also a unit test of the slash-form check.

**Tests**, run serially with the memory watchdog at 1500 MB and free RAM of 1.99–2.13 GB before each run ([output/suite_ram.txt](output/suite_ram.txt)):

| Module | Result |
|---|---|
| `zelda_api.tests_output_fidelity` | 282 OK (23 new since 5120190) |
| `zelda_api.tests_usage_basis` | 77 OK |
| `zelda_api.tests_funding_fidelity` | 67 OK |
| `zelda_api.tests_claim_context_dates` | 25 OK |

That is **451 OK** in total.

**Frozen memos 96–104 through the full guard order** ([output/replay_memos_96_to_104_41e4d35.json](output/replay_memos_96_to_104_41e4d35.json)):
- memos 96–103 are identical to the 5120190 replay;
- memo 104 differs only in `business_model_analysis` and `questions_for_management`, both identical to the `ff25de1` replay;
- for every memo, reversed item order gives the same result, a second pass changes nothing, and every citation names a supplied ref.

**Preservation controls:**
- **Carried probes:** all 75 are identical to 9fd0f35 ([output/carried_probes_compare.txt](output/carried_probes_compare.txt)).
- **Exact before/after:** 68 cases ([output/exact_before_after_41e4d35.json](output/exact_before_after_41e4d35.json)): the 56 from the `ff25de1` run plus the 12 new controls.
  - The same 19 cases differ from 5120190 as before: memo 104's two sentences, six longer-word tails and nine F-2 corrections.
  - All 12 new controls are byte-identical to their input.
  - Memo 103's graded sentences and the five recorded controls are unchanged.
  - Everything is idempotent and independent of item order.

## Targeted mutations

Source: [output/mutations.txt](output/mutations.txt). The 13 earlier mutants plus 6 new ones were run one at a time against `tests_output_fidelity` and `tests_funding_fidelity` (349 tests), with the original bytes restored and hashed after each. A mutant counts as caught only through assertion failures.

| ID | Mutant | Result |
|---|---|---|
| F1, F2 | tail unbounded / only "reported" bounded | caught, 16 / 10 failures |
| H1 | heading rule not applied | caught, 15 |
| H5–H11 | mid-clause, other content, all-or-none, outside-pair refs, pointer, closing dash, page-12 scope | caught, 1–14 each |
| **S1** | slash-form check not applied (the review's R1) | caught, 3 |
| **S2** | interval checked without its figure and noun | caught, 4 |
| **S3** | slash pair with no figure passes | caught, 1 |
| **O1** | own-figures subject check not applied (the review's R2, R3) | caught, 7 |
| **O2** | any lead-in before the linking verb | caught, 1 |
| H2, H3, H4, O3 | the earlier subject check (narrator, attribution, own source), its denial/hedge part, the condition check, and the own-source requirement inside `_OWN_FIGURES` | **survived: equivalent** (see below) |

**15 of 19 caught.** The four survivors are now redundant with the stricter new checks, so no input distinguishes them:
- **Dash form:** the subject must be the allowlisted own-figures phrase. It can't hold a narrator, a speaker, a denial, a hedge or a leading "if".
- **Comma form:** the subject must be exactly "the company" (or the deck, etc.) right before the reporting verb.
- **O3:** the older own-source check, which still runs, refuses "The figures — …".

I kept these checks as defence in depth rather than delete them. This is the same treatment as K5/K8/L6 in an earlier round.

## Reproduce

Scripts are in [output/scripts/](output/scripts/): `review_cases.py`, `t.sh`, `py.sh`, `mutate_f12.py`, `replay.py`, `carried_probe.py` with `cmp_probes.py`, and `exact.py`.
