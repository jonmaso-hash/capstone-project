# Review of b718566: clause ownership needs a source and its finite reporting verb

**This is correction evidence only, not live acceptance.**
- No model call was made, memo 102 was not regenerated, and Q1–Q7 were not repeated.
- This folder is additive. It changes nothing in the earlier evidence folders, in the memo-102 run (`6d131f5`), in its grade (`f2a282f`) or in any recorded memo.

**Where the change is:**
- **Branch:** `fix/basis-context-identity-of1003-1004`, base `main` at `d0bad8f`.
- **Commits:**
  - `fb1ea89c0886c7e931509734b94cc06a2646ccd5`: application and tests;
  - `f7a5ad1f9f508523ab38ba44652bd93310c72ae1`: tests only, the final head for validation.
- **Guard:** `zelda_api/basis_fidelity.py`, sha256 `a9da97df73c52b5b75c5a3a96ab902d30dd85139a583e7b41bffcb3bf4a06bab`.

**Worktree note:** the local worktree folder `KCV-of1003` had been removed from disk since the last round. Git still listed it as prunable. The branch was intact (local and `origin` both at `14f12fb`), so the worktree was re-created at the same path with `git worktree add -f`. The guard's bytes matched `b718566` (`60fd0b32…`) before any edit. No other worktree entry was pruned or touched.

## Reproduced first (at b718566)

These are full post-generation sequences on memo 102's payload. The outputs are in [output/review_probe_b718566.txt](output/review_probe_b718566.txt) and [output/review_probe_f7a5ad1.txt](output/review_probe_f7a5ad1.txt).

| Input | At `b718566` | At `f7a5ad1` |
|---|---|---|
| Page 10 does not state: the reported '500M messages/month' [C3, S2]. | → [C2, S3], `basis_citation_identity` | kept, no flag |
| Page 10 does not state (reported as '500M messages/month' [C3, S2]). | → [C2, S3], flag | kept, no flag |
| … the stated / (listed as / (shown as / (as reported, / (the figure reported elsewhere, … [C3, S2] | → [C2, S3] | kept |
| Page 10 does not state (as the deck states elsewhere, '500M messages/month' [C3, S2]). | → [C2, S3] | kept |
| Page 10 doesn’t state (reported as '500M messages/month' [C3, S2]). | → [C2, S3] | kept |
| Page 10 has no interval (on page 12, '500M messages/month' [C3, S3]). | → [C2, S3] | **kept** (see below) |
| Page 10 doesn’t give an interval (page 12 states '500M messages/month' [C3, S3]). | → [C2, S3] | → [C2, S3]; only this group changes |
| Second pair: Page 7 does not state: the reported / (reported as '3M bots/week' [C7, S7]). | → [C8, S8] | kept |

## Root cause and fix

**Cause.** At `b718566`, `_governing_clause` treated a segment set off by a colon, dash or parenthesis as its own clause if `_REPORTING` matched anywhere in it, or if it named a page. "Reported", "stated", "listed" and "shown" used as adjectives or participles therefore discarded the governing page-10 denial.

**Fix (`fb1ea89`).** A set-off segment is now its own clause only if `_OWN_REPORT` matches at its start:
- an optional "and", "but", "while" or "whereas";
- then a source as subject: "page N", "slide N", "the deck/pitch deck/company/slide/presentation/founder(s)/management/team", "it" or "they";
- then an optional "also", "separately", "instead" or "itself";
- then that subject's finite reporting verb (states/stated, reports/reported, presents/presented, lists/listed, shows/showed, gives/gave, cites/cited), not followed by "as".

Anything else is not ownership, and the clause around the figure governs it.

This is an allowlist. Under it:
- a bare reporting word is not ownership;
- a subordinate "as the deck states" is not ownership;
- a "verb as" form ("page 12 reported as") is not ownership;
- a page alone is not ownership.

All four fall back to the conservative reading.

**One earlier expectation changes:** "Page 10 has no interval (on page 12, '500M messages/month' [C3, S3])." was a corrected control at `b718566`, because a page alone counted as ownership. It is now kept unchanged. This is deliberate under-correction: a page alone does not establish an independent clause. The control moved from `REVIEW_F2A_FIXED` to `REVIEW_B71_KEPT`, and no other earlier expectation changed.

## Validation

| Check | Result |
|---|---|
| Red | The final tests against `b718566`'s guard give **15 assertion failures, 0 errors** out of 238 tests ([output/red_run_final_tests_on_b718566.txt](output/red_run_final_tests_on_b718566.txt)). "a cited …" is a control that passes at `b718566` as well, because "cited" was never a `_REPORTING` word there. |
| Green at `f7a5ad1` | **382 OK** in total: `tests_output_fidelity` 238, `tests_usage_basis` 77, `tests_funding_fidelity` 67 ([output/modules_f7a5ad1.txt](output/modules_f7a5ad1.txt)). `check` exits 0, and so does `makemigrations --check --dry-run` ([output/check_and_migrations_f7a5ad1.txt](output/check_and_migrations_f7a5ad1.txt)). |
| New controls (`ReviewB718566Tests`, 4 tests) | **Kept, no flags:** the review's two cases; the stated / listed as / shown as / as reported / a cited / the figure reported elsewhere / reported elsewhere; a subordinate "as the deck states"; "page 12 reported as"; "doesn’t" with "reported as"; a page alone.<br>**Corrected, with only the independent clause's group changing (asserted):** the review's control "(page 12 states …)"; "page 12 stated"; "while page 12 states"; "page 12 also reports"; ": page 12 lists"; "— the deck shows … elsewhere"; affirmative outer clauses with "the reported" or "(reported as …)".<br>**Also checked:** every case gives a stable second pass and the same output under reversed item order, every citation is a supplied ref, and each corrected group cites page 12's [C2, S3]. A second pair (C7/C8, S7/S8, pages 7/8) behaves the same way. |
| Earlier rounds | The review-of-75ca81f and review-of-f2a6ac1 probes give the same output at `f7a5ad1` as at `b718566` ([output/review75_probe_f7a5ad1.txt](output/review75_probe_f7a5ad1.txt), [output/review_f2a_probe_f7a5ad1.txt](output/review_f2a_probe_f7a5ad1.txt)). |
| Replay of memos 96–102 | Results are **identical to `b718566`'s**, and so to `0781baf`'s ([output/replay_memos_96_to_102_f7a5ad1.json](output/replay_memos_96_to_102_f7a5ad1.json)).<br>• Memos 96–101: unchanged.<br>• Memo 102: exactly its three corrected fields differ from base.<br>• Every replay is idempotent and order-stable, and every citation is supplied. The recorded memos were not touched. |
| Carried probes | 75/75 identical apart from `head` ([output/compare_probes_b718566_vs_f7a5ad1.txt](output/compare_probes_b718566_vs_f7a5ad1.txt)). |
| Exact outputs | **110/110** exact, with 0 diff lines against `b718566` once the head label is normalised. |
| Mutations at `f7a5ad1` | **61 of 62 were caught by assertion failures** ([output/mutations_all62_f7a5ad1.txt](output/mutations_all62_f7a5ad1.txt)).<br>• Assertion failures and execution errors are recorded separately for each mutant: every "errors in:" line is "-", so there were **0 execution errors and 0 crash-only kills**.<br>• All 62 were restored with a SHA-256 check, and the hashes before and after are equal.<br>• The set: H1–H10 (new); the carried G1–G4, G8, G9, R1–R14, C9R13 and 31 OF-1003/1004 mutants. G5–G7 were retired with the ownership test they mutated.<br>• Every chunk ran in the foreground, one per call, behind the 0.9 GB floor; free RAM was 1.90–2.10 GB ([output/mutation_ram.txt](output/mutation_ram.txt)). |

**The H mutants** each separate genuine clause ownership from merely finding a reporting word or a page. All ten were caught:
- **H1:** any reporting word owns the segment. This is the review's defect; 13 failures.
- **H2:** ownership is matched anywhere in the segment, not at its start.
- **H3:** no subject is required.
- **H4:** "verb as" counts as finite.
- **H5:** a page alone owns the segment.
- **H6:** no "while/and/but" opener is allowed.
- **H7:** past-tense verbs are dropped.
- **H8:** no adverb is allowed between subject and verb.
- **H9:** "the deck" is not a subject.
- **H10:** no segment is ever its own clause.

**C9** survives as an equivalent mutant, as in the last two rounds. C9R13, which removes both of the overlapping checks, is caught.

## Limitations

- **Ownership is an allowlist,** so some genuine independent clauses are not corrected, and the governing clause decides instead. Where that clause has a denial or names another page, a wrong citation stays. That is under-correction, never a wrong rewrite. Examples:
  - another subject ("(management says …)", "(the founders claim …)");
  - another verb ("says", "notes", "puts it at");
  - a passive ("(page 12 is stated …)");
  - a page alone ("(on page 12, …)").
- **Only one level of nesting.** A segment set off twice is read against the whole clause.
- **Carried from the earlier rounds:**
  - a denial anywhere in the governing clause keeps its citations;
  - questions are kept whole;
  - a denial outside the word set and without "n't" is not read;
  - "p. 10" and "slide 10" are not read as pages in the page check;
  - a condition whose moved refs sit in their own group is kept;
  - the OF-1003/1004 limitations in [`../output-of1003-1004-0781baf/README.md`](../output-of1003-1004-0781baf/README.md).

## Reproduction

The scripts are in [output/scripts/](output/scripts/) with a `.txt` suffix:
- **Probes:** `probe.py` (this round), `probe_r13.py` and `probe_r12.py` (earlier rounds).
- **Tests:** `t.sh`.
- **Probes, replay, exact table:** `shell.sh`.
- **Mutations:** `chunk.sh` calls `mutate_r.py`, which `make_mutate.py` derives from `r_mutants.py`. `anchors.py` confirms that all 62 anchors match exactly once.

## Status

- Pending independent re-review; not merged and not deployed.
- No live model run has been started.
- Still open: RA-109 live acceptance, RA-108, RA-114 and overall hardening.
