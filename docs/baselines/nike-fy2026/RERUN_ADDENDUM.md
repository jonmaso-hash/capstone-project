# Nike FY2026 rerun — pre-registered addendum

**Frozen:** 2026-10-04, committed **before** the rerun's first upload. Do not edit after the run starts. Record any correction as an erratum in `RERUN_LEDGER.md`.

The rerun is the Phase 1 acceptance test.

- **Pass A** runs [PROTOCOL.md](PROTOCOL.md) unchanged. It uses the same configuration as the baseline (EDGAR only, paid keys blanked) and is graded against [ANSWER_KEY.md](ANSWER_KEY.md) and every L-number in [BASELINE_LEDGER.md](BASELINE_LEDGER.md).
- **Pass B** runs the production provider configuration, and is graded only against §4.

Phase 1 added behaviour the frozen protocol could not anticipate. This addendum states, in advance, what each new layer must show.

## 1. Setup

**Code.** `main` at or after `ea81470` (PRs #135–#147). No local changes to `.py` files or templates.

**Earlier baseline principals.** The baseline users and document 3117 stay as frozen evidence. One change is made: Application 35's `company_name` becomes `NIKE, Inc. (baseline 2026-10-03)`, because the Intelligence Report looks companies up by name and two "NIKE, Inc." profiles would collide. Document 3117, its chunks, claims, reports and memo are not touched.

**Fresh principals** (prefix `rerun_`): owner, Lite investor, paid investor, staff, anonymous.

- The paid investor gets `InvestorApplication.is_premium=True` as well as an active subscription (erratum E-1).
- The owner's profile is "NIKE, Inc." with a hidden PRIVATE field holding `CANARY-RERUN-5519`.
- For Pass A the profile has **no website and no geography**, as in the baseline.

**Pass A environment.** These keys are blanked in-process: `FILED_API_KEY`, `COMPANYENRICH_API_KEY`, `NEWS_API_KEY`, `CRUNCHBASE_API_KEY`, `USPTO_ODP_API_KEY`, and now also `DATA4B2B_API_KEY`. The settings positive control must print them all `False` from inside the server and the worker, with the negative control printing `True`.

**Pass B environment.** All keys as in `.env`. Before the second upload, the profile gets `company_website=https://www.nike.com` and `geography=Beaverton, OR`.

## 2. Pass A expectations, by layer

| # | Layer | Must show |
|---|---|---|
| 1 | Extraction | 10 slides. `raw_text_full` holds `[[zelda:slide 1..10]]` markers; `raw_text_preview` holds none. No parser or dependency text anywhere. |
| 2 | Chunking | Exactly 10 chunks with `page_number` 1–10 in order, titled with the real slide titles. Every answer-key fact on its slide: Delaware {2,6,8}, 81,500 {2,6}, $52.8B {2,4}, "$52.8 billion" {3}, 46.1% {4}, CIK {8}. `embedding_model` = `semantic-hash-v1` or `hash-v1`, never `claude…`. |
| 3 | Insights | The regex extractor is unchanged (L-010 stays open). Insights recorded as found, not graded. |
| 4 | Claims | `employees` cites **slide 6** and `revenue` cites **slide 3**. `text_excerpt` is the claim's own sentence, ≤300 characters, never a whole chunk. |
| 5 | Truth Delta | Revenue: `no_data` / `period_unknown`, with the SEC observation 46,398,000,000, FY2026, CIK 0000320187, role `can_establish`, origin `sec_filing`. Employees: `no_data` / `no_external_evidence`. `provider_outcomes.dataforb2b` = `unconfigured`. Unscored, or scored only if an establishing row exists (it does: SEC revenue). |
| 6 | Canonical presentation | Truth Delta page: **0 VERIFIED**, rollup "0/2 claims verified (0%)", both icons ❔, revenue note "An external figure was found, but its period could not be confirmed as comparable…". Intelligence Report: "0 of 2 checkable claims verified against a public source; 2 could not be confirmed." Never "external support". "What Zelda noticed" says an external figure was found for revenue, not "no public source". |
| 7 | Retrieval / RAG | Q1–Q7: every source cites a real slide (1–10). No source with relevance 0.000. **Prediction:** every question contains "nike", which matches every slide's footer, so Q5 and Q6 will NOT report `no_relevant_evidence`. This is residual L-002/L-013 (keyword-only retrieval), recorded, not failed. |
| 8 | Intelligence outputs | Profile Analysis and valuation are not exercised (unchanged from baseline). |
| 9 | Memo | Created **after** the Truth Delta report (`memo.created_at` > report time). Built from `GroundedContext`. Contains **no "500 people"** contradiction (L-006 removed from the memo path). Never calls $52.8B "supported", "verified" or "disclosed fact"; states SEC's $46.4B with it. No canary, and no CONNECTED profile value. Cites `[C…]`/`[S…]` refs. No advice language. |
| 10 | Authorization | Same matrix as the baseline. Changed cells: anonymous `analyze/founder` → **403** (was 500, L-016). Search/RAG for Lite and paid investors → 403. Canary visible only to owner and staff. |
| 11 | Idempotence | Re-run verification on the Pass A document (as the Run Verification button does). The SEC observation set, category states, reasons, comparison rows and counts are identical. Exactly one new memo is generated afterwards; its text may differ (model output) and is recorded, not compared. |
| 12 | Ledger | Every L-number marked fixed / still open (deferred to a named workstream) / intentionally changed / newly found. |

## 3. Expected residuals in Pass A

These are recorded and do not fail the run:

- **C01** stays INSUFFICIENT (`period_unknown`), not CONTRADICTED. L-007: claims have no period. The pass condition is that every surface says that same thing.
- **C04 (Delaware)** stays MISSED. Entity Integrity compares the profile, not the deck (L-011).
- **I1/I4/I5** stay unflagged (L-012).
- L-002 (hash vectors, cosine always 0), L-010 (regex insights) and L-023/L-024 stay open.

## 4. Pass B expectations (production providers)

| Provider | Must show |
|---|---|
| DataForB2B | Profile website `nike.com` → free count of 10 → `provider_outcomes.dataforb2b` = **`ambiguous`**, no DataForB2B observation rows, **0 credits spent** (balance before = after). |
| Filed | Geography `Beaverton, OR` → state `OR` (a measured genuine registrar). One state-scoped search plus detail. A business-registration finding may appear; it never contradicts anything on its own. No cross-state search. |
| NewsAPI | Headlines may reach Truth Delta as context. Never an observation. |
| CompanyEnrich / others | Recorded as they behave. Never an establishing observation for a category they do not declare. |
| Revenue / employees | Same canonical states as Pass A. No provider in Pass B can verify or contradict them. |

## 5. Artifacts

Each pass writes JSON under `rerun/pass-a/` or `rerun/pass-b/`, one file per layer:

- extracted text (with markers);
- chunks;
- insights;
- claims;
- observations, with role, origin and provenance;
- `provider_outcomes`;
- report details and canonical states;
- the Truth Delta API payload;
- retrieval results for Q1–Q7;
- the memo;
- the authorization matrix;
- idempotence before/after (Pass A).

No secrets, passwords or keys in any artifact.
