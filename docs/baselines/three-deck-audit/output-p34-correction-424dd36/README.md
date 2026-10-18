# Mutation P34 corrected (review of `424dd36`)

**Separate, additive evidence. It supersedes P34's result in [`../output-figure-form-9d24d97/`](../output-figure-form-9d24d97/README.md)**, which is left unedited. No application code changed: application head `9d24d97`, branch head `424dd36` when this was run. The branch is **unmerged**, with no PR.

## Review

| Item | Value |
|---|---|
| Decision | The code fix at `9d24d97` passes. One mutation-evidence correction remains |
| Independent execution | The reviewer ran 101 guard and memo-replay tests in an isolated harness: all passed. The committed logs show 1,397 tests passing |
| Finding | P34 removed a regex capture group that `_stated_forms()` still reads. Every use raised `IndexError: no such group`, 85 errors in total, so it showed a crash rather than the intended behavioural check |
| Required | Correct P34, rerun that mutation, and record that the correction supersedes the crashing result. No application change or broad validation rerun |

## Superseded result

`../output-figure-form-9d24d97/output/mutations_9d24d97_chunk15.txt` and `mutations_targeted_new_and_reanchored.txt`:

    P34 CAUGHT Ran 251 tests in 9.708s FAILED (errors=85)

The mutant replaced `(?:/([a-z]+)|\s+[a-z]+/([a-z]+))?` with `(?:/([a-z]+))?`. That left `match.group(4)` naming a group that no longer exists. The runner counts errors as caught, so this was recorded as caught.

## Corrected P34

This is the reviewer's verified replacement, on the line `value, interval = match.group(1).replace(',', ''), match.group(3) or match.group(4)`:

| | |
|---|---|
| Old | `match.group(3) or match.group(4)` |
| New | `match.group(3)` |

The regex is unchanged. Only an interval stated on a figure's noun ("500M messages/month") stops being read, so that statement no longer states "500M/month".

**Result** ([output/mutation_P34_corrected.txt](output/mutation_P34_corrected.txt)):

    P34 CAUGHT Ran 251 tests in 11.555s FAILED (failures=11)

The run had **11 assertion failures and 0 errors**. The failing tests include:
- the positive controls: `test_numbers_and_parentheticals_do_not_end_the_clause`, and the "(500M, 500M/month)" and 140,000 controls in `test_a_figure_qualification_or_denominator_no_statement_gives_keeps_the_sentence` and `test_a_further_unknown_figure_keeps_the_sentence`;
- memo 99's repairs: `test_the_stored_memo_carries_the_repairs` and `test_only_the_expected_rules_fired`;
- the placement tests: `test_of705_each_fact_keeps_its_own_page_and_context`, `test_every_placed_citation_supports_its_page_and_context` and `test_a_basis_aside_is_superseded_by_the_restated_clarification`.

The runner shortens the list, so the full count is the 11 in the summary line. The reviewer's harness saw 2 failures because it runs 101 tests. This run uses the usual three labels (`tests_output_fidelity`, `tests_funding_fidelity`, `tests_usage_basis`), 251 tests.

The mutation set is therefore **73 of 73 caught, with P34 now caught by assertions**.

The restore was SHA-256 checked, and the three guard and pipeline files are identical before and after: [output/pre_mutation_hashes.txt](output/pre_mutation_hashes.txt), [output/post_mutation_hashes.txt](output/post_mutation_hashes.txt). It ran in the foreground with 2.16 GB free ([output/free_ram_before_mutation.txt](output/free_ram_before_mutation.txt)).

Commands: `output/scripts/mutate_j.py.txt` carries `mutate_i.py` with only P34 replaced. It is run by `mut_chunk_j.sh.txt`.

## A second error-only result, recorded and not changed here

A check of all 73 results for kills without an assertion failure found one more: **P29** (a figure token need not be whole), recorded as `FAILED (errors=1)` at `9d24d97`.
- At `2465791` it also had an assertion failure ("500M+500M" was read as 500M).
- At `9d24d97` the complete-form check already keeps "500M+500M", because it reads as "500m+", which no statement states. That leaves only the crash on a lone "$" (`_figure_key` gets no match).
- The whole-token check still has behavioural cases no test pins: "(500M/month/day)" would pass as "500M/month", and "(500ms)" as "500M".

This review scoped the correction to P34, so P29 is left as recorded. A test-only regression for those inputs would let P29 fail an assertion.

## Isolation

Test databases only. No network, provider or model call; no memo regenerated; no frozen artifact or earlier evidence edited; no deployment; no paid-source Pass B. No credentials in this folder. RA-109 live acceptance, RA-108 and overall hardening remain open.
