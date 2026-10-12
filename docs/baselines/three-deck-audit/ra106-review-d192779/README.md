# RA-102 / RA-106 review corrections at `d192779`

**Separate evidence.** This folder edits none of the earlier records, including
`../ra106-postfix-d93f2e3/`, the frozen answer key, documents 3132/3133 and memos 90/91.

**Status: RA-106 stays pending.** The memo evidence here uses mocked generation: the real
`_generate_memo` runs, but the model reply is a fixed test reply. RA-106 stays open until a
separate live post-fix rerun is graded by the owner. Frozen memo 91 was not regenerated. Not
deployed; Zelda hardening is not complete.

## Review findings and corrections

| # | Finding | Correction (`zelda_api/claim_context.py`) |
|---|---|---|
| 1 | `guard_time_wording` split sentences at the stop, so a citation after punctuation ("...to date. [S3]") was missed in its own sentence and applied to the next one | A sentence now ends after its stop **plus any citations written straight after it**. Grouped refs `[S1, S3]`, `[S1; S3]` and `[S1][S3]` are all read. A space is only inserted where wording was removed |
| 2 | `dated_heading` treated any short line with a digit as a sibling figure, so numeric prose ("Up 3x in 6 months") between the heading and a figure let the heading attach | A sibling must be a figure line: a number and up to three words naming it. Prose ends the block, numbers or not. A figure that sits inside a prose line gets no heading. Ambiguous means no association |
| 3 | The guard rewrote research questions ("What has ManyChat raised to date [S3]?") | Questions (ending in `?`) and requests to management ("Confirm…", "Ask management…", "Verify…") are kept. Only statements citing a claim-backed figure are rewritten. Memo prompt rule 9 says the same |

Unchanged: structured periods, Truth Delta comparison and scoring, the memo's no-raw-text
boundary (the source sentence still never reaches the memo), frozen rows.

## New regressions (`zelda_api/tests_claim_context_dates.py`, 15 → 25)

- **Citation placement:** before the stop, after it, after with no space, at a line end, and touching the phrase.
- **Grouped refs:** comma, semicolon after the stop, adjacent groups, and one allowing source with one that does not. A group whose only ref allows the wording is kept.
- **Adjacent sentences:** a citation after the stop never moves to the next, uncited sentence ("No revenue has been disclosed to date." is kept).
- **Questions and requests:** seven forms are kept, including bulleted, numbered and `Q2:`. A statement next to a question is still guarded.
- **Heading walk:**
  - six numeric-prose lines between heading and figure;
  - a figure inside a prose line;
  - the real slide-10 block with more sibling figures, which keeps "Traction by Apr-16".
- **Real memo writer**, using real ManyChat extraction into `_generate_memo` with a mocked model reply:
  - citations after the stop, grouped and adjacent groups;
  - `questions_for_management` keeps three question/request items, and a statement in the same section is still guarded.

## Results

[output/validation_output.txt](output/validation_output.txt):
- `check` clean; `makemigrations --check` reports no changes.
- `tests_claim_context_dates` + `pages.tests_ci_manifest`: 43 OK.
- Affected modules (`tests_grounded_context`, `tests_claim_attribution`, `tests_claim_periods`,
  `tests_claim_currency`, `tests_claim_extraction_recall`, `tests_memo_persistence`,
  `tests_memo_list_rendering`, `zelda_api.tests`): 572 OK.

[output/mutations_output.txt](output/mutations_output.txt): 16 mutations, all red.
- D1–D8 are the first validation's mutations, re-run.
- R1–R8 cover the corrections:
  - R1: the old splitter;
  - R2: refs split on commas only;
  - R3: questions rewritten;
  - R4: requests rewritten;
  - R5: the guard off;
  - R6: the old sibling walk;
  - R7: a prose figure line accepted;
  - R8: the citation glued to the text.
- Harness: [output/mutate_review.py.txt](output/mutate_review.py.txt).

[output/readonly_doc3133_check.txt](output/readonly_doc3133_check.txt): doc 3133 read-only, same as the
first check. Both slide-10 figures keep `Traction by Apr-16`; `$23.1M raised` keeps narrator
`Pitch Deck Hunt` and `dates_not_as_of ['2015']`; all periods are empty.

[output/frozen_rows_before_after.txt](output/frozen_rows_before_after.txt): memos 90/91 sha256
unchanged (same hashes as every earlier walk); document 3132/3133 rows and Redis lists identical.
The dev DB is still not migrated (0044 exists only in test databases).

## Still open

- **RA-106:** pending a separate live post-fix rerun, graded by the owner. Memo 91 is unchanged.
- RA-109 / I1, RA-103, and displaying the context in the Truth Delta rows, as before.

## Note on the earlier folder

`.gitignore` ignores every `logs/` directory. The earlier `ra106-postfix-d93f2e3` commit therefore
published only its README; the log files it links exist only in the local worktree. That folder is
left as committed. This folder keeps its logs under `output/`, which is published.
