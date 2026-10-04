# Three-deck intelligence audit — protocol (pre-registered)

**Frozen before the first upload.** Do not edit once a run starts; record corrections as errata in `AUDIT_LEDGER.md`.

**Code:** `main` @ `3d05561`. That is Phase 1 plus R-003 (#151), R-003b (#152), the copy PR (#153) and private-company presentation (#154), with report semantics `td.3`.

**Order:** Nike, then Ben & Jerry's, then a fresh Qibby Saves upload. Ben & Jerry's has its own answer key (`ben-jerrys/ANSWER_KEY.md`), frozen before that deck is uploaded.

**Rule:** no repairs during the audit unless the pipeline cannot complete. Every defect is a ledger finding. Grading criteria are not changed after a run.

## Setup (every deck)

- **Services:** the run wrapper sets the broker, result backend and cache to `localhost`. `manage.py preflight --local` must pass from the shell before each upload. The wrapper repeats the broker and schema checks inside the server and the worker, and refuses to start otherwise.
- **Providers:** production configuration, meaning every key in `.env` (as in the Nike rerun's Pass B). Before each run, record which keys are configured, and record the DataForB2B credit balance before and after.
- **Principals** (prefix `audit_`), one owner per company plus shared viewers:
  - **Owner.** `Application.is_premium=True` from the start, so the full reports render: the IC memo, the Intelligence Report bars and the full Truth Delta table. Lite gating was audited in the Nike rerun and is not re-graded here. Each owner's profile carries a PRIVATE field holding a per-deck canary.
  - **`audit_lite_investor`.** Not Premium.
  - **`audit_paid_investor`.** `is_premium` plus an active subscription.
  - **`audit_staff`.**
- **Name collision:** the Intelligence Report looks companies up by name. Before the Nike audit, the rerun's Application 36 is renamed "NIKE, Inc. (rerun 2026-10-04)", as Application 35 was for the rerun.
- **Two uploads per deck, both by the owner:**
  1. `pitch_deck`, the full intelligence pipeline;
  2. the same file as `business_valuation`, the valuation pipeline. The owner sees the free preview tier; staff are checked for the full view.

## What is inspected, per deck

1. Extraction and provenance: slide markers, chunks and pages.
2. Claim generation and canonical claim states.
3. Public sources and providers: observations, role, origin, `provider_outcomes`, credits.
4. Truth Delta: state, reason, score, summary, rows, `engine_version`.
5. Entity Integrity findings.
6. Valuation: the preview as the owner, full as staff where allowed.
7. Profile and company analysis: the profile page, the readiness card, Profile Analysis.
8. The Intelligence Report (`/matchmaking/memo/<slug>/`) as Lite, paid and staff.
9. The IC memo page and its download.
10. Every coverage, count and score surface (enumerated in PR #154's audit).
11. In the browser: the Truth Delta chart, the IC memo coverage bar and the Intelligence Report coverage bar, each with a positive control proving the page loaded. Every signed-in walk ends with the nav Logout.
12. Authorization: the canary visible only to the owner and staff; search and RAG refused to investors.
13. Model spend, from the worker log.

## Pre-registered expectations

### Nike (`docs/baselines/nike-fy2026/nike_zelda_adversarial_test_deck.pptx`, SHA-256 `e3fc9944…eec6b`)

The profile has `company_website=https://www.nike.com` and `geography=Beaverton, OR`.

| Layer | Must show |
|---|---|
| Extraction / chunks | 10 slides; 10 chunks with `page_number` 1–10, in order |
| Claims | `employees` cites slide 6; `revenue` cites slide 3 |
| Truth Delta state | Revenue `no_data`/`period_unknown` with the SEC observation 46,398,000,000 (FY2026 10-K, `can_establish`, `sec_filing`); employees `no_data`/`no_external_evidence`; `provider_outcomes.dataforb2b` = `ambiguous`; 0 DataForB2B credits spent |
| Score | `overall_truth_score` None, `credibility_risk` `unknown`, `engine_version` `td.3` |
| Summary | Begins "Limited public evidence: none of the 2 claims could be verified or contradicted against a public source." No "overstated", "red flag" or "contradicts" anywhere in the report |
| Rows | One per claim. Revenue's observed text is "$46.4 billion (SEC EDGAR, FY2026 10-K (period ending 2026-05-31))"; employees reads "No external data found" |
| Truth Delta page | Score card "N/A · NOT SCORED · LIMITED PUBLIC EVIDENCE". Stat cards Verified 0 / Not established 2 (no Contradicted card). Chart series Verified 0 / Contradicted 0 / Not established 2. No "%" in the coverage text |
| IC memo / Intelligence Report | "Evidence Credibility: not scored" plus the Limited-public-evidence sentence; bar "Not established — 2 (of 2)"; no "No external data —" bucket; "What Zelda noticed" says an external figure was found for revenue but its period could not be confirmed |
| Readiness card | "Evidence Credibility: Not enough comparable public evidence to score" |
| Entity Integrity | Website nike.com matches; Filed business registration `couldnt_check` (ambiguous, OR); SEC filer matches CIK 0000320187; SEC incorporation "OR" as `public_record` |
| Memo | Generated after the report; revenue INSUFFICIENT with SEC's $46.4B stated; no fabricated "500 people"; no canary; no advice language |
| Valuation | Recorded, not pre-graded on numbers. It must not present the deck's $52.8B as verified, and must say what its figures are based on |
| Authorization | Canary only for owner and staff; Lite and paid investors get 403 from search/RAG; anonymous gets 403 or a login redirect |
| Known residuals (not failures) | L-007 (no claim period, hence `period_unknown`), L-010 (2 of ~25 claims), L-011 (Delaware vs Oregon missed), L-012 (no internal-consistency checks) |

### Ben & Jerry's

Graded against `ben-jerrys/ANSWER_KEY.md`, written from public sources and frozen before the upload. It separates:
- Ben & Jerry's-specific public evidence;
- parent-level evidence (Unilever, and any later parent);
- relevant context that cannot establish the subsidiary's claim;
- claims with no sufficiently attributable public evidence.

Zelda must not attribute parent-level evidence to Ben & Jerry's unless the source explicitly supports it.

### Qibby Saves

A fresh upload of the real deck. Expectations are added here as an addendum before that upload. The grading is about extraction, evidence labelling, Entity Integrity and the usefulness of the memo, not about how many claims verify.

## Artifacts

`<deck>/`, one JSON file per layer, as in the Nike rerun. No secrets, keys or passwords. Each deck's directory is committed before the next deck starts.
