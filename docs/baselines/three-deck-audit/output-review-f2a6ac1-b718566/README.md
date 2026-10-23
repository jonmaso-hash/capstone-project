# Review of f2a6ac1: denial and source context across punctuation, typographic contractions

**This is correction evidence only, not live acceptance.**
- No model call was made, memo 102 was not regenerated, and Q1–Q7 were not repeated.
- This folder is additive. It changes nothing in the earlier evidence folders ([`../output-of1003-1004-0781baf/`](../output-of1003-1004-0781baf/README.md), [`../output-review-75ca81f-f2a6ac1/`](../output-review-75ca81f-f2a6ac1/README.md)), in the memo-102 run (`6d131f5`), in its grade (`f2a282f`) or in any recorded memo.

**Where the change is:**
- **Branch:** `fix/basis-context-identity-of1003-1004`, base `main` at `d0bad8f`.
- **Commit:** `b718566b2c3fe3a7aef7d2eb725f038fa0356ff9`, application and tests; this is the final head for validation.
- **Guard:** `zelda_api/basis_fidelity.py`, sha256 `60fd0b329baef1ff13456e8390c438d36b9b1ece7352b85e5f4b52824b2444ec`.

## The reported errors, at f2a6ac1 and now

Every case runs through the full post-generation sequence on memo 102's payload. The table lists the review's three inputs and a sample of the controls. Each row is a citation correct for page 10; at `f2a6ac1` the guard switched it to page 12's [C2, S3]. The full outputs are in [output/review_probe_f2a6ac1.txt](output/review_probe_f2a6ac1.txt) and [output/review_probe_b718566.txt](output/review_probe_b718566.txt).

| Input | At `f2a6ac1` | At `b718566` |
|---|---|---|
| Page 10 does not state: '500M messages/month' [C3, S2]. | → [C2, S3] | kept |
| Page 10 does not state ('500M messages/month' [C3, S2]). | → [C2, S3] | kept |
| The deck doesn’t state '500M messages/month' [C3, S2]. | → [C2, S3] | kept |
| Page 10 does not state — '500M messages/month' [C3, S2]. | → [C2, S3] | kept |
| The deck hasn't stated '500M messages/month' [C3, S2]. | → [C2, S3] | kept |
| Page 10 states: '500M messages/month' [C3, S2]. | → [C2, S3] | kept |
| Page 12 states: '500M messages/month' [C3, S3]. | → [C2, S3] | → [C2, S3] (still corrected) |

## What changed

- **The clause that governs a figure (`_governing_clause`).**
  - A colon, dash or parenthesis can set a figure off on its own. Such a segment counts as its own clause only when it reports something itself, meaning it has a reporting verb (`_REPORTING`) or names a page of its own, as in "(page 12 states '500M messages/month' [C3, S3])".
  - Otherwise the figure is only set off, and the clause around it governs it. That outer clause is bounded only by ";" and clause-linking commas, and it carries the source and any denial.
  - So "Page 10 does not state: …", "… does not state (… [C3, S2])", "(… [C3, S2]) is not stated on page 10" and "Page 10 states: …" keep page 10's refs. "The deck states: / ( … ) / — …" are still corrected.
- **Contractions.** Typographic apostrophes (’ ‘ ʼ) are read as "'", and any word ending in "n't" counts as a denial. The explicit "n't" entries were dropped from the word set, because the suffix rule now covers them.
- **Memo 102's three corrections are unchanged:**
  - `base_scenario`: S3 moved out, with the clarification;
  - `open_concerns`: [C3, S3] → [C2, S3];
  - `business_model_analysis`: "vs [C2, S3]".

## Validation

| Check | Result |
|---|---|
| Red | The final tests against `f2a6ac1`'s guard give **13 assertion failures, 0 errors** out of 234 tests ([output/red_run_final_tests_on_f2a6ac1.txt](output/red_run_final_tests_on_f2a6ac1.txt)). |
| Green at `b718566` | **378 OK** in total: `tests_output_fidelity` 234, `tests_usage_basis` 77, `tests_funding_fidelity` 67 ([output/modules_b718566.txt](output/modules_b718566.txt)). `check` exits 0, and so does `makemigrations --check --dry-run` ([output/check_and_migrations_b718566.txt](output/check_and_migrations_b718566.txt)). |
| New controls (`ReviewF2a6ac1Tests`, 4 tests) | **Kept:** the review's three cases; a dash; a denial after the parenthesis; a typographic contraction across a colon; "hasn’t" and "hasn't"; another page across a colon or parenthesis; another source context across a colon; a question across a colon.<br>**Corrected:** the affirmative colon, parenthesis and dash forms; a parenthesis that reports for itself, by a verb or by its own page, beside a typographic denial; ";" and ", but" after a typographic denial.<br>**Also checked:** every case gives a stable second pass and the same output under reversed item order, and every citation is a supplied ref. Each corrected group cites page 12's [C2, S3]. A second pair (C7/C8, S7/S8) behaves the same way. |
| Previous round | The review-of-75ca81f probe gives the same output at `b718566` as at `f2a6ac1` ([output/review75_probe_b718566.txt](output/review75_probe_b718566.txt)). Its 6 tests pass. |
| Replay of memos 96–102 | Results are **identical to `f2a6ac1`'s** and therefore to `0781baf`'s ([output/replay_memos_96_to_102_b718566.json](output/replay_memos_96_to_102_b718566.json)).<br>• Memos 96–101: 0 fields differ from the base replay.<br>• Memo 102: exactly the three corrected fields differ.<br>• Every replay is idempotent and order-stable, and every citation is a supplied ref. The recorded memos were not touched. |
| Carried probes | 75/75 identical apart from `head` ([output/compare_probes_f2a6ac1_vs_b718566.txt](output/compare_probes_f2a6ac1_vs_b718566.txt)). |
| Exact outputs | **110/110** exact, with 0 diff lines against `f2a6ac1` once the head label is normalised and whitespace is ignored. |
| Mutations at `b718566` | **54 of 55 were caught by assertion failures**, and each was restored with a SHA-256 check ([output/mutations_all55_b718566.txt](output/mutations_all55_b718566.txt)). The set:<br>• the 31 carried OF-1003/1004 mutants;<br>• R1–R14 and C9R13 from the previous round, with R1, R2, R3, R5 and R9 re-anchored to the edited lines;<br>• G1–G9, new for this round (see below).<br>No errors-only kills, no NO-RUN, and the hashes before and after are equal. Every chunk ran in the foreground, one chunk per call, behind the 0.9 GB floor; free RAM was 1.16–1.84 GB ([output/mutation_ram.txt](output/mutation_ram.txt)). |

The G mutants each remove one of this round's protections:
- **G1:** no outer clause is used.
- **G2:** the outer clause still stops at a colon or dash.
- **G3:** the outer clause still starts at "(".
- **G4:** the outer clause still ends at ")".
- **G5, G6, G7:** a set-off segment no longer counts as its own clause through its reporting verb (G5), its own page (G6), or at all (G7).
- **G8:** typographic apostrophes are not translated.
- **G9:** the "n't" suffix rule is removed.

**C9 survives as an equivalent mutant**, as at `f2a6ac1`. With no ref under the heading, every condition group holds moved refs alone, and the empty-group check already keeps the sentence. C9R13, which removes both checks, is caught.

## Limitations

- **Own clause by an allowlist.** A set-off segment is its own clause only through a `_REPORTING` verb (states, reports, presents, lists, shows, gives, cites) or a page. "(the deck says '500M messages/month' [C3, S3])" therefore takes the outer clause. A denial there keeps the wrong ref, which is over-preservation rather than a wrong rewrite.
- **Only one level of nesting.** A figure set off twice ("(page 12: '…' [C3, S3])") is read against the whole sentence-level clause.
- **Carried from the earlier rounds:**
  - a denial anywhere in the governing clause keeps its citations, even when it denies something else;
  - questions are kept whole;
  - a denial outside the word set and without "n't" ("leaves out") is not read;
  - "p. 10" and "slide 10" are not read as pages;
  - a condition whose moved refs sit in a group of their own is kept;
  - the OF-1003/1004 limitations recorded in [`../output-of1003-1004-0781baf/README.md`](../output-of1003-1004-0781baf/README.md).

## Reproduction

The scripts are in [output/scripts/](output/scripts/) with a `.txt` suffix:
- **Tests:** `t.sh` (CI env, `--parallel 1`, labels required).
- **Probes, replay, exact table:** `shell.sh`. `probe.py` holds this round's cases and `probe_r12.py` the previous round's.
- **Mutations:** run `chunk.sh <name> <IDs>`, which calls `mutate_r.py`. `mutate_r.py` is derived by `make_mutate.py` from the r11 runner plus `r_mutants.py`. `anchors.py` checks that every anchor matches exactly once.

## Status

- Pending independent re-review; not merged and not deployed.
- No live model run has been started.
- Still open: RA-109 live acceptance, RA-108, RA-114 and overall hardening.
