# Funding-source fidelity: second review corrections at `3481d8f`

**Separate, additive evidence.** It does not edit [../funding-fidelity-2befa42/](../funding-fidelity-2befa42/README.md),
[../funding-fidelity-a0ac9ad/](../funding-fidelity-a0ac9ad/README.md), the live run's ledger, OWNER_GRADING.md
(branch `docs/manychat-postfix-a975af3`, 88df894), memo 94, memos 90/91 or documents 3132/3133.

**Status:** RA-106 and Zelda hardening stay pending. Memo 94 is not regenerated. Not deployed.

## Review findings on `a0ac9ad`, and the correction

| # | Finding (review case) | At a0ac9ad | At 3481d8f |
|---|---|---|---|
| 1 | "The company is considering raising $5M." / "Is the company raising $5M?" / "If the company is raising $5M, the founders should clarify its terms." | Each set `raise_supported=True` | Each is rejected as tentative, a question or a condition, as are "may be raising", "plan on raising", "…raising $5M?" and "whether". The affirmative controls still count: "Seeking $5M seed round", "We are raising a $5M Series A", "ManyChat is raising $5M" |
| 2a | "Investors cite annual revenue of $23.1M." (Pitch Deck Hunt funding + same-amount revenue item) | Gained "(per Pitch Deck Hunt)": "Investors" read as funding, and the metric before the amount was not seen | Unchanged: a metric word in the four words before an uncited amount keeps its own identity |
| 2b | An uncited amount that two narrators (or a narrator and the company's own figure) could each be | Attribution followed item order | Attributed to **none**, with identical output in either order. A citation still decides ("[S3]" goes to Pitch Deck Hunt, "[S5]" to Crunchbase) |

## Results

- [output/review2_cases_probe.txt](output/review2_cases_probe.txt): every review case, the controls, and the ambiguity cases in forward and reversed item order (`same: True` for each).
- [output/memo94_probe_3481d8f.txt](output/memo94_probe_3481d8f.txt): memo 94's stored sections, read via `git show 88df894:…`.
  - 9 sections change.
  - The output is **identical** to the a0ac9ad probe; memo 94's wording needs none of these checks.

**Regressions** (`zelda_api/tests_funding_fidelity.py`):
- **Raise statements:** the three review statements, plus "may be", "plan on", a trailing "?" and "whether".
- **Metric before the amount:** the review sentence, "revenue reached", "ARR of", and a funding positive control.
- **Ambiguity:** another narrator, and the company's own figure, each in both item orders, uncited and cited.
- **Isolating tests** for the after-amount metric, another named source and funding wording. The new checks would otherwise shadow these three (mutations G13–G15 survived until these were added).

[output/mutations_output.txt](output/mutations_output.txt): **32 mutations, all red.** Runs are labelled.
- **Discarded groups.** A `timeout` wrapper killed one harness run while the F12 mutation was applied, and it stayed in the file. The two groups that then ran on mutated code are discarded and not shown. The line was restored, the file diffed against `a0ac9ad` after every later group, and those mutations re-run.
- **H1–H5 (this review):** tentative, question, condition, metric before the amount, and ambiguity resolved by order.

[output/validation_output.txt](output/validation_output.txt), on the committed code with isolated test databases, one batch at a time:
- `check` clean; `makemigrations --check` reports no changes.
- 213 + 76 + 428 (`zelda_api.tests`) + 103 + 426 (`matchmaking.tests`) + 147 (accounts/pages) = **1,393 tests, all OK**.

## Unchanged

- Structured periods, Truth Delta comparison and scoring.
- Tier permissions and the raw-source memo boundary.
- Memo 94 and the frozen evidence.

## Still open

- **RA-106:** until a newly generated memo is graded.
- **Upside scenario:** the "fully deployed into growth" hypothetical is left to prompt rule 10.
- **Tense:** labels only, no restructuring.
- Also open: RA-109/I1, RA-103, RA-108, PF-206.
