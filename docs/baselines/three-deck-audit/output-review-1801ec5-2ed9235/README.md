# Review of `1801ec5` addressed at `2ed9235`: OF-806's protections hold through the judgment rule; OF-805 splits only the company's affirmative statement

**Separate, additive correction evidence.** It edits nothing in `output-grounding-of805-807-1801ec5/` or any earlier evidence, grade, memo, raw response, ledger, frozen key or fixture. No model was called; recorded memos are replayed, not regenerated. **Correction evidence, not live acceptance.**

| Commit | What | Checks run at that commit |
|---|---|---|
| `1801ec5` | Reviewed head (OF-805/806/807 rules) | Reproduction of the reviewer's cases ([output/reviewer_cases_1801ec5.txt](output/reviewer_cases_1801ec5.txt)); red run of the new tests with `1801ec5`'s `basis_fidelity.py` ([output/red_run_on_1801ec5.txt](output/red_run_on_1801ec5.txt)) |
| `d31cf7b` | **Fix:** judgment dispatch; context split only for the company's own affirmative statement; regressions | `tests_output_fidelity` 137 OK; `tests_usage_basis` + `tests_funding_fidelity` 144 OK; replay of memos 96–100 ([d31cf7b json](output/replay_memos_96_to_100_d31cf7b.json)); 75 probes identical |
| `397776e` | An untestable hedge term (`to establish`) removed; control for the every-judging-clause dispatch | `tests_output_fidelity` 138 OK; mutations R1–R6 and Q1–Q15 ([R](output/mutations_R1-R6_397776e.txt), [Q](output/mutations_Q1-Q15_397776e.txt)): 20 of 21 caught, **Q7 survived** |
| `2ed9235` | Control for a condition after the company's own verb (tests only; `basis_fidelity.py` identical to `397776e`) | Q7 alone, caught; then **all 21 mutations again: 21 of 21 caught** ([output/mutations_final_all21_2ed9235.txt](output/mutations_final_all21_2ed9235.txt)); the three modules one after another (138 + 77 + 67 OK); `check`; `makemigrations --check`; replay of memos 96–100; 75 probes |

## Blocker 1: the judgment rule bypassed OF-806's protections

At `1801ec5`, `_judgment()` ran before `_referent_judgment()`. A cited "one or both figures" judgment resolves through its citations, and `_judgment()` replaced the whole sentence before the denial, contradicted-pair or clause-only protections could act.

| Input (`guard_basis_wording`) | `1801ec5` | `2ed9235` |
|---|---|---|
| "Nothing shows that one or both figures misrepresent activity [S2, S3]." | whole sentence → clarification (`basis_overstatement`) | **unchanged**, no rule |
| "One or both figures may misrepresent activity [S2, S3]." with a CONTRADICTED member | whole sentence → clarification (`basis_overstatement`) | **unchanged**, no rule |
| "These cannot be compared without clarification; one or both figures may misrepresent activity [S2, S3]." | whole sentence → clarification (`basis_overstatement`) | "These cannot be compared without clarification; how the figure stated without an explicit interval relates to the monthly figure needs clarification before either is relied on [S2, S3]." (`basis_referent_judgment`) |

**Fix:**
- **Dispatch:** when every clause that judges the figures is about "one or both figures" (`_referent_judged`), `_judgment()` leaves the sentence to `_referent_judgment()`, which applies the protections.
- **Unchanged:** a judgment in any other clause stays with `_judgment()`.
- **Memo-98 correction preserved:** "If the cumulative figure is being presented as a monthly figure, the key traction claim is materially overstated [C2, C3]." is still replaced whole (`basis_overstatement`), and so is a sentence mixing such a clause with a "one or both figures" clause. Both are controlled.

## Blocker 2: the context split acted on denied, narrated and hedged statements

| Input | `1801ec5` | `2ed9235` |
|---|---|---|
| "The company does not state 500M messages [S2, S3] (in a slide context headed 'Traction by Apr-16')." | S3 removed from the denied statement, and an affirmative "and separately 500M messages/month [S3] on page 12 (…)" appended | **unchanged** |
| "Pitch Deck Hunt lists 500M messages [S2, S3] (…)" | split under the narrator's verb | **unchanged by the basis guard**. Through the full sequence the merged narrator-provenance rule (#281) adds "(not Pitch Deck Hunt's: [S2, S3] are the company's own traction statements)", as before |
| "The company may state 500M messages [S2, S3] (…)" | split | **unchanged** |

**Fix:**
- **What may be split:** `_context_aside()` moves citations only when the moved citations follow a reporting verb whose subject is the company's own ("the company states", "… only that the company states", "the deck lists").
- **Clause conditions:** the clause must carry no denial word and no hedge ("may", "might", "appears", "reportedly", "whether", …).
- **Added controls,** through the full sequence and the basis helper:
  - "does not state";
  - "never states";
  - the narrator's listing;
  - "may state";
  - "appears to list";
  - no reporting verb;
  - the company's own verb with a later denial ("states that it has not verified …");
  - the company's own verb with a later hedge ("states what may be …");
  - the company's own verb inside a condition ("states, if the slide is read as one figure, …").
- **Still split:** the company's own affirmative statement, and memo 100's `business_model_analysis`.

## Red, then green

- **Red** ([output/red_run_on_1801ec5.txt](output/red_run_on_1801ec5.txt)): `Review1801ec5Tests` (full normalisation, time, funding and basis sequence on memo 100's payload) and `PipelineReview1801ec5Tests` (the memo writer, `intelligence_pipeline._generate_memo`), with `1801ec5`'s `basis_fidelity.py`. **12 assertion failures, 0 errors.** The memo-98 overstatement control and the company's own split passed.
- **Green at `2ed9235`** ([output/modules_after_restoration_2ed9235.txt](output/modules_after_restoration_2ed9235.txt)): `tests_output_fidelity` 138, `tests_usage_basis` 77 and `tests_funding_fidelity` 67, run one after another, all OK.
- **Checks:** `manage.py check` reports no issues; `makemigrations --check --dry-run` reports no changes ([output/check_and_migrations_2ed9235.txt](output/check_and_migrations_2ed9235.txt)).

## Replay and probes

- **Replay** ([output/replay_memos_96_to_100_2ed9235.json](output/replay_memos_96_to_100_2ed9235.json)): memos 96–100's recorded replies go through the full guard order with `f34e3a3`'s basis guard and with `2ed9235`'s.
  - **Memos 96–99:** no field differs.
  - **Memo 100:** exactly the three graded sentences (OF-805/806/807) differ. The `f34e3a3` replay reproduces memo 100's stored text in all 15 fields.
  - **Stability:** reversed items give the same output and changes, a second pass changes nothing, and citations stay in order.
  - **Against `1801ec5`:** every memo's results are **identical** (`d31cf7b` too). The new protections change no recorded output.
- **Probes** ([output/carried_probes_75_2ed9235.json](output/carried_probes_75_2ed9235.json)): the 75 carried probes for the whole-figure, arithmetic, parenthetical, funding and source-context protections give **identical** output and changes.

## Mutations

The runner ([output/scripts/mutate_r.py.txt](output/scripts/mutate_r.py.txt)) carries Q1–Q15 unchanged and adds R1–R6. Each mutant runs against the three affected modules (282 tests), and the original bytes are restored and SHA-256 checked after each. **A mutant counts as caught only by assertion failures**; errors are listed separately.

| ID | Mutation (integration, review of 1801ec5) | Final run at `2ed9235` |
|---|---|---|
| R1 | the judgment rule does not leave a "one or both figures" judgment to its own rule | caught, 4 failures, 0 errors (full sequence and memo writer) |
| R2 | one "one or both figures" judging clause is enough to bypass the judgment rule | caught, 1, 0 (mixed-clause control) |
| R3 | the context split does not need the company as subject | caught, 1, 0 (sub-case: the narrator's listing) |
| R4 | the context split does not need a reporting verb | caught, 1, 0 (sub-case: no reporting verb) |
| R5 | a denial in the clause does not keep the citations | caught, 1, 0 (sub-case: "states that it has not verified") |
| R6 | a hedge in the clause does not keep the citations | caught, 1, 0 (sub-case: "states what may be") |
| Q1–Q15 | the OF-805/806/807 mutations from `1801ec5` | all caught by assertion failures, 0 errors |

- **Q7 at `397776e`:** it survived, because the original condition control was also kept by the new reporting-verb requirement. `2ed9235` adds a control in which only the condition check keeps the sentence, and Q7 is caught there.
- **Final tally at `2ed9235`:** **21 of 21 caught, 0 crash-only, 0 survived**.
- **Restores:** every restore matched; [pre](output/pre_mutation_hashes.txt) and [post](output/post_mutation_hashes.txt) hashes are identical.
- **Run notes:**
  - The first R attempt failed to parse (a quote in a description) before any mutant was applied; it was fixed and rerun.
  - One final chunk exceeded the 10-minute foreground limit and finished in the background. The next chunk refused to start while its hash check failed, so the runs never overlapped, and the restore was verified before continuing.
- **Removed as untestable:** the `to establish` term in the new denial check had no case the denial words did not already keep, so it was removed in `397776e`.

## Memory

All steps ran serially. Free RAM was recorded before each mutation chunk and each gated run (1.27–2.22 GB; [output/free_ram_before_mutation_chunks.txt](output/free_ram_before_mutation_chunks.txt)), and gated steps would refuse below 1.2 GB. **The memory watchdog (`tools/memwatch.ps1`) was not running this round**, an omission.

## Remaining limitations and issues (not fixed here)

- **Pre-existing, seen while reproducing, preserved:**
  - `_judgment()` has no denial check of its own: "Nothing shows that the cumulative figure is overstated [C2, C3]." is replaced with the clarification at `f34e3a3`, `1801ec5` and `2ed9235` alike.
  - Changing it would alter the rule accepted since PR #284; it is reported, not changed.
- **Lexical scope:**
  - The context split recognises the listed reporting verbs, own subjects, denial words and hedges.
  - Other phrasings keep their citations, which is the conservative direction.
- **Carried from `1801ec5`:**
  - A separate page-12 mention before a context aside is not moved.
  - Slash citations ("[C3/S2]") are not recognised by `claim_context._REF`.
  - The OF-807 rule is lexical.
- **Not live:** live behaviour needs a post-merge sample after review.

**Status:** branch `fix/basis-grounding-of805-807`, unmerged and not deployed. RA-109 live acceptance, RA-108, RA-114 and overall hardening remain open.
