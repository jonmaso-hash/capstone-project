# RA-109 review corrections at `200afbc`

**Separate, additive evidence.** It edits nothing in `../usage-basis-a5494ae/`, any run ledger, grading, memo, answer key, protocol or frozen fixture. No report was regenerated. No live model run was made.

**Status:** branch `fix/usage-basis-preservation`, pushed and **unmerged**, with no PR.
- RA-109/I1 stays open until the corrections are reviewed.
- RA-108 and overall Zelda hardening stay open. RA-106's scoped acceptance is unaffected.
- Nothing is deployed, and paid-source Pass B was not run.

| Commit | What |
|---|---|
| `b9cddec` | Application base (unchanged). Main is now `fbb9161` (PR #282, evidence only: 0 non-`docs/` files differ from `b9cddec`), so the branch was **not rebased** |
| `a5494ae`, `17c541c` | First fix and its evidence (reviewed: request changes) |
| `200afbc` | **These corrections** |

## Findings and corrections

All "before" rows were reproduced on `a5494ae` with the **real** `_analyze_document` and the **real** `extract_claims_from_insights`, in a throwaway in-memory test database ([output/repro_before_a5494ae.json](output/repro_before_a5494ae.json)). The "after" rows are the same script at `200afbc` ([output/repro_after_200afbc.json](output/repro_after_200afbc.json)). Summary: [output/repro_summary.txt](output/repro_summary.txt).

### 1. A blank or sibling line hid a platform owner (P2)

| Input (document subject ManyChat) | `a5494ae`: stored claim | `200afbc` |
|---|---|---|
| `Telegram / (blank) / 500M / messages/month` | `500M messages/month`, implied | none |
| `Telegram / 100M bots / 500M / messages/month` | `500M messages/month`, implied | none |
| `500M / messages/month / Telegram Messaging Service` | `500M messages/month`, implied | none |
| control: `Telegram / 500M / messages/month` | none | none |
| The same three spans handed straight to the claim task | stored as implied | none |
| `ManyChat / 140 000+ bots / 500M / messages/month / Launching on Facebook` | `500M messages/month` implied, `140 000+ bots` | unchanged |
| `ManyChat / (blank) / 500M / messages/month` | `500M messages/month`, implied | unchanged |

**Correction (`zelda_api/usage_basis.py`).** The join now resolves the **block**, not the neighbouring line.
- **Walking up:** blank lines and sibling metric lines are crossed. A sibling metric is a figure plus up to four lower-case or generic words, with no capitalised name.
- **Above:** the first other line must be a generic heading (metric and time words) or the **document's own subject name**. Otherwise the chunk must start. Any other label, prose line or bare figure refuses.
- **Walking down,** the same way: a continuation ("via …", or a lower-case start) or a title-case organisation label of up to six words refuses. An ordinary statement ("Launching on Facebook") ends the block.
- **Subject names:** these come from `claim_attribution.company_names(document)`. They are passed by `_analyze_document` (new `_smart_extract(subject_names=…)`) and by the claim task (also to `dated_heading`). Without them, a label naming the subject is an unknown owner and refuses.

**Claim admission (`truth_delta_tasks`).** A usage span whose figure stands alone on a line of its chunk exists only by joining. It is admitted only if the same rule, with the subject names, joined exactly that pair (`unresolved_split`).
- Ownership is never read from the bare joined span.
- A span that is simply not in its chunk keeps the earlier behaviour, unchanged here.
- `refused_split` and the unbounded-pair record from `a5494ae` are replaced by this positive check.

### 2. Numeric and compound denominators were simplified (P2)

| Source text | `a5494ae` stored unit | `200afbc` |
|---|---|---|
| `500M messages per 2 months` | `messages` | refused (no claim) |
| `500M messages/month per user` | `messages/month` | refused (no claim) |
| controls `500M messages per month`, `500M messages/month`, `2M messages per day` | `messages/month`, `messages/month`, `messages/day` | unchanged |

**Correction (`financial_metrics.usage_basis`).** An explicit denominator is recognised by its introducer alone ("/", "per", "each", "every", or "a" before a period word). What follows must be exactly one supported period word.
- **Refused:** numeric (`per 2 months`, `/2 months`, `every 2 months`), compound (`/month per user`, `per month per user`, `per month, per user`, `/day/user`) and hyphenated or unsupported rate adjectives (`bi-monthly`, `quarterly`). None is ever simplified to a bare count or a plainer rate.
- **Selection:** `_select_insights` gives such a candidate no slot and never keys it as a bare count.

### 3. Unrelated cumulative words changed the basis (P2)

| Source text | `a5494ae` | `200afbc` |
|---|---|---|
| `500M messages with lifetime customer support` | `messages (cumulative)` | `messages` |
| `500M messages; bots tracked since launch` | `messages (cumulative)` | `messages` |
| control `500M messages to date` | `messages (cumulative)` | unchanged |

**Correction.** Cumulative wording counts only inside the figure's own phrase:
- before the noun: "cumulative", "total", "lifetime", "all-time";
- directly after it, optionally after its verb: "to date", "cumulatively", "in total", "all-time", "since inception/launch/founding".

A regression checks that such wording elsewhere in the text creates no false basis note.

### P3, recorded and not changed

`format_count` rounds large non-round values to one decimal place in the note, e.g. 1,234,567 → "1.2M". Per the review this is tracked as a separate P3 precision note. The frozen 500M case is unaffected.

## The accepted behaviour, re-checked on the frozen chunks

Before and after are identical ([repro_summary.txt](output/repro_summary.txt)):
- **Traction insights:** `140 000+ bots`, `500M messages`, `500M messages/month`.
- **Claims:** `$23.1M raised` (named), `500M messages/month` (`messages/month`, implied), `500M messages` (`messages`, implied), `140 000+ bots` (`bots`, implied).
- **Note:** the one note "Page 10 states 500M messages without an explicit interval; page 12 states 500M messages/month. These use different measurement bases and need clarification before comparison." It is a clarification, not verification and not a contradiction.

## Regressions ([`zelda_api/tests_usage_basis.py`](../../../../zelda_api/tests_usage_basis.py), 64 tests)

New classes, with the real analyzer and claim task where the finding needs them:

| Class | Covers |
|---|---|
| `BlockOwnershipTests` | Seven platform shapes: owner above a blank line, above a sibling metric, both; a longer label below; a label below a blank line; a label below a sibling metric; `FB Messenger` above two blank lines. Each is checked against the helper, the analyzer's candidates, end-to-end claims, and spans handed straight to the claim task. Positive company-owned blocks are kept as implied. Unknown vs subject labels are tested with and without names |
| `DenominatorTests` | Eight unrepresentable forms refused. Ten supported controls, including "every month", a trailing period, and trailing words after the rate. Selection gives no slot to an unrepresentable rate. The claim task stores neither reproduced form |
| `CumulativeBindingTests` | Four "belongs elsewhere" negatives and seven own-phrase positives. The claim task and the basis note do not borrow cumulative wording |

**Contract-driven test updates.** The join now needs the document's subject names to admit a block labelled with that name.
- `SplitLineJoinTests`, same-slide test: passes `['ManyChat']`, and also asserts that without names the text is unchanged.
- `SplitLineJoinTests`, "only the two lines": uses a generic `Traction` heading instead of a prose line. Prose above a block is now an unresolved owner.
- `tests_claim_extraction_recall.assert_sources`: builds the joined view with the fixture's subject name, as `extract()` sets it.
- **Unchanged:** the earlier ownership negatives.

**Red on `a5494ae`** ([output/red_run_on_a5494ae.txt](output/red_run_on_a5494ae.txt)): 64 tests, **28 failures and 32 errors**.
- The errors are the new `names` / `subject_names` parameters.
- The failures are the semantic reproductions: real claims stored for the platform blocks, simplified denominators, and borrowed cumulative bases.

## Mutations ([output/mutations_output.txt](output/mutations_output.txt))

**26 of 26 caught.**
- **How they ran:** one at a time, in the foreground, with the watchdog running, and each file's SHA-256 verified after restore. All six mutated files equal the committed `200afbc`.
- **Labels:** `tests_usage_basis`, `tests_claim_extraction_recall` and `tests_claim_periods` (101 tests).
- **Carried over:** M1–M16, re-anchored where the code changed:
  - M5 is now the admission gate;
  - M10 is now "the analyzer does not pass the subject names".
- **New for the review findings:**

| ID | Mutation | Result |
|---|---|---|
| M17 | A blank line above erases the owner context | caught (9F) |
| M18 | A sibling metric above erases the owner context | caught (9F) |
| M19 | Only labels of up to two words count below | caught (4F) |
| M20 | A blank line below ends the block | caught (4F) |
| M21 | A numeric denominator falls back to a bare count | caught (4F) |
| M22 | A compound denominator keeps the first rate | caught (6F) |
| M23 | Cumulative wording borrowed from anywhere after the noun | caught (4F) |
| M24 | An unrepresentable rate keeps a selection slot | caught (1F) |
| M25 | Any label passes as the subject | caught (33F) |
| M26 | Unsupported rate adjectives (`bi-monthly`) accepted | caught (1F) |

## Validation at `200afbc`

**1,277 tests OK** in the same four sequential batches as at `a5494ae`, so the counts are comparable. No other batches were added.
- **Environment:** the CI environment via `t.sh`.
- **Memory:** free RAM was 1.48–1.85 GB before each batch, and the watchdog logged nothing over 1,500 MB.

| Batch | Result |
|---|---|
| A (funding fidelity, grounded context, memo, presentation, CI manifest) | 259 OK |
| B (claim path: usage basis, recall, currency, periods, attribution, binding, scoring, grounding, reconciliation, dashboards, boundaries, verdicts, no-network guard) | 402 OK |
| C (`zelda_api.tests`) | 430 OK |
| D (authorization, panels, library, notifications, valuation, retrieval, overview identity) | 186 OK |

`manage.py check`: no issues. `makemigrations --check --dry-run`: no changes ([check_and_migrations.txt](output/check_and_migrations.txt)). The pre-existing order dependence recorded in `../usage-basis-a5494ae/` (7 errors with the claim modules first, identical on `b9cddec`) is unchanged and was not re-investigated. The established batch grouping was used.

## Isolation

- **Databases:** every test used Django's test database. The reproductions created and destroyed in-memory test databases. A temporary worktree at `a5494ae` was used for the "before" run and then removed.
- **Untouched:** the dev DB and the run copies. The empty `db.sqlite3` that management commands create in this worktree was deleted.
- **Not done:** no network, no paid provider, no model call. No memo was regenerated, and no frozen or historical artifact was edited.

## Limits

- **Subject names:** the join needs the document's subject names to admit a block labelled with them. A deck that labels its own stats with a different brand or product name is refused (conservative).
- **Prose above a block:** prose in the block's upward walk refuses. So does a chart axis value (a bare figure) anywhere above in the same block.
- **Carried from `a5494ae`:** the note covers the same noun with the same number only; supported rates are month, week, day and year; a figureless noun line can still be a Traction insight but never a claim; and the P3 rounding above.
