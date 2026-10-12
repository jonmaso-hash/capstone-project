# Funding-source fidelity: review corrections at `a0ac9ad`

**Separate, additive evidence.** It does not edit [../funding-fidelity-2befa42/](../funding-fidelity-2befa42/README.md),
the live run's ledger, [OWNER_GRADING.md](https://github.com/jonmaso-hash/capstone-project/blob/docs/manychat-postfix-a975af3/docs/baselines/manychat/postfix-a975af3/pass-a/OWNER_GRADING.md)
(branch `docs/manychat-postfix-a975af3`, 88df894), memo 94, memos 90/91 or documents 3132/3133.

**Status:** RA-106 and Zelda hardening stay pending. Memo 94 is not regenerated. Not deployed.

## Review blockers on `2befa42`, and the correction

| # | Blocker (review case) | At 2befa42 | At a0ac9ad |
|---|---|---|---|
| 1 | "The company states it has raised $23.1M [S3] and reports 140,000+ bots." | "Pitch Deck Hunt reports it has raised $23.1M [S3] and reports 140,000+ bots." (Pitch Deck Hunt reports both) | "Pitch Deck Hunt lists **the company** as having raised $23.1M [S3] and **the company** reports 140,000+ bots." |
| 2 | "The company is not raising capital" / "Use of proceeds: Not found" / "In 2015 the company was seeking $5M" | Each set `raise_supported=True`, so "this raise" premises were kept | None counts. Only an affirmative, company-specific current raise counts: a public profile raise above 0, or "Seeking $5M seed round" / "We are raising …" / "ManyChat is raising …" |
| 3 | "The company reports $23.1M revenue [S4]" / "Crunchbase reports $23.1M raised [S4]" | Both gained "(per Pitch Deck Hunt)" by amount alone | Both unchanged. The cited item decides; an uncited figure must read as funding, and the sentence may not name another source |

**Found and fixed while correcting:**
- **Self-reported in another clause.** A first correction turned memo 94's "two self-reported usage figures" (the company's own counts, in another clause) into "two reported by Pitch Deck Hunt usage figures". The memo-94 probe caught it. "self-reported" is now reassigned only in the figure's own clause, when nothing else cited there is the company's. Parentheses and citations do not split clauses.
- **Dead "$23.1M revenue" check.** Mutation G13 first survived, which showed the check never matched: a `^` anchor combined with a `.match()` position. A new test ("Investors cite $23.1M revenue.") failed on the real code, the anchor was fixed, and the whole suite was re-run.

## Results

[output/review_cases_probe.txt](output/review_cases_probe.txt): the review cases and their variants, in memory.

[output/memo94_probe_corrected.txt](output/memo94_probe_corrected.txt): the guard applied in memory to memo 94's stored sections.
- The sections are read with `git show 88df894:…/09_memo.json` (sha256 `c9e52f30…`).
- The `KCV-mc-postfix` worktree folder was found deleted. Git lists it as prunable; the branch is intact on the remote.
- **9 sections change. "Two self-reported usage figures" stays the company's.** No "deck states", "Pitch Deck Hunt reports" or "two reported by" appears.

**Regressions** (`zelda_api/tests_funding_fidelity.py`), using the review's exact sentences:

- **Clause attribution:**
  - the uncited-bots review case;
  - the cited-bots case;
  - the company-named case with a comma before "and";
  - "self-reported" in another clause;
  - "self-reported" covering the company's figures.
- **Raise evidence:**
  - the three review statements;
  - a negation with an amount;
  - a past raise without a year;
  - another company's raise;
  - a third-party report;
  - three affirmative positives.
- **Identity:**
  - both review sentences;
  - a citation to a non-narrated item;
  - uncited revenue;
  - uncited Crunchbase;
  - revenue beside a funding word;
  - funding wording absent;
  - the narrated item still attributed beside a same-amount revenue figure.

`tests_claim_context_dates` now expects the clause-preserving wording.

[output/mutations_output.txt](output/mutations_output.txt): **27 mutations, all red.**
- **F (original rules, retargeted):** F1, F2, F4–F12, F14.
- **G1–G6, clauses:**
  - G1 the "the company states" lead-in left in place;
  - G2 the following predicate not given back to the company;
  - G3 the narrator as recipient;
  - G4 "self-reported" in another clause;
  - G5 "self-reported" covering the company's figures;
  - G6 citations split at their commas.
- **G7–G11, raise evidence:** negation, past or dated raise, any subject, a third party's report, any raise word.
- **G12–G15, identity:** citation ignored, "$23.1M revenue", another named source, uncited figure with no funding wording.

[output/validation_output.txt](output/validation_output.txt), all on `a0ac9ad` with isolated test databases:
- `check` clean; `makemigrations --check` reports no changes.
- 210 + 76 + 428 (`zelda_api.tests`) + 103 + 426 (`matchmaking.tests`) + 147 (accounts/pages) = **1,390 tests, all OK**.
- The first background run was stopped by Claude Code for low system memory during `zelda_api.tests`. With the owner's go-ahead, the remaining four batches were run one at a time.

## Unchanged

- Structured periods, Truth Delta comparison and scoring.
- Tier permissions: the Lite API is still `tier: lite`, `locked: true`, with the same five sections.
- The raw-source memo boundary; the memo payload.
- Memo 94 and the frozen evidence.

## Still open

- **RA-106:** until a newly generated memo is graded.
- **Upside scenario:** the "fully deployed into growth" hypothetical is left to prompt rule 10.
- **Tense:** the guard labels without restructuring, so "was a Series A" keeps its tense.
- Also open: RA-109/I1, RA-103, RA-108, PF-206.
