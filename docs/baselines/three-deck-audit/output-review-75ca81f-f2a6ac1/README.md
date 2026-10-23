# Review of 75ca81f / 0781baf: denials, questions and separately grouped condition citations

**Correction evidence only. This is not live acceptance.** No model call was made, memo 102 was not regenerated and Q1–Q7 were not repeated. This folder is additive: it changes nothing in [`../output-of1003-1004-0781baf/`](../output-of1003-1004-0781baf/README.md), in the memo-102 run (`6d131f5`), in its grade (`f2a282f`) or in any recorded memo.

- **Branch:** `fix/basis-context-identity-of1003-1004`, base `main` at `d0bad8f`.
- **Commits in this round:**
  - `b4fa23e69cde325fec618c3877b37f2c038833d8`: application and tests;
  - `f2a6ac1a279161d6f01867c2cfc8a29a0df97887`: tests only, the final head for validation.
- **Guard bytes at both commits:** `zelda_api/basis_fidelity.py` sha256 `4a627720af499952f031279bf9e90714a85cf422a52b2090dddb879eb18fcbd9`.

## The two regressions, at 0781baf and now

The table shows the full post-generation sequence on memo 102's payload. The outputs are in [output/review_probe_0781baf.txt](output/review_probe_0781baf.txt) and [output/review_probe_f2a6ac1.txt](output/review_probe_f2a6ac1.txt).

| Input | At `0781baf` | At `f2a6ac1` |
|---|---|---|
| Page 10 does not state '500M messages/month' [C3, S2]. | … [C2, S3]. (switched to page 12) | kept |
| If the traction figures [S1, S2] and [S3] are taken at face value under the 'Traction by Apr-16' framing, the picture changes. | "… [S1, S2] and [] are taken …; the deck separately states …" | kept |

## What changed (`b4fa23e`)

1. **Identity rule (`_states_as_cited`, `_clause_bounds`).** A citation group, whether after one figure or as a "vs" operand, is corrected only in a clause that affirms the figure.
   - **Kept unchanged:** questions (`_asks`), "whether" clauses, and clauses with a denial word. The denial words are `_DENIAL` plus "omit(s/ted)", "absent", "missing", "nowhere" and "n't" forms.
   - **Kept unchanged:** clauses that name a page or source context other than the named side's own. For example, "Page 10 states '500M messages/month' [C3, S2]" cites page 10 as what page 10 says.
   - **Kept unchanged:** for a "vs", only another pair's pages or contexts; both sides' own pages are allowed.
   - **Clause boundaries:** a clause stops at ";", ":", a dash, a clause-linking comma (", but", ", while", …) and an unmatched parenthesis. So an affirmative clause beside a denied one, or inside a parenthesis, is still corrected.
2. **Condition rule.** If a citation group would hold only moved refs ("[S1, S2] and [S3]", "[S1, S2], [S3]"), no faithful structural rewrite exists. The sentence is kept, and no "[]" or dangling connector is produced. A moved ref that shares its group with a ref that stays ("[S1] and [S2, S3]") is still moved.

Memo 102's three corrections are unchanged:
- `base_scenario`: S3 is moved out with the clarification;
- `open_concerns`: [C3, S3] → [C2, S3];
- `business_model_analysis`: "vs [C2, S3]".

## Validation

| Check | Result |
|---|---|
| Red | Final tests (`f2a6ac1`) against `0781baf`'s guard: **18 assertion failures, 0 errors**, 230 tests ([output/red_run_final_tests_on_0781baf.txt](output/red_run_final_tests_on_0781baf.txt)). The `b4fa23e` tests also give 18/0 ([output/red_run_b4fa23e_tests_on_0781baf.txt](output/red_run_b4fa23e_tests_on_0781baf.txt)). |
| Green at `f2a6ac1` | `tests_output_fidelity` 230 OK, `tests_usage_basis` 77 OK, `tests_funding_fidelity` 67 OK: **374 OK** ([output/modules_f2a6ac1.txt](output/modules_f2a6ac1.txt)). `check` exit 0 and `makemigrations --check --dry-run` exit 0 ([output/check_and_migrations_f2a6ac1.txt](output/check_and_migrations_f2a6ac1.txt)). |
| New controls (`Review75ca81fTests`, 6 tests) | Kept: the review's denial; a denial alone; "omits"; another page named alone; another source context named alone; a question about a page; "whether" with and without a page; a question alone; a "vs" in a denial; a list of both figures with no page. Corrected: a ", but" clause after a denial; a denial after ", but"; "the slide on page 12"; a parenthesis with words around it on both sides. Condition: the review's case and a comma-separated variant kept, "[S1] and [S2, S3]" corrected. Every case checked for a second pass, reversed item order, no "[]" and every citation a supplied ref. The corrected group cites page 12's [C2, S3]. A second pair (C7/C8, S7/S8, pages 7/8) is handled alike. |
| Replay of memos 96–102 | Raw replies from committed evidence, full guard sequence, base `d0bad8f` vs `f2a6ac1` ([output/replay_memos_96_to_102_f2a6ac1.json](output/replay_memos_96_to_102_f2a6ac1.json)). Every memo's result is **identical to the `0781baf` replay**: memos 96–101 have 0 differing fields, and memo 102 differs from base in exactly the three corrected fields. All memos are idempotent and order-stable, and every citation is supplied. The recorded memos are not touched. |
| Carried probes | 75/75 identical to `0781baf` apart from `head` ([output/compare_probes_0781baf_vs_f2a6ac1.txt](output/compare_probes_0781baf_vs_f2a6ac1.txt)). |
| Exact outputs | **110/110** exact; 0 diff lines against `0781baf` after the head label is normalised and whitespace ignored. The label width shifts the columns ([output/exact_diff_0781baf_vs_f2a6ac1.txt](output/exact_diff_0781baf_vs_f2a6ac1.txt)). |
| Mutations at `f2a6ac1` | **45 of 46 caught by assertion failures**, each restored with a SHA-256 check ([output/mutations_all46_f2a6ac1.txt](output/mutations_all46_f2a6ac1.txt)). There were no errors-only kills, no crashes and no NO-RUN, and the file hashes before and after are equal. The set is the 31 carried OF-1003/1004 mutants (I15's anchor follows the new vs check), R1–R14 for this round's protections, and C9R13. |

### Mutations: the one survivor, and the first pass

- **C9 survives, and it is equivalent at this head.** C9 removes `not inside`, the check that some ref stays under the heading. If none stays, every citation group holds only moved refs, which the new empty-group check (R13's anchor) already keeps; each group holds at least one ref. **C9R13** removes both checks and is caught by six cases, including "If the figure [S3] is taken at face value …". So the page-12-only protection is still pinned.
- **First pass at `b4fa23e`** ([output/mutations_first_pass_b4fa23e/](output/mutations_first_pass_b4fa23e/)): I3 (the list guard) also survived. Its only list control named page 10, which the new page check now keeps on its own. `f2a6ac1` adds "The deck states 500M messages and 500M messages/month [C3, S3].", decided by the list guard alone, and the whole set was rerun. The first pass's pre-run hash file was overwritten when the test file changed; the `b4fa23e` hashes are the guard hash above and the earlier test file.
- **RAM:** every chunk ran in the foreground, one chunk per call, behind the 0.9 GB floor. Free RAM was 1.75–1.85 GB ([output/mutation_ram.txt](output/mutation_ram.txt)).

## Limitations

- **Over-preservation:** a denial word anywhere in the clause keeps its citations, even when it denies something else ("The deck does not reconcile [C3, S2] vs [C3, S3]" keeps the wrong C3). A hedge does not block a correction.
- **Questions:** a question is kept whole, so a wrong citation in a question stays.
- **Denial vocabulary:** this is a word set. A denial the set does not name ("the slide leaves out …") is corrected as an affirmative. The page and source-context check still keeps it if another page or context is named.
- **Pages:** "page N", "pages N and M" and "page-N" are read; "p. 10" and "slide 10" are not.
- **Condition rule:** a condition whose moved refs sit in their own group is kept with its wrong heading for page 12. This is under-correction by design: no faithful rewrite is established.
- **Carried:** the OF-1003/1004 limitations in [`../output-of1003-1004-0781baf/README.md`](../output-of1003-1004-0781baf/README.md) and earlier rounds.

## Reproduction

The scripts are in [output/scripts/](output/scripts/), each saved with a `.txt` suffix. Tests run through `t.sh` (CI env, `--parallel 1`, labels required). Probe, replay and exact scripts run through `shell.sh` (`manage.py shell`, memory broker, no network). Mutations run through `chunk.sh <name> <IDs>` (hash precheck, RAM floor) → `mutate_r.py` (`make_mutate.py` derives it from the r11 runner plus `r_mutants.py`). `anchors.py` confirms that every anchor matches exactly once.

## Status

- The correction is pending independent re-review. It is not merged or deployed.
- No live model run has been started.
- RA-109 live acceptance, RA-108, RA-114 and overall hardening remain open.
