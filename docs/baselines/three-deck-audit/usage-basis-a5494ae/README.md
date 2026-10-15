# RA-109 / I1: usage figures keep their measurement basis, at `a5494ae`

**Separate, additive evidence.** It edits no earlier evidence folder, run ledger, grading, memo, answer key, protocol or frozen fixture. No report was regenerated. No live model run was made.

**Status:** branch `fix/usage-basis-preservation`, pushed and **unmerged**, with no PR.
- RA-109/I1 stays **open** until this deterministic correction is reviewed; a later live acceptance run, if wanted, is a separate step.
- RA-108 and overall Zelda hardening stay open.
- Nothing is deployed, and paid-source Pass B was not run.

| Commit | What |
|---|---|
| `b9cddec` | Starting point (main; PR #281 merged). The evidence-only PR #282 changes no code |
| `a5494ae` | **This fix** (code and tests) |
| this folder | Reproduction, red/green runs, mutations, validation |

## The defect, reproduced on the starting code

[output/repro_before_b9cddec.json](output/repro_before_b9cddec.json) is the pure Traction selection path over memo 97's 12 recorded chunks (`git show ea3ab13:docs/baselines/manychat/narrator-provenance-b9cddec/pass-a/02_chunks.json`). There is no database and no provider. It matches the reviewer's table:

| Stage | At `b9cddec` | At `a5494ae` ([after](output/repro_after_fix.json)) |
|---|---|---|
| Slide 12 collected | `140 000+ bots`, `messages/month` (no number) | `140 000+ bots`, **`500M messages/month`** |
| Document selection | `140 000+ bots` (p10), `500M messages` (p10) | + **`500M messages/month` (p12)** |
| `500M messages` + `500M messages/month` fed directly | collapse to 1 | **2** |
| `500M bots` + `500M messages` | collapse to 1 | **2** |
| `500M messages` + `500 million messages` | 1 | 1 (genuine duplicate) |
| `500M messages` + `600M messages/month` | 2 | 2 |
| `usage_unit('500M messages/month')` | `messages` | `messages` (noun-only contract kept); new `usage_basis(...).label` = **`messages/month`** |

## What changed (`a5494ae`)

| Problem | Fix |
|---|---|
| 1. Number and rate on adjacent lines never formed one fact | `zelda_api/usage_basis.py`: `join_split_usage_lines` joins a one-figure line with the **very next** line only when that line is a usage noun with an optional supported rate, inside one chunk. See the join rules below. The analyzer applies it to Traction only. A Traction candidate built this way carries `joined_lines: True` in its in-memory provenance |
| 2. `_select_insights` deduplicated Traction by number alone | A usage figure's key is now (value, noun, basis). Customer, headcount and money keys are unchanged. The cap stays 3 |
| 3. The claim unit dropped the rate denominator | `financial_metrics.usage_basis()` returns the noun and basis. The basis is `''` (no interval stated), `cumulative` (explicit only: "to date", "cumulative", "total", "since launch", "lifetime", "all-time"), or a rate: `month`, `week`, `day` or `year`. The claim stores the canonical unit (`messages/month`). `usage_unit()` is unchanged for its callers |

**Join rules.** The two lines are refused, and left unchanged, when any of these holds:
- the line above is a label that could name an owner. Only an empty line, a sibling figure line ("140 000+ bots") or a generic heading made of metric and time words ("Traction by Apr-16") is accepted above. The company's own name is refused too (conservative);
- a bare figure sits above (an axis value or a list);
- the line below continues the figure ("via Telegram", or any lower-case start) or is a short organisation label;
- there is a blank line, prose or a second figure between them, or the noun line carries a figure.

Refusals are recorded. The claim task refuses a usage span that exists only by joining a refused pair. This covers an owner label above and also number and noun separated by prose.

**The basis note.** It is built from admitted claims only: category `usage`, value, unit, page and id. It is never built from source text, and it appears only when two claims count the same noun with the **same number** on **different bases**:

> Page 10 states 500M messages without an explicit interval; page 12 states 500M messages/month. These use different measurement bases and need clarification before comparison.

Where it appears:
- in the memo payload as `consistency_notes` (`{kind, refs, note}`), **only when a note exists**. Every other document's payload, and the user prompt, are byte-identical to before;
- in memo prompt rule 11 ("not a contradiction, not a verification result and not an error … never convert a total into a rate or a rate into a total");
- in a "Measurement basis to clarify" block on the Truth Delta page, built from the same claims that page already lists to its viewers.

It does not change states, reasons, scores or Truth Delta's per-claim rows.

**Periods.** `/month` already sets the period layer's `period_kind='monthly'`. It sets **no** `period_end` and no fiscal year, so `as_of` stays "not stated". Slide 10's `500M messages` keeps unit `messages`: no interval is stated, and the "Traction by Apr-16" heading stays slide context only. It is not labelled cumulative.

**No migration** (`unit` is the existing `CharField(max_length=50)`). `makemigrations --check`: no changes.

### Frozen fixtures

[`zelda_api/data/claim_recall/manychat.json`](../../../../zelda_api/data/claim_recall/manychat.json) is unchanged. Its `not_recovered_by_design` entry for slide 12 recorded that RA-109 had not been decided then. The new decision is the additive [`manychat_ra109.json`](../../../../zelda_api/data/claim_recall/manychat_ra109.json): one added claim, `usage 500000000 messages/month`, page 12, `implied`, `period_kind monthly`, as_of not stated.

Three existing tests pinned the old count. They now read **frozen + added** through `tests_claim_extraction_recall.current_expected_claims()` and `added_claims()`:
- `tests_claim_extraction_recall`;
- `tests_claim_currency`, where `claim_count` 3 + 1 added, and the added claim's `time_period` is `/month`;
- `tests_claim_periods`, where `with_period` 0 + 1 added, and no claim acquires a `period_end`.

`data/claim_currency/expectations.json` and `data/claim_periods/expectations.json` are unchanged. Before the update those tests failed exactly where expected (5 failures, all the one added claim: [output/consumers_pinning_the_old_count.txt](output/consumers_pinning_the_old_count.txt)).

Real extraction of the frozen chunks at `a5494ae` ([output/frozen_manychat_payload_after.json](output/frozen_manychat_payload_after.json), throwaway in-memory test DB):
- **Claims:** funding `$23.1M raised` (p2, named) plus three usage claims: `140 000+ bots` (p10), `500M messages` (p10, unit `messages`, context "Traction by Apr-16") and `500M messages/month` (p12, unit `messages/month`, implied, `period_kind` monthly, no `period_end`).
- **Payload:** `consistency_notes` holds the one note above with refs `[C3, C2]` (page 10's claim first). The Truth Delta page note is the same text.

## Regressions ([`zelda_api/tests_usage_basis.py`](../../../../zelda_api/tests_usage_basis.py), 51 tests)

| Required | Tests |
|---|---|
| 1. Stored ManyChat chunks | `FrozenManyChatUsageTests`: three distinct insights and usage claims with pages and units; the rate claim's bounded source sentence, ownership `implied`, no narrator; frozen + additive expectation; slide 4 stays out |
| 2. Join admitted / refused | `SplitLineJoinTests`: same slide admitted; start-of-block and dated heading admitted; only the two lines change. Refused: chunk boundary, intervening prose, blank line, competing figures (three shapes), platform label above, continuation or owner label below. The pattern equals the analyzer's |
| 3. Ownership | `SplitLineOwnershipTests`: a platform rate split across lines is refused even when offered directly as an insight; an unbounded split is refused at the claim layer; the company rate is kept as implied; end-to-end, a Telegram/Kik block yields no figure and no claim; a dated heading over a joined figure stays context. Also `test_the_old_people_control_still_matches_nothing` and the slide 4 chunk unchanged |
| 4. Dedup | `UsageDedupTests`: alternate spellings dedupe (count and rate); a different basis, noun or number survives; customer and money behaviour is unchanged; the cap is unchanged at 3 |
| 5. Rate forms | `UsageBasisFormTests`: 7 monthly forms; day, week and year; no interval; explicit cumulative; unsupported denominators (`per user`, `/quarter`, `per bot`) refused; `usage_unit` noun-only. `UsageBasisClaimTests`: stored units; an unsupported denominator is not stored |
| 6. Periods | `UsageBasisPeriodTests`: the monthly rate has no as-of date and no time wording; slide 10 keeps its slide context and is not cumulative |
| 7. Payload and reader | `BasisNoteInGroundedContextTests`: both facts and pages survive; the note names both refs and both bounded facts; no raw-source, key or canary text; no key without a pair; the prompt carries rule 11. `BasisNoteOnTruthDeltaPageTests`: the owner sees the note; anonymous is redirected; no note without a pair |
| 8. Truth Delta | `BasisNoteIsNotVerificationTests`: with the rate pair present, usage stays `no_data` (INSUFFICIENT), 0 verified and 0 contradicted, the same score, and no basis text in the report details |
| 9. Silence | `BasisNoteTests`: no note for same-basis duplicates, different nouns or different numbers; a cumulative total is described as one |

### Red on the starting code ([output/red_run.txt](output/red_run.txt))

Application code was identical to `b9cddec` (`git diff --quiet HEAD`). Result: **49 tests, 13 failures and 37 errors.** The errors are the helpers that did not exist yet; the failures are the frozen-deck, dedup, unit, claim-layer, payload and page assertions.

The platform-block test passes on the starting code, as a control should: it asserts the absence of a figure or claim.

**Test corrections after the first red attempt** ([output/red_run_first_attempt.txt](output/red_run_first_attempt.txt)):
- **End-to-end platform block.** It first asserted *no Traction insight at all*. On the starting code a bare `messages/month` line is already a figureless Traction insight; it is not a claim. That is pre-existing and outside this scope, so the assertion became "no insight carrying a figure, no claim". The other two corrections below were made for the same reason.
- **Platform-label join test.** The same correction ("no candidate carrying a figure").
- **Claim units test.** It now compares sorted output, because claim order follows insight order and is not part of the contract.
- **Added after red:** the dated-heading test and the pattern-equality guard.

## Mutations ([output/mutations_output.txt](output/mutations_output.txt))

**16 of 16 caught.**
- **How they ran:** one at a time, in the foreground, with the watchdog running. Each file's SHA-256 was verified after restore.
- **Code:** the six mutated source files equal the committed `a5494ae` (hashes checked before and after).
- **Labels:** `zelda_api.tests_usage_basis zelda_api.tests_claim_extraction_recall zelda_api.tests_claim_periods` (88 tests).

| ID | Mutation | Result |
|---|---|---|
| M1 | Lose the rate suffix in the unit | caught (17F, 3E) |
| M2 | Restore numeric-only usage dedup | caught (11F, 3E) |
| M3 | Drop the rate candidate (no join in the analyzer) | caught (10F, 3E) |
| M4 | Bypass the owner-label check above | caught (4F) |
| M5 | Bypass the claim-layer refusal | caught (2F) |
| M6 | Bypass the continuation/owner check below | caught (1F) |
| M7 | Basis note → "These figures contradict each other." | caught (3F) |
| M8 | Drop "not a contradiction" from rule 11 | caught (1F) |
| M9 | Unsupported denominator stored as a bare count | caught (4F) |
| M10 | No record of an unbounded (prose-separated) pair | caught (1F) |
| M11 | Note order by claim id, not page | caught (1F) |
| M12 | `consistency_notes` sent even when empty | caught (1F) |
| M13 | Note for different numbers | caught (1F) |
| M14 | `dated_heading` ignores the joined view | caught (1F) |
| M15 | Cumulative wording ignored | caught (1F) |
| M16 | A bare figure line above treated as a heading | caught (1F) |

**First mutation run** ([output/mutations_first_run.txt](output/mutations_first_run.txt)):
- **Not applied:** M2 and M3. Their multi-line anchors missed a CRLF checkout; the harness now matches CRLF.
- **Survived:** a mutation that removed the joined view from `claim_attribution.source_sentence`. An admitted joined figure has no owner words of its own, so the fallback to the span gives the same sentence and the same `implied` ownership.
- **Consequence:** that change was unobservable, so it was **removed from the code** rather than kept. The docstring now says so. The mutation was replaced by M14, which covers the one place the joined view is observable: `dated_heading`.

## Validation at `a5494ae` ([output/](output/))

**1,264 tests OK** in four sequential batches. Each ran with the CI environment (scratchpad `t.sh`: `DEBUG=True`, memory broker, `--parallel 1`, no bytecode). Free RAM was 1.5–1.9 GB before each batch, and the watchdog logged no process over 1,500 MB ([memwatch.log.txt](output/memwatch.log.txt)).

| Batch | Labels | Result |
|---|---|---|
| A | zelda_api `tests_funding_fidelity`, `tests_claim_context_dates`, `tests_grounded_context`, `tests_memo_persistence`, `tests_memo_list_rendering`, `tests_claim_counts_per_claim`, `tests_canonical_presentation`, `tests_no_investment_advice`, `tests_private_company_presentation`, `tests_source_naming`, `tests_verification_grounding`; `pages.tests_ci_manifest` | 259 OK |
| B | zelda_api `tests_usage_basis`, `tests_claim_extraction_recall`, `tests_claim_currency`, `tests_claim_periods`, `tests_claim_attribution`, `tests_claim_field_binding`, `tests_claim_extraction_scoring`, `tests_financial_fact_semantics`, `tests_three_state_grounding`, `tests_profile_reconciliation`, `tests_dashboard_authorization`, `tests_chunk_boundary`, `tests_boundary_closeout`, `tests_page_provenance`, `tests_verification_no_claims`, `tests_score_follows_verdict`, `tests_summary_follows_verdict`, `tests_report_semantics`; `pages.tests_no_network_in_tests` | 389 OK |
| C | `zelda_api.tests` | 430 OK |
| D | zelda_api `tests_authorization`, `tests_assistant_panel_escaping`, `tests_library`, `tests_terminal_notifications`, `tests_valuation_paywall`, `tests_retrieval`, `tests_principal`, `tests_corroboration`, `tests_source_capabilities`, `tests_verification_starts_together`, `tests_extraction_failures`; `matchmaking.tests_company_overview_identity` | 186 OK |

`manage.py check`: no issues. `makemigrations --check --dry-run`: no changes ([check_and_migrations.txt](output/check_and_migrations.txt)). `tests_usage_basis` is added to the blocking CI job (`.github/workflows/ci.yml`), and `pages.tests_ci_manifest` passes.

**Pre-existing order dependence (not introduced here).** Earlier, on the pre-commit working tree (which still had the later-removed `source_sentence` change), the claim-path modules were run in the same process as `tests_funding_fidelity` and `tests_grounded_context`, in the order shown in [order_dependency_fix_worktree.txt](output/order_dependency_fix_worktree.txt). That run had 7 errors: 4 in `MemoWriterTests` and 3 in `NoRawInputTests`/`OrchestrationTests`, with `messages.create` never called. The **same 7 errors occur on unchanged `b9cddec`** with the same labels minus the new module ([order_dependency_base_b9cddec.txt](output/order_dependency_base_b9cddec.txt)). Both modules pass alone (101 OK), and in batch A. This is recorded, not investigated or fixed here.

## Isolation

- **Databases:** every test used Django's throwaway test database. The evidence payload dump created and destroyed its own in-memory test DB (`file:memorydb_default?mode=memory&cache=shared`).
- **Untouched:** the dev DB (`KCV/db.sqlite3`, SHA-256 `5a0b8c1c…`) and every run copy.
- **Side effect:** an empty, gitignored `db.sqlite3` that `makemigrations --check` created in this worktree was deleted.
- **Not done:** no network, no paid provider, no model call. Memo 97 was not regenerated, and no old artifact was edited.

## Limits and what is still open

- **Note scope:** the note covers the same noun with the same number on different bases. Different numbers on different bases ("500M messages" vs "20M messages/month") get no note by design.
- **Supported rates:** month, week, day and year only. Any other denominator is refused, not stored.
- **Join scope:** only a usage noun line (bots, messages) joins. A company-name label directly above a split figure is refused (conservative). Customer-count lines are not joined.
- **Pre-existing noise:** a bare noun line (`messages/month`) is still a figureless Traction insight when its join is refused. It never becomes a claim.
- **Basis vs period:** the basis is read from the claim's own words. The period layer's `period_kind` and the unit's basis are separate fields and are not reconciled with each other.
- **Not changed:** RA-108 (self-comparison wording), FF-413 (Truth Delta page styling), RA-103 (funding claim from audit-framing slide 2), RA-114, PF-206/FF-311 and the other recorded open items.
- **Not yet observed live:** whether a live memo states the note well (rule 11) is a separate live acceptance step. It was not run here.
