# F-2 review of 64dff63: H6 was not equivalent; an unstated "+" is now pinned

This folder adds evidence for branch `fix/funding-word-heading-scope-f1-f2`.
- **Earlier evidence is unchanged and still the raw record:** `output-f1-f2-ff25de1/` (`2d0b0e9`), `output-f1-f2-review-ff25de1-41e4d35/` (`0a51dd9`), `output-f1-f2-review-41e4d35-64dff63/` (`94e6f59`) and the run evidence `f73bef5`. Where this folder corrects them, it says so here; their files were not edited.
- **Nothing else was touched:** no memo was regenerated, no model was called, and no database or MFA was changed. The worker stayed stopped, and nothing was merged or deployed.
- **Validation status:** all validation is my own. None of it is independent review.
- **Still open:** RA-108, RA-109, RA-114, Q-2–Q-4 and overall acceptance. Successful browser access does not establish report-content acceptance.

## What the review found (64dff63)

1. **H6 is not an equivalent mutant.** With memo 104's evidence, the committed code keeps this sentence byte for byte:

   > The company's self-reported traction figures — 140,000+ bots [S1] and 500M+ messages or 500M messages/month [S2, S3] — contextualised under a slide heading 'Traction by Apr-16'.

   Under H6, which bypasses `_placing_words(listed, vocabulary, False)`, the heading rule rewrites it and drops the unsupported "+". The per-figure helper compares values without their "+". The complete-figure vocabulary check is the one that refuses a "+" that no cited statement states. So the two checks are not redundant, and `94e6f59` was wrong to call H6 equivalent.
2. **Reproduction scripts could not be retrieved under the names the READMEs gave.** `output/scripts/mutate_f12.py` returned 404 at `94e6f59`.

## Corrections to earlier evidence

- **`94e6f59` (`output-f1-f2-review-41e4d35-64dff63/README.md`).**
  - Its H6 line ("survived: newly equivalent") is **wrong**, and so is the argument that the per-figure check "rejects everything the shared-word check rejected". That argument missed the "+".
  - Its total ("18 of 25 caught") was a correct count of that run, because no test pinned the "+". It does not describe the protection.
  - Its raw `output/mutations.txt` is kept as recorded.
- **All three earlier READMEs list script names without the `.txt` suffix the files are committed with**, so every listed script path 404s. No script is missing: all 26 are committed, at `<name>.txt`. [output/scripts_manifest.txt](output/scripts_manifest.txt) maps each name a README promises to its committed path and blob. For `94e6f59`, the committed copies are byte-identical to the scripts that produced its outputs.

## Commits

| Commit | Content |
|---|---|
| `7fe189b7d1056529f1998d2c733f85d6c0d17347` | tests only. **Validation head** (parent `94e6f59`) |
| this commit | evidence only (this folder) |

There is **no application change.** `basis_fidelity.py` and `funding_fidelity.py` are the same blobs at `64dff63` and `7fe189b` ([output/committed_hashes.txt](output/committed_hashes.txt)). The vocabulary check that keeps these sentences stays in place as working protection.
- **Diff `64dff63..7fe189b`:** `zelda_api/tests_output_fidelity.py` +8 ([output/diff_stat_64dff63_7fe189b.txt](output/diff_stat_64dff63_7fe189b.txt)).
- **Whole branch against 5120190:** 5 files, +845 / −2 ([output/diff_stat_5120190_7fe189b.txt](output/diff_stat_5120190_7fe189b.txt)).

## The change

Four integration preservation controls in `HEADING_KEPT`. They run through `replay()`, the full time → funding → basis guard order, with `memo104_payload()`:

| Control | Form | Path |
|---|---|---|
| the reviewer's sentence, byte for byte (checked: [output/scripts/literal.py.txt](output/scripts/literal.py.txt)) | dash | appositive subject (`_OWN_FIGURES`) |
| the same list after "The company states" | comma | reporting verb (`_OWN_SUBJECT`); distinct from the dash form |
| "500M+ messages/month [S3]", a "+" on page 12's figure | dash | as above |
| the same, after "The company states" | comma | as above |

## Validation at 7fe189b

The validated content is the committed content. `git diff --quiet 7fe189b` on the guard and test files was clean before and after the whole chain, and the working-copy hashes were checked after every mutant ([output/committed_hashes.txt](output/committed_hashes.txt)).

**Reproduction through the full replay** with memo 104's payload ([output/repro_h6_7fe189b.txt](output/repro_h6_7fe189b.txt), exact text in [output/repro_h6_7fe189b.json](output/repro_h6_7fe189b.json)):
- **Committed guards** (loaded from git): all four sentences are kept byte for byte, with no rule fired.
- **H6** (applied in memory to the committed source, using the harness's own anchor): all four are rewritten by `basis_heading_scope`, and the "+" is gone. For example: "… 140 000+ bots [S1] and 500M messages with no explicit interval [S2] on page 10, under 'Traction by Apr-16', and separately 500M messages/month [S3] on page 12 (…)".
- **The other six survivors:** all four are kept.

**The actual H6 mutant through the harness.** The file was mutated on disk, then restored and hash-checked ([output/mutations_h6_check.txt](output/mutations_h6_check.txt)):
- **Caught**, with 4 assertion failures in `test_controls_are_kept`. They are exactly the four new controls.
- On the committed application, the same controls pass.

**Tests**, run serially with free RAM of 1.93–2.21 GB before each run ([output/suite_ram.txt](output/suite_ram.txt)):

| Module | Result |
|---|---|
| `zelda_api.tests_output_fidelity` | 283 OK (the controls are sub-cases of an existing test, so the count is unchanged) |
| `zelda_api.tests_usage_basis` | 77 OK |
| `zelda_api.tests_funding_fidelity` | 67 OK |
| `zelda_api.tests_claim_context_dates` | 25 OK |

That is **452 OK** in total.

**Other checks:**
- **Frozen memos 96–104** ([output/replay_memos_96_to_104_7fe189b.json](output/replay_memos_96_to_104_7fe189b.json)): identical to the `41e4d35` and `64dff63` replays apart from the head SHA. Memos 96–103 are unchanged against 5120190, and memo 104 changes only `business_model_analysis` and `questions_for_management`.
- **Carried probes:** all 75 are identical to 9fd0f35 ([output/carried_probes_compare.txt](output/carried_probes_compare.txt)).
- **Exact before/after:** 81 cases, the 77 from `64dff63` plus the 4 new controls ([output/exact_before_after_7fe189b.json](output/exact_before_after_7fe189b.json)).
  - The same 19 cases differ from 5120190.
  - The 77 shared outputs are identical to the `64dff63` run.
  - The 4 new controls are byte-identical to their input.
  - Every case is idempotent and independent of item order.
- **Earlier review cases:** identical to the `64dff63` run ([output/review_cases_7fe189b.txt](output/review_cases_7fe189b.txt)).

## Targeted mutations

Source: [output/mutations.txt](output/mutations.txt). The same 25 mutants as `94e6f59` were run one at a time against `tests_output_fidelity` and `tests_funding_fidelity` (350 tests), with the original bytes restored and hashed after each. The final hashes match the pre-run bytes.

**19 of 25 caught** (at `94e6f59`: 18 of 25, with H6 surviving). H6 is now caught by 4 failures. Every other result is the same as at `94e6f59`.

**The six survivors: no counterexample found, not proven equivalent.** These are H2, H3, H4, O3, P3 and S1. Because the H6 claim rested on reasoning that missed a case, I searched for counterexamples instead of re-asserting equivalence ([output/diff_survivors_20000_7fe189b.txt](output/diff_survivors_20000_7fe189b.txt), [json](output/diff_survivors_20000_7fe189b.json)). The search:
- generated 20,000 distinct heading-list sentences, seeded and deterministic, with memo 104's payload, in both forms;
- varied the subjects (own, other speaker, narrator, hedge, denial, condition), values (with or without "+", spaced or grouped digits, "~", other figures), nouns and intervals, qualifiers, asides, citation groupings and endings;
- ran every sentence through the full guard order, under the committed rule and under each survivor applied in memory.

Results:
- **The committed rule rewrote 570 sentences**, so the rule's paths were reached.
- **The six survivors: 0 differences each.**
- **H6: 101 differences** ([output/diff_survivors_h6_classes.txt](output/diff_survivors_h6_classes.txt)). The committed rule keeps all 101.
  - In 80 of them, H6 drops a "+" on a 500M figure that no statement states (the reviewer's defect class). 3 of those 80 also use the spacing below.
  - In the other 21, the only difference is that S1's figure is written with the statement's own digit spacing ("140 000+ bots [S1]"), which H6 would restate. That is a conservative missed correction, not a harmful rewrite: the shared-word check reads "140 000+" as two tokens. I left it unchanged, because this task preserves the application's protection and asks for no new correction.

The search makes the six survivors credible as equivalent within the generated space. It is not a proof. I kept them as defence in depth.

## Reproduce

Scripts are committed under [output/scripts/](output/scripts/) **with a `.txt` suffix**, at exactly these paths:
- `output/scripts/repro_h6.py.txt`: the reproduction, at the committed guards, the working tree and each survivor.
- `output/scripts/diff_survivors.py.txt`: the differential search.
- `output/scripts/literal.py.txt`: checks that the reviewer's sentence is a control byte for byte.
- `output/scripts/mutate_f12.py.txt`: the mutation harness.
- `output/scripts/review_cases2.py.txt`, `output/scripts/replay.py.txt`, `output/scripts/carried_probe.py.txt`, `output/scripts/cmp_probes.py.txt`, `output/scripts/exact.py.txt`.
- `output/scripts/t.sh.txt` (test runner) and `output/scripts/py.sh.txt` (script runner). These contain only the CI placeholder settings, no credentials.

After pushing, each of these paths and every path in the manifest was checked against the remote branch ([output/scripts_retrievable.txt](output/scripts_retrievable.txt)).
