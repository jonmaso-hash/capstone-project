# RA-109 follow-up corrections at `9ec3efa`

**Separate, additive evidence.** It edits nothing in `../usage-basis-a5494ae/`, `../usage-basis-review-200afbc/`, any run ledger, grading, memo, answer key, protocol or frozen fixture. No report was regenerated, and no live model run was made.

**Status:** branch `fix/usage-basis-preservation`, pushed and **unmerged**, with no PR.
- RA-109/I1 stays open until these corrections are reviewed.
- RA-108 and overall Zelda hardening stay open. RA-106's scoped acceptance is unaffected.
- Nothing is deployed, and paid-source Pass B was not run.

| Commit | What |
|---|---|
| `b9cddec` | Application base. Main is `fbb9161`, evidence only (0 non-`docs/` files differ from `b9cddec`), so the branch was not rebased |
| `a5494ae` / `17c541c` | First fix and evidence |
| `200afbc` / `50aada8` | Review corrections and evidence (follow-up review: request changes) |
| `9ec3efa` | **These corrections:** `zelda_api/usage_basis.py`, `zelda_api/intelligence_pipeline.py`, `zelda_api/tests_usage_basis.py` |

## Findings and corrections

"Before" is `200afbc` and "after" is `9ec3efa`. Both ran the same script with the **real** `_analyze_document` and the **real** `extract_claims_from_insights`, in a throwaway in-memory test database. Files: [before](output/repro_before_200afbc.json), [after](output/repro_after_9ec3efa.json), [summary](output/repro_summary.txt).

### P2-1: a generic heading erased the block's platform owner

| Chunk (document subject ManyChat) | `200afbc` | `9ec3efa` |
|---|---|---|
| `Telegram / Traction / 500M / messages/month` | joined; `500M messages/month` stored, implied (analyzer and offered span) | not joined; no claim either way |
| `Telegram / (blank) / Traction by Apr-16 / 500M / messages/month` | the same false claim | none |
| `500M / messages/month / Traction / Telegram` (below) | the same false claim | none |
| control `Traction by Apr-16 / 500M / messages/month` (heading at chunk start) | joined, implied | unchanged |
| control `ManyChat / Traction / 500M / messages/month` | joined, implied | unchanged |

**Correction (`usage_basis._block_label_above` and `_block_label_below`).** A generic metric/time heading is context, not an owner. The walk now passes through it, as it does through blank lines and sibling metrics. The block resolves only at the document's own subject name or at the chunk edge. Any other label, prose line or bare figure refuses the pair, including when a heading sits between it and the figure. Below the figure, a heading is passed through the same way, so an organisation label or a continuation beneath it still refuses.

The claim gate (`unresolved_split`) reuses this rule, so the offered span is refused too.

### P2-2: the initial winner bypassed the unsupported-basis filter

Chunks in this order: `500M messages per 2 months`, `140 000+ bots`, `500M messages`, `500M messages/month`. All score 95.0, and the first wins the tie.

| | `200afbc` | `9ec3efa` |
|---|---|---|
| Traction insights | `500M messages per 2 months`, `140 000+ bots`, `500M messages` | `140 000+ bots`, `500M messages`, `500M messages/month` |
| Claims | bots, messages (the rate is lost) | bots, messages, **messages/month** |
| Basis note | none | the note |
| Control without the unsupported chunk | three facts and the note | unchanged |
| A single unsupported chunk | one insight (`… per 2 months`), no claim | **no Traction insight**, no claim |
| Frozen ManyChat with the unsupported chunk first | `… per 2 months` (p1), bots (p10), messages (p10); no rate; no note | bots (p10), messages (p10), `messages/month` (p12); the note |
| Frozen ManyChat | three facts and the note | unchanged |

**Correction (`intelligence_pipeline._select_insights`).** The eligibility rule ("a usage figure whose basis cannot be represented never becomes a claim") now applies to the initial winner as well as later candidates.
- **An ineligible winner** is replaced by the next eligible candidate in the same order (highest confidence, then document order). It takes no slot and seeds no dedup key: `500M messages per 2 months` parses to 5e8, and it no longer blocks a valid 500M figure.
- **No eligible candidate** means the category yields no insight.
- **Unchanged:** the cap of three, and every non-Traction category.

**Decision to confirm.** The review did not state the expected outcome for a single unsupported candidate. This change drops the Traction insight entirely, consistent with "takes no slot", so the memo gets a Traction gap instead of a self-reported statement with an unrepresentable basis. The alternative is to keep it as an insight that never becomes a claim. That is a one-line change, covered by mutation M31 below.

## Regressions ([`zelda_api/tests_usage_basis.py`](../../../../zelda_api/tests_usage_basis.py), 77 tests)

| Class | Covers |
|---|---|
| `HeadingOwnershipTests` | Five heading shapes:<br>• heading between owner and figure;<br>• blank line and a dated heading;<br>• heading, then a sibling metric;<br>• heading below, then the owner;<br>• blank line, dated heading and a longer label below.<br>Each is tested through the helper, the analyzer's candidates, end-to-end claims, and the span offered straight to the claim task. Positives: heading-only blocks at chunk start (including two headings), company-owned blocks with a heading between, the subject name below a heading |
| `InitialWinnerEligibilityTests` | An unsupported winner first, a supported winner first, a single unsupported candidate, no dedup key seeded from the rejected value, Funding unchanged. Also the review's four-chunk reproduction and its control (analyzer insights and claims), and the frozen ManyChat chunks with an invalid chunk first: all three valid facts, their pages and the neutral note |

**Red on `50aada8`** (application code identical to `200afbc`): [output/red_run_on_50aada8.txt](output/red_run_on_50aada8.txt). Result: **77 tests, 25 failures**, all of them the two reproductions in every form. The positive controls passed on the old code, as they should. No earlier test was changed in this round.

## Mutations ([output/mutations_output.txt](output/mutations_output.txt))

**31 of 31 caught.**
- **How they ran:** one at a time, in the foreground, with the watchdog running. Each file's SHA-256 was verified after restore, and the six mutated files equal the committed `9ec3efa`.
- **Labels:** `tests_usage_basis`, `tests_claim_extraction_recall` and `tests_claim_periods` (114 tests).
- **Carried over:** M1–M26 from `../usage-basis-review-200afbc/`, loaded from that harness unchanged except M24, re-anchored to the new `eligible()` check. All 26 are still caught.
- **New:**

| ID | Mutation | Result |
|---|---|---|
| M27 | A generic heading above resolves the block again (the reviewed short circuit) | caught (12F) |
| M28 | The same below the figure | caught (8F) |
| M29 | A generic heading above treated as an owner (over-refusal) | caught (7F) |
| M30 | The initial winner is not checked for eligibility | caught (5F) |
| M31 | A single unsupported candidate is still emitted | caught (1F) |

## Validation at `9ec3efa`

**1,290 tests OK** in the same four sequential batches as before. No other batches were added.
- **Environment:** CI environment via `t.sh`.
- **Memory:** free RAM was 1.27–1.58 GB before each batch, and the watchdog logged nothing over 1,500 MB ([memwatch.log.txt](output/memwatch.log.txt)).

| Batch | Result |
|---|---|
| A (funding fidelity, grounded context, memo, presentation, CI manifest) | 259 OK |
| B (claim path, including `tests_usage_basis`) | 415 OK |
| C (`zelda_api.tests`) | 430 OK |
| D (authorization, panels, library, notifications, valuation, retrieval, overview identity) | 186 OK |

`manage.py check`: no issues. `makemigrations --check --dry-run`: no changes ([check_and_migrations.txt](output/check_and_migrations.txt)). The pre-existing order-dependence record in `../usage-basis-a5494ae/` is unchanged and was not re-investigated. The established grouping was used.

## Isolation

- **Databases:** test databases only. The reproductions created and destroyed in-memory test databases. A temporary worktree at `200afbc` was used for "before" and then removed.
- **Untouched:** the dev DB and the run copies. The empty `db.sqlite3` that management commands create in this worktree was deleted.
- **Not done:** no network, no paid provider, no model call. No memo was regenerated, and no frozen or historical artifact was edited.

## Limits (unchanged unless noted)

- **New in this round:** a block now needs the document's subject name, or nothing but headings, sibling metrics and blank lines up to the chunk start. A chunk that opens with contact lines (e.g. `angel.co/…`, `mike@…`) above a heading and a split figure now refuses. This is conservative; the frozen deck's slide 12 resolves at its "ManyChat" line before reaching those lines.
- **Carried over:**
  - Same-noun, same-number only for the note.
  - Month, week, day and year rates only.
  - The figureless noun-line insight stays pre-existing noise.
  - The P3 note rounding (`1,234,567` → "1.2M") is still recorded, not changed.
