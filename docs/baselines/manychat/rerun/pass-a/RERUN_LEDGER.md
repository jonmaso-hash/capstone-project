# ManyChat — Pass A rerun ledger at `458bdc9`

Graded against the frozen [../../ANSWER_KEY.md](../../ANSWER_KEY.md), [../../LEDGER.md](../../LEDGER.md)
and [../../../three-deck-audit/PROTOCOL.md](../../../three-deck-audit/PROTOCOL.md), with the base rules of
[../../../nike-fy2026/PROTOCOL.md](../../../nike-fy2026/PROTOCOL.md). **None of those files is edited.**
"Frozen" below means the frozen narrow run: document 3129 at `bcb295a`. That run did not cover the
five-principal matrix, retrieval or Q1–Q7, so those rows have no "before".

**Status: ungraded by the owner.** The grades below are the run's own reading against the key.
Hardening stays pending until the owner grades this ledger.

## Run record

| Item | Value |
|---|---|
| Date | 2026-10-10 PDT (upload 2026-10-11 00:55:57 UTC) |
| Order | After the Ben & Jerry's ledger was committed locally (`3a46844`) |
| Code state | `458bdc9`, same worktree, server (pid 20000) and worker (pid 3816) as the Ben & Jerry's rerun. No `.py` or template changes |
| Deck | `manychat_series_a_audit_deck.pptx`, 175,622 bytes, SHA-256 `be7a7171bbc84b9895a45adfbc41f2533f3d23b3a4a561c82a8d9de6b94f3ef1`. Matches the key, on disk and inside the upload process just before the POST. **One upload** |
| Document | **3133**, `analyzed`, `verification_state=complete` |
| Pass | A only. Pass B not run |
| Environment | Server and worker `BASELINE-ENV-CHECK`: six paid keys `False`, ANTHROPIC `True`. Truth Delta `provider_outcomes.dataforb2b=unconfigured` |
| Broker / schema | Both processes: all four targets `redis://localhost`; `SCHEMA-CHECK pending=0` with `zelda_api.0035`, `matchmaking.0083`, `matchmaking.0095`. `celery` list empty before the upload |
| Worker chain | `process_document_pipeline` (12 chunks, **3 insights**) → `extract_claims_from_insights` (**3**) → `verify_entity_integrity` (report 34) → `verify_document_truth_delta` (report 87) → `generate_intelligence_memo` (**memo 91, saved**, 48.1 s) → `notify_document_processed` ([06](06_worker_chain.txt)) |
| Principals | `ramc_owner` (314, Application 47, not Premium), `ramc_lite` (315), `ramc_paid` (316, `is_premium=True` + active `INVESTOR_PREMIUM` subscription 8), `ramc_staff` (317, staff MFA enrolled), anonymous |
| Profile fixture (key §E) | `company_name="ManyChat"`, `prior_amount_raised=163000000`, `raising_amount=0`, revenue blank, `reporting_currency` blank (the field postdates the key). Canary `CANARY-MANYCHAT-4417` in `reason_for_capital`, PRIVATE |
| Model calls | 1 memo call; 7 `/ask/` calls |

Deviations D-1 to D-5 and D-7 from the [Ben & Jerry's rerun ledger](../../../ben-jerrys/rerun/pass-a/RERUN_LEDGER.md)
apply unchanged (worktree, API upload, migration 0095, staff MFA enrolment, **no browser walks**, stale
`high_priority` list). D-6 here: three profiles are named "ManyChat" (Applications 42, 45, 47).

## State-vocabulary mapping

| Pipeline state | Key state | Note |
|---|---|---|
| Truth Delta `zelda_state=no_data`, `zelda_reason=no_external_evidence` | INSUFFICIENT | All three claims |
| `verification_state=complete` | — | B-1 terminal state |
| Truth Delta score `null`, risk `unknown`, "not scored" | — | Nothing scoreable |
| Entity Integrity `sec_filer` `not_found` | No SEC match (E1) | |
| B-2 `not_comparable` / `profile_currency_unknown` | none | A reconciliation outcome, not a verification state. New since #270 |
| Memo `LITTLE_EVIDENCE` | INSUFFICIENT / self-reported | |

## Before and after

| Layer | Frozen (doc 3129) | Rerun (doc 3133) | Change |
|---|---|---|---|
| Chunks | 12, slides 1–12 | 12, slides 1–12 | None |
| Insights | 1 (slide-2 Funding sentence) | **3**: Traction "140 000+ bots", Traction "500M messages", Funding "$23.1M raised" | Better (#162) |
| Claims | 1: `funding_raised` $23.1M, slide 2 | **3**: 2354 `funding_raised` $23.1M (slide 2, ownership `named`); 2355 `usage` 500M messages (slide 10, `implied`); 2356 `usage` 140,000 bots (slide 10, `implied`) | Better |
| Currency | (field did not exist) | `currency` blank on all three; the bare `$` is unknown currency (#266) | New field, behaves as designed |
| Periods | `time_period` blank | `time_period`, `period_kind`, `period_fiscal_year`, `period_end` all blank on all three | No period kept (see table) |
| Truth Delta | Report 85: 1 claim, `no_data`, score null, risk unknown | Report 87, engine `td.5`: 3 claims, all `no_data` / `no_external_evidence`; score null, risk unknown; `sec=not_found` | Same states, more claims |
| Displayed counts | "1 claim, 0 verified, 1 not established" | **"2 Claims Analyzed … 2 Not established (of 2)"** while 3 claims were checked; the IC memo shows "Claims checked: 3" beside "(of 2)" (RA-104) | New inconsistency |
| B-2 owner | `differs`: $163,000,000 vs $23,100,000 | **`not_comparable` / `profile_currency_unknown`**: "Choose a reporting currency on your profile before comparing these figures." Lite, paid, staff, anonymous `[]` | Changed by #270 (RA-105) |
| Entity Integrity | Report 30, `sec_filer` `not_found` | Report 34, same text | None |
| Memo | Memo 89: "has raised $23.1M in total funding" | Memo 91: "**has raised $23.1M to date**" plus 140,000+ bots and 500M messages | Staleness worse (RA-106) |
| Memo list sections | — | `supported_points`, `open_concerns`, `questions_for_management` stored as Python list repr (`['…', '…']`) and shown raw (RA-107) | New |
| S-7 probe | `140 000+ bots` → 140.0 (latent) | Claim 2356 = **140000.0** | Fixed and exercised |

## Merged-fix checks

| Fix | Observation | Result |
|---|---|---|
| B-1 (#156) | `complete`, a terminal state. With claims present, "No public data could be found to independently verify these claims (checked SEC EDGAR)…" is scoped to the claims | **PASS** |
| B-2 (#157) + #270 | Owner: one row, `prior_amount_raised`, `not_comparable`, `profile_currency_unknown`, 163,000,000 vs [23,100,000], claim 2354; panel "Profile and deck figures to review … Previously raised: Choose a reporting currency…" on the owner's Truth Delta page only. Lite, paid, staff and anonymous: function `[]`; panel text absent from the Lite, paid and staff pages, each HTTP 200 (positive control: the "Truth Delta Verification" heading, checked in the saved paid and staff text); anonymous 302 to login. `raising_amount=0`, no raise guard | **Boundary PASS. Key §E's `differs` is no longer reachable** with this fixture: the profile has no currency, and the deck's bare `$` is unknown currency too, so setting USD on the profile would still give `deck_currency_unknown` |
| A (#158) | No revenue claim, no profile revenue | **Not exercisable** |
| #269 (memo archive) | Memo 91 saved with three list-valued sections | **PASS** |
| A-1 (#155) | No valuation (API 202 owner/staff, 403 investors; UI 404) | Not applicable |

## Period language (for B)

| Claim | category | claimed_value | numeric | unit | currency | time_period | text_excerpt | slide | Period phrase on slide | Kept / dropped / misattached |
|---|---|---|---|---|---|---|---|---|---|---|
| 2354 | `funding_raised` | "$23.1M raised" | 23100000.0 | "" | "" | "" | "$23.1M raised" | 2 | "a **2015** Series A deck with $23.1M raised" | **Dropped**: "2015" and "Series A" cut; no period fields set |
| 2355 | `usage` | "500M messages" | 500000000.0 | messages | "" | "" | "500M messages" | 10 | "Traction **by Apr-16**", axis Jul-15…Apr-16 | **Dropped** |
| 2356 | `usage` | "140 000+ bots" | 140000.0 | bots | "" | "" | "140 000+ bots" | 10 | "Traction **by Apr-16**" | **Dropped** |
| — | — | "500M messages/month" | — | — | — | — | — | 12 | "**/month**", "**this month**" | Not extracted (slide 12 repeats the figures; only slide 10's were taken) |

No phrase was attached to the wrong figure. Every phrase that sits on a claim's slide was dropped.
`claim_periods` (#268) reads the claim's own sentence only, and each excerpt here is just the figure,
so nothing in it names a period. Before/after: frozen had one claim with "2015" dropped; now three
claims, all periods dropped.

## Grades against the key

| ID | Observation | Grade | Vs frozen |
|---|---|---|---|
| M1 $23.1M | Extracted from slide 2 (audit framing, I4), ownership `named` although the sentence attributes the figure to Pitch Deck Hunt. Truth Delta INSUFFICIENT. Memo: "The company states it has raised $23.1M **to date**" | INSUFFICIENT (pass); **STALENESS ERROR** (the pre-2025 total presented as current) | Worse wording (frozen: "has raised … in total funding") |
| M2–M4 platform users | Not extracted; the memo names no platform figure (Messenger appears only in a question about platform dependency) | No ATTRIBUTION ERROR | Same (abstention) |
| M5 140,000+ bots | Extracted as `usage` 140,000, `implied`, INSUFFICIENT; "by Apr-16" dropped; memo "140,000+ bots deployed", undated | INSUFFICIENT, self-reported; **undated** | Better (S-7 fixed; frozen: not extracted) |
| M6 500M vs 500M/month | Only slide 10's "500M messages" extracted; memo "500M messages processed"; I1 not flagged; the two were not merged into one verified figure | INSUFFICIENT; I1 missed | New reach; I1 still missed |
| M7 "launching this month" | Not extracted; not in the memo | Correct abstention | Same |
| M8 active private company | Not extracted | Not extracted (allowed) | Same |
| E1 | `sec_filer` `not_found`; no CIK, Form D, incorporation or address on any surface | No INVENTED IDENTITY | Same |
| E2–E3 | Nothing contradicted; contact details not used as evidence | PASS | Same |
| I1–I3 | Not flagged | Expected observed failure | Same |
| I4 | The funding claim still comes from the audit-framing slide | New-failure class persists | Same |
| Q1–Q7 | Search/RAG 200 for owner; ties; `no_relevant_evidence` false on all seven. Q3 ranks slides 10 and 12 first (tied 0.12). `/ask/` returns marketplace guidance for all seven. No advice word on any probed surface (the only hits are the owner's membership-upsell "recommendations" and "conditions hold" in the memo's scenario text) | Q1–Q6 not exercisable; Q7 PASS | No frozen baseline |

## Authorization matrix (first full matrix for this deck)

| Surface | Owner | Lite | Paid | Staff (after MFA) | Anon |
|---|---|---|---|---|---|
| Home (control) | 200 | 200 | 200 | 200 | 200 |
| Profile `/accounts/profile/ramc_owner/` | 200, canary | 200 | 200 | 200, canary | 302 login |
| Profile analysis | 200 | 302 profile | 302 profile | 302 profile | 302 login |
| Company overview `/matchmaking/memo/manychat/` | **500** | **500** | **500** | **500** | 302 login |
| IC memo / download | 200 / 302 | 404 / 404 | 404 / 404 | 200 / 200 | 302 / 302 |
| Truth Delta page | 200, **B-2 panel** | 200 | 200 | 200 | 302 login |
| Memo API | 200 | 200 `lite_sections` | 200 `lite_sections` | 200 full | 403 |
| Truth Delta API | 200 | 200 | 200 | 200 | 403 |
| Status API | 200 | 403 | 403 | 200 | 403 |
| Valuation API / UI | 202 / 404 | 403 / 404 | 403 / 404 | 202 / 404 | 403 / 302 |
| Identity-check status (report 34) | 200 | 404 | 404 | 200 | 302 |
| Library | 200 | 200 | 200 | 200 | 403 |
| `analyze/founder/ramc_owner` | 403 | 200 | 200 | 403 | 403 |
| Search / RAG (POST) | 200 / 200 | 403 / 403 | 403 / 403 | 200 / 200 | 403 / 403 |

Same shape as the Ben & Jerry's matrix. Canary only in the owner's and staff's profile responses
(raw and script-stripped). Marker false positives checked in context: "Form D" in the staff memo
is "plat**form d**ependency"; "Series B", "currency" and "verified" on the home and profile pages are
site navigation and filter copy. Full rows: [11](11_authorization_matrix.json).

## Ledger

| ID | Layer | Principal | Observation | Key ref | Period phrase | Grade | Bucket | Sev | Blocking |
|---|---|---|---|---|---|---|---|---|---|
| RA-101 | 3–4 | — | Claims 1 → 3 from 3 insights; bots now 140,000 (S-7 fixed). Slide 4 platform figures and slide 12 still not extracted | M1, M5, M6 | see table | Improved | INTEL-QUALITY | P1 (ceiling still low) | No |
| RA-102 | 4 | — | All periods dropped: excerpts are the bare figure, so #268's own-sentence rule finds nothing ("2015", "by Apr-16") | §D | "2015", "by Apr-16" | Dropped | INTEL-QUALITY | P2 | No |
| RA-103 | 4 | — | Claim 2354 comes from slide 2 (audit framing) and is marked ownership `named`, though the sentence attributes it to "Pitch Deck Hunt" | M1, I4 | "2015" | — | INTEL-QUALITY | P2 | No |
| RA-104 | 5, 9 | all report readers | Count mismatch: Truth Delta page "2 Claims Analyzed / 2 Not established", staff profile card "2 not established (of 2)", IC memo "Claims checked: 3 … Not established — 2 (of 2)". Counts come from `category_states()`, so the two `usage` claims collapse into one category | — | — | — | PRODUCT-UI / CORRECTNESS | P2 | No |
| RA-105 | 5 | owner | B-2 now returns `not_comparable` / `profile_currency_unknown` instead of key §E's `differs`. Owner-only boundary holds with controls. With a bare-`$` deck, no profile currency choice can make this pair comparable (`deck_currency_unknown` would follow) | §E, B-2 | — | Boundary PASS; `differs` unreachable | — (owner decision on §E) | — | No |
| RA-106 | 9 | all memo readers | Memo: "The company states it has raised $23.1M **to date**". The key's STALENESS ERROR: a pre-2025 cumulative total presented as current (frozen MC-4, now explicit) | M1 | "2015" dropped | STALENESS ERROR | PHASE1-GROUNDING | P2 | No |
| RA-107 | 9 | staff (IC memo page), memo API full | Three memo sections stored as Python list repr (`['…', '…']`) and shown raw. Ben & Jerry's memo 90 stored its list section as JSON (`["…"]`), so the serialization is inconsistent too | — | — | — | PRODUCT-UI | P2 | No |
| RA-108 | 9 | all memo readers | `zelda_advantage` credits "the verification pass" for finding no confirming evidence (self-credit family, B&J L-008) | — | — | Self-credit | PHASE1-GROUNDING | P3 | No |
| RA-109 | 5–9 | — | I1 (500M cumulative vs 500M/month) not flagged; the memo says "500M messages processed" with no date | M6, I1 | "by Apr-16", "/month" | Missed | INTEL-QUALITY | P2 | No |
| RA-110 | 6 | owner, staff | Entity Integrity `sec_filer` `not_found`; no invented identity anywhere | E1 | — | PASS | — | — | No |
| RA-111 | 10 | all | Authorization: canary owner and staff only; search/RAG 200 only for owner and staff; B-2 panel only for the owner | — | — | PASS | — | — | No |
| RA-112 | 10 | signed-in | Company overview `/matchmaking/memo/manychat/` 500 for every signed-in principal; three profiles share the name (B&J L-012) | — | — | — | CORRECTNESS | P1 | No |
| RA-113 | 6 | paid | The paid investor's Truth Delta page static HTML contains "Verification Not Available — Truth Delta verification hasn't been run yet for this document" beside "Loading verification data…", although report 87 exists. Likely a JS-replaced placeholder; **not confirmed** without a browser (D-5) | — | — | Unconfirmed | PRODUCT-UI | P3 (if real: P2) | No |
| RA-114 | 7–8 | owner | Retrieval ties, `no_relevant_evidence` never true; `/ask/` is marketplace search (B&J L-010/L-011 family) | Q1–Q6 | — | Not exercisable | PHASE1-GROUNDING | P2 | No |
| RA-115 | — | worker | The fixture saves enqueued two `refresh_matches_for_investor_task` runs and no founder refresh task (Ben & Jerry's had one). Recorded only | — | — | — | OPS | P3 | No |

## Summary

Claim extraction reaches more of this deck than in the frozen run: 3 claims instead of 1, the bot
count parsed correctly, and ownership and currency recorded. Truth Delta still states INSUFFICIENT
for all three, which is correct for Pass A. Every period phrase is still dropped. New problems are
in presentation: counts that disagree (3 claims, "of 2"), list sections shown raw, and a memo that
calls a 2016-era funding total current. Under #270, B-2 can no longer produce the key's `differs`
for this deck. The owner needs to decide whether §E's expectation or the fixture should change.

Artifacts: [00](00_setup.json) setup, [01](01_extraction.json)–[09](09_memo.json) pipeline rows
(`04_claims.json` carries each claim's slide text in `_slide_text`), [10](10_retrieval_ask_q1_q7.json),
[11](11_authorization_matrix.json) + [11b](11b_reconciliation_by_principal.json),
[12](12_api_payloads.json), [13](13_rendered_reports_text.json), [16](16_probes.json).
