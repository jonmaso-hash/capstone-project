# RA-104 saved-summary follow-up at `b4f17a9`

**Separate, additive evidence.** It completes the saved-summary case on `fix/claim-count-consistency`
before merge. Nothing earlier is edited:
- `ra104-postfix-b455fe6/`;
- the BW, RA and frozen baseline records.

**Status: ungraded. Zelda hardening stays pending.** Not deployed, and no report was regenerated.

## Gap

At `b455fe6`, every claim *label* counted claims, but `TruthDeltaScoreView` and
`truth_delta_signal` still returned `report.summary` as stored. A summary composed by
`narrative.summary()` opens with a deterministic count sentence. Summaries saved before
claim counts computed that sentence over categories, so one could show "2 not established (of 2)"
beside three claim rows.

## Change (`b4f17a9`)

`zelda_api.ic_memo.display_summary(report)` rewrites the summary's **opening** sentence only when it
is exactly one of the deterministic wordings `narrative.summary()` has stored:

| Wording | Stored by |
|---|---|
| `V verified · C contradicted · N not established (of T).` | current `coverage_line` |
| `Limited public evidence: none of the N claims could … / the claim could not … be verified or contradicted against a public source.` | current, nothing scoreable (since `4a3d465`) |
| `V of T checkable claim(s) verified against a public source[; C contradicted][; U could not be confirmed].` | `2b0e895` → `4a3d465`, 2026-10-04 |

- The rewrite uses `coverage_sentence(coverage_counts(report.claim_stats()))`.
- **Left exactly as stored:**
  - all text after the sentence (narrative, citations);
  - any summary that doesn't open with one of these sentences;
  - numbers in prose;
  - a report with no claim rows.
- `report.summary` is never written.
- **Surfaces that now show it:**
  - Truth Delta page (`summary`);
  - score API (`summary`);
  - memo/overview signal, which feeds the IC memo HTML and markdown;
  - profile verification history (`report.display_summary`).

## Regression

`SavedCategoryCountSummaryTests` stores `0 verified · 0 contradicted · 2 not established (of 2).` plus a
narrative tail with a citation, on a three-claim report shaped like report 87. It asserts:
- **Every surface** shows "Limited public evidence: none of the **3** claims …" followed by the
  identical tail, and never "(of 2)". The surfaces are the page context and HTML, the API, the
  signal, the staff IC memo HTML and the profile history. The page, API and memo counts all read 3.
- **The stored row is unchanged:** the `TruthDeltaReport` row is equal field-for-field, including
  `summary`, before and after every surface was rendered.
- **Score and outcomes:** `None` / `unknown`, with `category_states` and per-claim
  (claim_id, state, reason) unchanged.
- **Inherited checks:** it subclasses the report-87 test class, so all of those page, API, memo and
  unscored assertions also run against the old summary.

`DisplaySummaryRecognitionTests` checks:
- each historical wording is recounted;
- prose numbers and a count sentence that is not at the start are left alone;
- the no-count sentences are left alone;
- a report with no claim rows keeps its stored text.

## Results

- [logs/validation_output.txt](logs/validation_output.txt), runner output:
  - `check` clean; `makemigrations --check` reports no changes;
  - `zelda_api.tests_claim_counts_per_claim` 24 OK;
  - consumer batch 589 OK (`zelda_api.tests` + 11 Truth Delta presentation/grounding modules +
    `pages.tests_ci_manifest`);
  - `accounts` 293 OK; `matchmaking` 884 OK.
- [logs/mutations_output.txt](logs/mutations_output.txt), each surface put back on `report.summary`
  (S1–S4), a match anywhere instead of only at the start (S5), and the result written back to the row
  (S6). All six turn the suite red.
- [logs/dev_db_summary_scan.txt](logs/dev_db_summary_scan.txt), a **read-only** scan of the dev DB:
  - 69 saved reports; one (report 83) opens with a recognized count sentence, and its counts already
    agree;
  - `display_differs=0`;
  - report 87's stored summary has no count sentence, so it displays unchanged.

  The saved-category-summary case is therefore proven by the regression, not observed in local data.
  For the same reason no new browser walk was run: every page would render identically to
  `ra104-postfix-b455fe6/`.
