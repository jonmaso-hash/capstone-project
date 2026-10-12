# ManyChat RA-102 / RA-106 post-fix validation at `d93f2e3`

**Separate, post-fix evidence.** This folder edits none of the earlier records:
- the frozen answer key (`docs/baselines/manychat/ANSWER_KEY.md`);
- the Pass A rerun ledger (`docs/two-deck-rerun-458bdc9`);
- documents 3132/3133 and memos 90/91;
- any earlier evidence folder.

**Status: ungraded by the owner. Zelda hardening stays pending.** Not deployed.

**RA-106 stays open for memo 91.** By owner decision, saved memo 91 is not changed and is not
regenerated. Its stored "has raised $23.1M to date" remains until the deck is re-run. This change
stops a newly generated memo from writing it.

## Owner decisions applied (2026-10-11)

- **Context only.** "Traction by Apr-16" is kept as source context for the figures on slide 10.
  Their structured period stays as the 2026-10-10 rule leaves it: the claim's own sentence only, so
  empty here. Truth Delta comparability and scoring are unchanged.
- **The funding sentence keeps its narrator** (Pitch Deck Hunt) and its "2015" deck context. 2015
  is never assigned as the as-of date of $23.1M.
- **Future memos only.** Memo 91 is shown as stored.

## Trace (where the context was lost)

| Hop | Before | Source |
|---|---|---|
| Deck text | slide 2: "Source: Pitch Deck Hunt lists ManyChat as a 2015 Series A deck with $23.1M raised."; slide 10: "Traction by Apr-16" above "140 000+ bots" and "500M messages" | `04_claims.json` `_slide_text` |
| Insight extraction | Bare fragments: `'$23.1M raised'`, `'140 000+ bots'`, `'500M messages'` | `03_insights.json` |
| Claim extraction | Recovered the source sentence but used it only for ownership and period. The claim kept the bare figure. "2015" is a bare year, which is correctly not a period, so it was dropped. The heading is on another line, so it was dropped (owner rule). Ownership was `named`, so the company appeared to be speaking | `truth_delta_tasks.extract_claims_from_insights`, `claim_periods` |
| GroundedContext | Gave the memo `statement: "$23.1M raised"` with no date, narrator or context | `grounded_context._claim_items`, `_statement_items` |
| Memo 91 | "The company states it has raised $23.1M **to date** [S3]" | `09_memo.json` |
| Company overview | Shows `memo.executive_summary`, so the same sentence | `matchmaking.views._company_overview` |

## Fix

- **`zelda_api/claim_context.py`** (new):
  - `dated_heading`: a dated heading directly over the figure's block.
  - `claim_narrator`: a third party the sentence says reports the figure; never the company.
  - `unbound_dates`: dates in the sentence that are not the figure's period.
  - `guard_time_wording`: the memo guard.
- **`ClaimedDatapoint`:** gains `source_sentence` (bounded to 300 characters), `narrator` and
  `source_context` (migration **0044**; blank, never backfilled). The structured period fields are
  untouched.
- **GroundedContext:** each claim-backed item, and the statement that is that claim's figure,
  carries:
  - `as_of`: its own period's end date or fiscal year, else `not stated`;
  - `narrator`, `source_context` and `dates_not_as_of`.

  **The source sentence itself does not cross the memo boundary.**
- **Memo prompt rule 9** covers dates and narrators.
- **Deterministic guard:** after generation, it removes "to date", "so far", "currently", "at
  present", "as of today", "as of now", "as it stands", "up to now" and "until now" from sentences
  that cite a claim-backed item whose own source does not use that wording. Sentences that cite
  nothing, and wording the source itself uses, are kept.

## Results

| Check | Result |
|---|---|
| Real data (read-only, dev DB, `PRAGMA query_only`), [logs/readonly_doc3133_check.txt](logs/readonly_doc3133_check.txt) | Doc 3133 insight 5164 `140 000+ bots` and 5165 `500M messages`: heading `Traction by Apr-16`, no narrator, period empty. Insight 5166 `$23.1M raised`: narrator `Pitch Deck Hunt`, `dates_not_as_of ['2015']`, period empty. Memo 91's stored summary contains "to date"; the guard would remove it for a new memo; memo 91 is not changed |
| Extraction (stored ManyChat slide text, real `_analyze_document` and `extract_claims_from_insights`) | Funding claim: narrator `Pitch Deck Hunt`, sentence kept verbatim (minus the final full stop the existing splitter drops), no heading. Usage claims: `source_context` = `Traction by Apr-16`. All structured periods are empty |
| Truth Delta | Score `None` / `unknown`, all categories `no_data`, comparison rows carry no claim period |
| Memo payload | Funding items (claim and statement): `as_of: not stated`, `narrator: Pitch Deck Hunt`, `dates_not_as_of: ["2015"]`. Usage items: `source_context: Traction by Apr-16`. The sentence text is **absent** from the payload |
| Generated memo | "…has raised $23.1M [S…]" with no "to date"; "so far" and "currently" removed from cited sentences; an uncited "No revenue has been disclosed to date." kept |
| IC memo page and company overview | Show the guarded text; never "$23.1M to date" |

**Negative controls** (unrelated dates and narrators are not attached):
- the chart axis values and month labels on slide 10;
- an undated heading;
- a bare-year heading ("2015 Highlights");
- a prose line between heading and figure;
- a dated heading below the figure;
- "this month" lines;
- a figure from another slide;
- the company itself in the narrator slot ("ManyChat reports…", "According to ManyChat…");
- "per our last filing" and "per month".

## Validation

[logs/validation_output.txt](logs/validation_output.txt):
- `check` clean; `makemigrations --check` reports no changes (0044 present).
- 15 new tests pass (`zelda_api.tests_claim_context_dates`, in the blocking CI list).
- Before the new module was added, 572 existing tests in the affected modules passed.
- Full `matchmaking` 884 and `pages` 517 pass.
- Full `zelda_api` 1481: only the 3 pre-existing, order-dependent `tests_grounded_context` errors.
  Main `485306c` has the same three in 1466 tests, and the module passes 34/34 in isolation here.

[logs/mutations_output.txt](logs/mutations_output.txt): eight mutations, all red.
- The first run had D8 (the company counted as narrator) surviving. Company-as-narrator cases were
  added, and D8 is now red.

## Frozen data

[logs/frozen_rows_before_after.txt](logs/frozen_rows_before_after.txt):
- memos 90/91 have the same sha256 before and after the read-only check, matching every earlier
  walk;
- document 3132/3133 rows are unchanged;
- Redis lists are unchanged.

The dev DB was **not** migrated: migration 0044 exists only in the test databases.

## Still open

- **RA-106 for memo 91:** open until the deck is re-run (owner decision).
- **RA-109 / I1** (500M cumulative vs 500M/month): not addressed. The heading context now reaches
  the memo, but nothing flags the conflict.
- **RA-103** (slide 2 is audit framing, marked `named`): ownership is unchanged. The narrator now
  records whose statement it is.
- **Displaying context:** the Truth Delta claim rows do not yet show `source_context` or `narrator`.
  The fields are stored for that.
