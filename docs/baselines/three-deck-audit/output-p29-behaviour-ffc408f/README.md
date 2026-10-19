# Mutation P29 caught by behaviour (review of `a4f55e5`)

**Separate, additive evidence. It supersedes P29's result in [`../output-figure-form-9d24d97/`](../output-figure-form-9d24d97/README.md)** (`FAILED (errors=1)`). It closes the gap recorded in [`../output-p34-correction-424dd36/`](../output-p34-correction-424dd36/README.md). Both folders are left unedited.

- **Application code:** unchanged since `9d24d97`.
- **Tests:** `ffc408f` adds tests only.
- **Branch:** unmerged, with no PR.

## Request

- Add regressions for "(500M/month/day)" and "(500ms)", through the full guard sequence and the basis helper. Both must stay unchanged with no rule fired. Keep the "(500M, 500M/month)" restatement control.
- Confirm the tests pass, then rerun only P29. It must fail assertions on these cases, with exceptions reported separately. Hash-check the restore.
- Run the affected module after the restore. No broad mutation rerun, no application change.

## Test (`ffc408f`)

`test_a_figure_token_that_is_not_one_whole_figure_keeps_the_sentence` in `zelda_api/tests_output_fidelity.py`:

| Input | Path | Expected |
|---|---|---|
| "The company states the message figures (500M/month/day) on the same slide [S2, S3]." | full sequence and helper | unchanged, no rule fired |
| "The company states the message figures (500ms) on the same slide [S2, S3]." | full sequence and helper | unchanged, no rule fired |
| "… (500M, 500M/month) …" | helper | **restated** (control) |

**Before the mutation:** the new test passes ([output/new_test_before_mutation.txt](output/new_test_before_mutation.txt)), and the module passes, 108 OK ([output/module_before_mutation.txt](output/module_before_mutation.txt)).

## P29 alone

P29 replaces `if not _FIGURE_TOKEN.fullmatch(word):` with `if False:`, so a figure token need not be one whole figure.

**Runner** ([output/mutation_P29.txt](output/mutation_P29.txt)), with the usual three labels (252 tests) and a hash-checked restore:

    P29 CAUGHT Ran 252 tests in 11.770s FAILED (failures=4, errors=1)

The runner reports only counts. For the per-case breakdown, the same mutant was applied once more by hand to the module, then restored from a byte copy and hash-checked ([output/mutation_P29_detail_module.txt](output/mutation_P29_detail_module.txt)):

| Kind | Test | Case |
|---|---|---|
| **Assertion failure** | `test_a_figure_token_that_is_not_one_whole_figure_keeps_the_sentence` | "(500M/month/day)", full sequence |
| **Assertion failure** | same | "(500M/month/day)", helper |
| **Assertion failure** | same | "(500ms)", full sequence |
| **Assertion failure** | same | "(500ms)", helper |
| Exception, reported separately | `test_an_additional_figure_keeps_the_sentence` | "($ 500M)": `AttributeError: 'NoneType' object has no attribute 'group'`. A lone "$" reaches `_figure_key` |

All four assertion failures are the new cases. Under the mutant, each sentence is restated from the cited 500M statements, discarding "/day" or the "s". The single exception is the one recorded at `9d24d97`. It is not counted as the behavioural kill.

**Restore:** the three guard and pipeline files are identical before and after: [output/pre_mutation_hashes.txt](output/pre_mutation_hashes.txt), [output/post_mutation_hashes.txt](output/post_mutation_hashes.txt). Free RAM before the run was 2.15 GB ([output/free_ram_before_mutation.txt](output/free_ram_before_mutation.txt)).

**After the restore:** `zelda_api.tests_output_fidelity` passes, 108 OK ([output/module_after_restoration.txt](output/module_after_restoration.txt)).

Commands: `output/scripts/mut_chunk_k.sh.txt` runs `mutate_j.py.txt`, whose P29 is unchanged from `mutate_g.py`.

## Scope

No broad mutation rerun, no application change, no live model run, no regenerated memo, no frozen artifact or earlier evidence edited, no merge or deployment, no paid-source Pass B. No credentials in this folder. RA-109 live acceptance, RA-108 and overall hardening remain open.
