# Memo-98 output rules: containment corrections at `3e0fa33`

**Separate, additive evidence.** It edits nothing in `../output-fidelity-2fb8530/` (kept as review material for `2fb8530`), any run ledger, grading, memo, answer key, protocol or frozen fixture. Memo 98 is not edited or regenerated. No live model run was made.

**Status:** branch `fix/usage-basis-output-fidelity`, pushed and **unmerged**, with no PR. Main is still `d276918`.
- RA-109 live output acceptance stays open.
- RA-106's scoped acceptance is unchanged.
- RA-108, overview coverage, styling, the P3 notes and overall hardening are out of scope and still open.

| Commit | What |
|---|---|
| `2fb8530` / `60a5b3a` | First output-fidelity correction and its evidence (review: request changes) |
| `3e0fa33` | **These corrections:** `zelda_api/basis_fidelity.py` (per-pair facts and sentence-to-pair resolution), `zelda_api/funding_fidelity.py` (per-item total support), `zelda_api/tests_output_fidelity.py` |

## The three findings and what changed

### P2-1: a usage note rewrote an unrelated metric

| Input (usage note C3/C2 active, revenue C8 admitted) | `2fb8530` | `3e0fa33` |
|---|---|---|
| `Monthly revenue is overstated [C8].` | the usage clarification, citing [C8] | unchanged |
| `The cumulative figure for revenue is $10M [C8].` | "The figure stated without an explicit interval for revenue …" | unchanged |
| `The monthly message figure [C2] is overstated, and revenue is overstated too [C8].` | the whole sentence replaced, citing [C2] [C8] | unchanged (the revenue clause is kept; C8 never lands on a usage clarification) |
| `The monthly figure [C2] and the other figure [C8] look overstated.` | replaced | unchanged |

### P2-2: pairs shared the first pair's wording and one cumulative flag

| Input (notes C3/C2 messages, C5/C6 bots/day, C7/C9 cumulative/week) | `2fb8530` | `3e0fa33` |
|---|---|---|
| `The daily bot figure [C6] is overstated compared with the bare bot count [C5].` | "… relates to the **monthly** figure … [C6] [C5]." | "How the figure stated without an explicit interval relates to the **daily** figure needs clarification before either is relied on [C6] [C5]." |
| `The cumulative figure [C3] sits beside a monthly rate [C2].` | unchanged (C7's cumulative fact disabled the repair) | "The figure stated without an explicit interval [C3] sits beside a monthly rate [C2]." |
| `The cumulative figure [C7] sits beside a weekly rate [C9].` | unchanged | unchanged (C7 really is cumulative) |
| Reversed notes and items | — | identical output |

**Correction.** Each note is its own `Pair`, with its own refs and members (statements repeating a pair claim's figure on the same page), clarification, and cumulative support. A sentence is acted on only when it resolves to **exactly one** pair:

| Order | Route | Resolves when |
|---|---|---|
| 1 | Citations | **Every** cited ref is that pair's |
| 2 | Noun | Nothing is cited, and the counted noun names exactly one pair |
| 3 | Paragraph | Nothing is cited and there is no noun: the nearest earlier sentence in the **same paragraph or list item** that resolved (this keeps memo 98's uncited sentence corrected) |
| 4 | Sole pair | Nothing is cited, and the context has exactly one pair |

**Never resolved:** a sentence naming another metric (revenue, customers, users, funding, …), or citing anything outside one pair. The judgment rule then uses that pair's clarification. The referent rule uses that pair's cumulative support only.

### P2-3: one source's stated total licensed another's

| Input (C1 `$23.1M raised` by Pitch Deck Hunt; C5 `$10M raised in total` by Other Source; both item orders) | `2fb8530` | `3e0fa33` |
|---|---|---|
| `Pitch Deck Hunt lists $23.1M as the total amount raised [C1].` | unchanged | "… as the amount raised [C1]." |
| `Other Source lists $10M as the total amount raised [C5].` | unchanged | unchanged (C5 states a total) |
| Both clauses in one sentence | unchanged | C1's "total" dropped; C5's kept |
| `Pitch Deck Hunt lists $23.1M as the total amount raised.` (uncited) | dropped | dropped (the item resolves by its amount) |

**Correction.** Total support is judged only for the item or items the clause states: by its citations, else by its amount.

### Memo 98 repairs unchanged

The replay at `3e0fa33` ([output/replay_memos_96_97_98.json](output/replay_memos_96_97_98.json)) is **identical** to the `2fb8530` replay:

| Memo | Sections differing from stored |
|---|---|
| 98 | the same four sections, with the same repaired text |
| 97 | none |
| 96 | only the previously accepted FF-405 `zelda_advantage` wording |

Memo 98's actual repaired passages:

> **risk_assessment:** "How the figure stated without an explicit interval relates to the monthly figure needs clarification before either is relied on." (resolved by its paragraph: the preceding sentence cites [C3, S2] and [C2, S3])
>
> **supported_points:** "Pitch Deck Hunt lists $23.1M as the amount raised [S4]." / "… the fundraising narrative Pitch Deck Hunt has put forward …"
>
> **what_would_change_the_picture:** "… how long the company can operate — from the dated cash and burn alone, since the capital narrated as raised is historical funding, not cash on hand [S4]."
>
> **questions_for_management:** "… how does that translate to runway — from the dated cash and burn alone, since the $23.1M (per Pitch Deck Hunt) narrated as raised is historical funding, not cash on hand [S4]?"

## Evidence

### Red

Both runs used the application code at `60a5b3a` (= `2fb8530`).

- **First run** ([output/red_run_on_60a5b3a.txt](output/red_run_on_60a5b3a.txt)): **38 tests, 18 failures**, all the reproductions: helper, memo writer, two pairs, cumulative only in one pair, both funding item orders, and the paragraph-resolved memo-98 passage with an unrelated item 2. The earlier 20 tests passed.
- **Three regressions added after the first red,** one for each new gate: a pair ref beside an unrelated ref; two pairs resolved by paragraph; no inheritance across list items. The full current file was then run against `60a5b3a` in a temporary worktree ([output/red_run_all_41_on_60a5b3a.txt](output/red_run_all_41_on_60a5b3a.txt)): **41 tests, 20 failures**.
  - The two-pair paragraph test passes on the old code **by coincidence**: the old code always used the first pair's "monthly" wording.
  - The paragraph association it pins is covered by mutation C5.
- **Added after the first mutation run:** one control, a sole-pair sentence that is not about the bases keeps its judgment.

### Regressions ([`zelda_api/tests_output_fidelity.py`](../../../../zelda_api/tests_output_fidelity.py), 42 tests)

| Class | Covers |
|---|---|
| `BasisContainmentTests` | Unrelated monthly revenue (3 forms); unrelated cumulative referent (2); mixed sentence; the memo-98 passage resolved by its paragraph beside an unrelated item; the second pair's wording and citations; per-pair cumulative support; two-pair refs and an ambiguous uncited sentence left alone; note and item order |
| `BasisResolutionTests` | A pair ref beside an unrelated ref; two pairs resolved by paragraph (with statement refs S2/S3); no inheritance across list items; a sole-pair sentence not about the bases |
| `FundingTotalPerItemTests` | C1 corrected beside C5 (both orders); C5's stated total kept (both orders); separate clauses each keep their own support; an uncited figure resolves by its amount |
| `PipelineContainmentTests` | The memo writer with three notes and a revenue item: the revenue sentences are stored unchanged; the bot pair gets the daily clarification with [C6] [C5]; C3/C2 is corrected while C7/C9 is kept |
| Carried | `Memo98ReplayTests`, `PipelineAppliesTheRulesTests`, `BasisGuardTests`, `FundingSourceAndRunwayTests`: unchanged and passing |

### Mutations ([output/mutations_output.txt](output/mutations_output.txt))

**24 of 24 caught on the committed code.**
- **How they ran:** one at a time, in the foreground, with the watchdog running. Each file's SHA-256 was verified after restore.
- **Labels:** `tests_output_fidelity`, `tests_funding_fidelity` and `tests_usage_basis` (186 tests).
- **Carried mutations:** O1–O6, O8, F1–F7 and F9, re-anchored where the code changed.
- **New:**

| ID | Mutation | Result |
|---|---|---|
| C1 | Unrelated-metric gating removed | caught |
| C2 | A sentence citing a pair ref and an unrelated ref resolves to the pair | caught |
| C3 | Every pair worded with the first pair's clarification | caught |
| C4 | One cumulative fact anywhere licenses every pair | caught |
| C5 | No paragraph association | caught |
| C6 | Paragraph association crosses list items | caught |
| C7 | Any item's stated total licenses every item | caught |
| C8 | An uncited clause no longer resolves its item by amount | caught |
| C9 | A statement repeating a pair claim is not counted as the pair's | caught |

**First run** ([output/mutations_first_run.txt](output/mutations_first_run.txt)): 23 of 25 caught.
- **O3** ("a judgment need not be about the bases") **survived.** A sole-pair sentence that is not about the bases had no test, so the control above was added; O3 is now caught.
- **O7** ("the guard acts without a basis note") **survived.** With no note there is no pair, so no sentence can resolve. That early return was unobservable, so it was **removed from the code**, and the final run omits O7.

### Validation at `3e0fa33`

**1,332 tests OK** in the established four sequential batches. Free RAM was 1.59–1.80 GB before each batch, and the watchdog logged nothing over 1,500 MB.

| Batch | Result |
|---|---|
| A (output fidelity, funding fidelity, grounded context, memo, presentation, CI manifest) | 301 OK |
| B (claim path including usage basis) | 415 OK |
| C (`zelda_api.tests`) | 430 OK |
| D (authorization, panels, library, notifications, valuation, retrieval, overview identity) | 186 OK |

`manage.py check`: no issues. `makemigrations --check --dry-run`: no changes.

## Isolation and limits

- **Isolation:** test databases only (the red run on old code used a temporary worktree that was then removed). No network, provider or model call; no memo regenerated; no frozen artifact edited.
- **Resolution is deliberately conservative.** An uncited sentence with no noun, outside a resolved paragraph, among several pairs, is left as written: a missed correction rather than a wrong one. A sentence that also names another metric is never corrected, even if it also misstates the usage basis.
- **Detection stays lexical:** judgment words, basis words, "the cumulative <figure word>", "the company <verb>" in the narrative clause, and runway/operate verbs with a funding-naming denominator.
- **Not proven live:** live behaviour still needs a post-merge run after review.
