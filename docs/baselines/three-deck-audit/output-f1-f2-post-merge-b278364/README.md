# Post-merge verification of PR #290 at b278364 (F-1, F-2, H6 controls)

This folder adds evidence. **Earlier evidence is unchanged:**
- the four `output-f1-f2-*` folders (`2d0b0e9`, `0a51dd9`, `94e6f59`, `3d1eeae` / `5c48efc`);
- the memo-104 run `f73bef5`.

**Nothing else was touched:**
- no memo was regenerated or overwritten, no model was called, and no application database was opened;
- no MFA was changed;
- the worker was not started, and nothing was merged or deployed.

**Still open:** RA-108, RA-109, RA-114, Q-2–Q-4 and overall acceptance. All validation here is my own and is not independent review.

| Item | Value |
|---|---|
| Execution SHA | `b27836439ca0e6aa9acc1ca6feaeae1be80b6415`: `origin/main`, the merge of PR #290. Confirmed with `git ls-remote` |
| Merge parents | `5120190` (main) and `5c48efc` (branch head). Main had no other commits since `5120190` |
| Validation SHA carried forward | `7fe189b7d1056529f1998d2c733f85d6c0d17347` |
| Checkout | new worktree `KCV-pm-b27` on `docs/post-merge-verification-b278364`, created at `b278364`. It was clean before and after every run. Other worktrees were not touched |

## 1. The merge preserved the validated bytes

Source: [output/merge_bytes.txt](output/merge_bytes.txt).

These files have the same blob at `7fe189b`, at `b278364` and in the checkout (`git hash-object`):
- `basis_fidelity.py`
- `funding_fidelity.py`
- `claim_context.py`
- `memo_lists.py`
- the four test modules
- `memo104.json`
- `memo104_payload.json`

The whole `zelda_api/` tree is the same object at both commits (`e2f63bda…`). Outside `docs/`, `git diff 7fe189b b278364` is empty, and `b278364`'s tree equals `5c48efc`'s.

## 2. Tests

The four modules ran serially, with the CI placeholder settings and a throwaway test database. Free RAM was 1.76–1.97 GB before each run, above the 0.9 GB floor ([output/suite_ram.txt](output/suite_ram.txt)).

| Module | Result |
|---|---|
| `zelda_api.tests_output_fidelity` | 283 OK |
| `zelda_api.tests_usage_basis` | 77 OK |
| `zelda_api.tests_funding_fidelity` | 67 OK |
| `zelda_api.tests_claim_context_dates` | 25 OK |

That is **452 OK**, the same as the recorded baseline at `7fe189b`. Full output is in `output/final_tests_tests_*.txt`.

## 3. Replays, compared with the 7fe189b evidence

Source: [output/postmerge_compare_b278364.txt](output/postmerge_compare_b278364.txt), with the detail in [json](output/postmerge_compare_b278364.json).

Each output was compared with the file committed at `3d1eeae`. Metadata keys are compared separately from content.

| Output | Content | Metadata difference |
|---|---|---|
| Frozen memos 96–104 ([json](output/replay_memos_96_to_104_b278364.json)) | **identical** | `head` only (`7fe189b` → `b278364`) |
| 75 carried probes ([json](output/carried_probes_75_b278364.json)) | **identical** | `head` only |
| 81 exact before/after cases ([json](output/exact_before_after_b278364.json)) | **identical** | `head` only |
| Earlier review cases ([json](output/review_cases_b278364.json)) | **identical** | `head` only |

**The replay is read-only.** It reads each run's recorded reply and stored memo from git. It writes only a JSON file to the scratchpad and never touches the database or a memo.

**Explicit checks.** All of them pass:
- **F-1:**
  - At `5120190`, memo 104's question becomes the stored text "the $23.1M reported (per Pitch Deck Hunt)ly raised [S4]".
  - At `b278364` it is "the $23.1M (per Pitch Deck Hunt) reportedly raised [S4]" (`Q5_104_AFTER`), in both the exact case and the memo-104 replay.
- **F-2:**
  - At `5120190`, memo 104's `business_model_analysis` sentence is left with page 10's heading over [S2, S3].
  - At `b278364` it is restated as `BM_104_AFTER`: S3 is "separately" on page 12, in both the exact case and the replay.
- **Memo replay:**
  - Memo 104's base replay equals what the run stored, in every field.
  - Memo 104 changes only `business_model_analysis` and `questions_for_management`.
  - Memos 96–103 are unchanged.
  - Every memo is idempotent and independent of item order, and every ref it cites is supplied.
- **H6:**
  - The reviewer's sentence is a `HEADING_KEPT` control, byte for byte.
  - All four "+" controls (`F-2 kept 43`–`46`: dash and comma forms, with a "+" on S2 or on S3) come out byte for byte as their input, and no rule fires. Each is idempotent and independent of item order.
- **Exact cases:** of the 81, the same 19 differ from `5120190`. All are idempotent and independent of order, and every kept control is byte-identical.

## 4. Mutation result, carried forward from 7fe189b (no new run)

The application and test bytes at `b278364` are identical to `7fe189b` (section 1). The mutation result is therefore **carried forward as validation from `7fe189b`**. It is not a new post-merge mutation run, and no mutant was applied in this checkout.
- **Result:** 19 of 25 caught ([`../output-f1-f2-review-64dff63-7fe189b/output/mutations.txt`](../output-f1-f2-review-64dff63-7fe189b/output/mutations.txt)).
- **Survivors:** H2, H3, H4, O3, P3 and S1 are **not proven equivalent**. The 20,000-sentence differential search found no counterexample for them, which is not a proof.

## 5. Remaining acceptance work

This list is drawn from the current evidence: the `f73bef5` ledger, the F-1/F-2 reviews and this verification.

| Item | State after PR #290 | What would close it |
|---|---|---|
| **RA-109** (live output fidelity) | Every known output finding has a merged fix (OF-1102/1103 in #289; F-1 and F-2 in #290). **F-1 and F-2 have not been run live.** Memo 104 shows them uncorrected, because it was generated at `5120190` | One bounded live Pass A at the merged head, then independent grading ([NEXT_LIVE_VALIDATION.md](NEXT_LIVE_VALIDATION.md)) |
| **RA-114** (`/ask/`) | Open: Q1–Q7 all returned the marketplace fallback in memo 104's run. **No fix on main** | A scoped code fix first. A live run before that can only re-observe it |
| **RA-108** (verification-process wording) | Open: "The verification process identified …" in `zelda_advantage`. **No fix on main** | A scoped fix, or a grader or owner decision on the wording |
| **Q-2–Q-4** (P3 wording) | Open, waiting on the grader: "undated total on page 10", the present-tense "large installed base", and "bot/messaging automation space" | Grader or owner decisions; code only after a decision |
| **Overall acceptance** | Open | All of the above, with independent grading |

## 6. Next live validation (prepared, not run)

[NEXT_LIVE_VALIDATION.md](NEXT_LIVE_VALIDATION.md) sets out:
- one ManyChat Pass A at the merged head, with a **budget of 8 model calls** (1 memo, plus Q1–Q7 once each) and no retries;
- preconditions, steps, and pass/fail criteria for run integrity, F-1, F-2 (including "not exercised") and regressions;
- what is recorded for the grader only (RA-108, RA-114, Q-2–Q-4).

It needs an explicit owner go-ahead, because it makes model calls and starts the worker.

## Reproduce

Scripts are committed under [output/scripts/](output/scripts/), **with a `.txt` suffix** (repo tests walk `.py` files):
- `replay.py.txt`, `carried_probe.py.txt`, `exact.py.txt`, `review_cases2.py.txt`: the same scripts as at `7fe189b`, run unchanged at `b278364`.
- `postmerge_compare.py.txt`: the comparison and the explicit checks.
- `t.sh.txt` (test runner) and `py.sh.txt` (script runner; refuses below 0.9 GB free). These contain only the CI placeholder settings, no credentials.
