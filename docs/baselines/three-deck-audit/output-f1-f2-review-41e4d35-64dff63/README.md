# F-2 correction, review of 41e4d35: each listed figure keeps its own metric and qualification

This folder adds correction evidence for branch `fix/funding-word-heading-scope-f1-f2`.
- **Earlier folders are unchanged:** `output-f1-f2-ff25de1/` (`2d0b0e9`), `output-f1-f2-review-ff25de1-41e4d35/` (`0a51dd9`) and the run evidence `f73bef5` stay as they were.
- **Nothing else was touched:** no memo was regenerated, no model was called, and no database or MFA was changed. The worker stayed stopped, and nothing was merged or deployed.
- **Validation status:** all validation is my own. None of it is independent review.
- **Still open:** RA-108, RA-109, RA-114, Q-2–Q-4 and overall acceptance. Successful browser access does not establish report-content acceptance.

## What the review found (41e4d35)

The reviewer reproduced two P2 blockers with memo 104's payload. Both sentences stay unchanged at the merged baseline `5120190`, and both were already rewritten at `ff25de1`.

1. **The heading rule changed the metric.** "140,000+ messages [S1]" was restated as "140 000+ bots [S1]". The check pooled words from every cited statement, so S2's "messages" passed on S1's figure.
2. **The heading rule erased a negative qualification.** "140,000+ bots with no messages [S1]" lost "with no messages". "with" and "no" come from S2's "with no explicit interval", and the denial check only read the subject, not the list.

## Commits

| Commit | Content |
|---|---|
| `64dff630fa4a18dd19352ddd882045e89b14ee87` | app and tests. **Validation head** (parent `0a51dd9`) |
| this commit | evidence only (this folder) |

**Code diff `41e4d35..64dff63`** ([output/diff_stat_41e4d35_64dff63.txt](output/diff_stat_41e4d35_64dff63.txt)):

| File | Lines |
|---|---|
| `zelda_api/basis_fidelity.py` | +51 / −1 (+5 of them docstring) |
| `zelda_api/tests_output_fidelity.py` | +38 |

The whole branch against 5120190 is 5 files, +837 / −2 ([output/diff_stat_5120190_64dff63.txt](output/diff_stat_5120190_64dff63.txt)). F-1 is unchanged since `ff25de1`.

## The change

**`_items_own_statements(written, statements)`** runs after the existing checks, on the list as written (slashes kept). The list is split at its citation groups, then each group's text is split into figures at ", ", " and " and " or ". A digit-grouping comma such as "140,000+" is never a split point. Rules:
- Each figure must be one of **its own group's** statements, word for word from the figure on. The figure value is compared after digit grouping, and the "+" may be written or left out.
- A figure may **stop early**, before the rest of its statement ("500M messages" for "500M messages with no explicit interval"). The restatement gives the rest back from the statement itself.
- A figure may **not take another statement's noun or qualification.** It also may not put any word before the figure, or leave out its noun.
- Every ref of a group must be written, and nothing may follow the last group.
- Anything else keeps the sentence unchanged, for review.

Memo 104's sentence, the other F-2 corrections and F-1 are unchanged. Every output shared with the `41e4d35` exact run is identical.

## Validation at 64dff63

The committed content is the validated content: the working copy's hashes were checked after every run, and `git diff --quiet 64dff63` on the three guard and test files is clean ([output/committed_hashes.txt](output/committed_hashes.txt); the working copy is CRLF under `core.autocrlf`, the blobs are LF). Outputs recording `head 0a51dd9` were produced from this working copy just before the commit.

**The new tests fail on `41e4d35`.** I put `41e4d35`'s `basis_fidelity.py` back with the final tests in place ([output/red_on_41e4d35.txt](output/red_on_41e4d35.txt)):
- 7 assertion failures: the two reproductions, their comma forms, and three variants;
- 1 error: the new helper doesn't exist at `41e4d35`;
- the fixed file was then restored and checked against the hashes.

**The reviewer's cases and variants** ([output/review_cases_fix.txt](output/review_cases_fix.txt); exact text for all three rule versions in [output/review_cases_fix.json](output/review_cases_fix.json)):

| Case | 5120190 | 41e4d35 | 64dff63 |
|---|---|---|---|
| R1 "140,000+ messages [S1]" (metric) | kept | **rewritten** | kept |
| R2 "140,000+ bots with no messages [S1]" (qualification) | kept | **rewritten** | kept |
| W1, W2: R1 and R2 in the comma form ("The company states …") | kept | **rewritten** | kept |
| W3 "500M bots [S2]" (metric on page 10's other figure) | kept | **rewritten** | kept |
| W4 "140,000+ bots with no explicit interval [S1]" (another statement's qualifier) | kept | **rewritten** | kept |
| W6 "140,000+ bots [S1, S2]" (S2 cited, not written) | kept | **rewritten** | kept |
| W5 two figures under [S1]; W7 words after the last group | kept | kept | kept |
| K0 memo 104's stored sentence; K1–K9 the `HEADING_FIXED` corrections | kept (defect) | corrected | corrected, same output as 41e4d35 |

All nine preservation cases are now in `HEADING_KEPT`. There is also a unit test of the per-figure check, and a control for a written fact outside the pair (see H8 below).

**Tests**, run serially with free RAM of 1.18–1.90 GB before each run, above the 0.9 GB floor ([output/suite_ram.txt](output/suite_ram.txt)):

| Module | Result |
|---|---|
| `zelda_api.tests_output_fidelity` | 283 OK (24 new since 5120190) |
| `zelda_api.tests_usage_basis` | 77 OK |
| `zelda_api.tests_funding_fidelity` | 67 OK |
| `zelda_api.tests_claim_context_dates` | 25 OK |

That is **452 OK** in total.

**Frozen memos 96–104 through the full guard order** ([output/replay_memos_96_to_104_fix.json](output/replay_memos_96_to_104_fix.json)):
- the output is identical to the `41e4d35` replay, apart from the head SHA and the working-tree flag;
- memos 96–103 are identical to the 5120190 replay;
- memo 104 differs only in `business_model_analysis` and `questions_for_management`.

**Preservation controls:**
- **Carried probes:** all 75 are identical to 9fd0f35 ([output/carried_probes_compare.txt](output/carried_probes_compare.txt)).
- **Exact before/after:** 77 cases ([output/exact_before_after_fix.json](output/exact_before_after_fix.json)): the 68 from the `41e4d35` run plus the 9 new controls.
  - The same 19 cases differ from 5120190 as before.
  - The 68 shared outputs are identical to the `41e4d35` run.
  - All 9 new controls are byte-identical to their input.
  - Every case is idempotent and independent of item order.

## Targeted mutations

Source: [output/mutations.txt](output/mutations.txt), run on the final bytes. The 19 earlier mutants plus 6 new ones were run one at a time against `tests_output_fidelity` and `tests_funding_fidelity` (350 tests), with the original bytes restored and hashed after each. A mutant counts as caught only through assertion failures.

| ID | Mutant | Result |
|---|---|---|
| **P1** | per-figure check not applied (the review's two cases) | caught, 7 |
| **P2** | only the figure compared: any noun or qualification passes | caught, 5 |
| **P4** | a cited ref need not be written | caught, 2 |
| **P5** | words may follow the last group | caught, 1 |
| **P6** | the join splits "140,000+" at its comma | caught, 15 |
| **P3** | ownership pooled across all cited statements | **survived: equivalent** (below) |
| F1, F2, H1, H5, H7, H9–H11, S2, S3, O1, O2 | as in the earlier round | caught |
| H8 | refs outside the pair may move | caught, 1. It survived the first run of this round; see below |
| H2, H3, H4, O3 | as in the earlier round | survived: equivalent |
| H6, S1 | the shared-word check, and the slash-form call | **survived: newly equivalent** (below) |

**18 of 25 caught.** The 7 survivors are explained here:
- **H8 (fixed in this round).** The old S9 control cited "40 staff" without writing it, so the new rule's "every cited ref written" check rejected it before the pair check was reached. I added a control that writes the outside fact ("… [S7, S8] and 40 staff [S9]"). H8 is now caught; the single re-run is in [output/mutations_h8_rerun.txt](output/mutations_h8_rerun.txt), and the full final run above includes it.
- **P3.** A figure owned only by a statement outside its group adds that outside ref to the group's written set. The "every ref written, and no other" equality then fails anyway, so no input tells P3 apart.
- **H6 and S1.** Every figure must now be a word-for-word prefix of its own statement, compared token by token. That rejects everything the shared-word check rejected (another fact, figure, aside, denial, hedge, "+", "~"). It also rejects every unstated "noun/interval", because "bots/month" is not "bots". The slash-form helper's own unit test still catches S2 and S3.
- **H2, H3, H4, O3.** These are unchanged from the earlier round: the stricter subject checks make them redundant.

I kept the redundant checks as defence in depth. They can be removed in a follow-up if preferred.

## Reproduce

Scripts are in [output/scripts/](output/scripts/): `review_cases2.py`, `t.sh`, `py.sh`, `mutate_f12.py`, `replay.py`, `carried_probe.py` with `cmp_probes.py`, and `exact.py`. The scripts contain only the CI placeholder settings, no credentials.
