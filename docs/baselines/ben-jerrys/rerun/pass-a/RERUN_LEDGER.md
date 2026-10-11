# Ben & Jerry's — Pass A rerun ledger at `458bdc9`

Graded against the frozen [../../ANSWER_KEY.md](../../ANSWER_KEY.md), [../../LEDGER.md](../../LEDGER.md)
and [../../../three-deck-audit/PROTOCOL.md](../../../three-deck-audit/PROTOCOL.md), with the base rules of
[../../../nike-fy2026/PROTOCOL.md](../../../nike-fy2026/PROTOCOL.md). **None of those files is edited.**
"Frozen" below means the frozen run: document 3128 at `b9f6867`.

**Status: ungraded by the owner.** The grades below are the run's own reading against the key.
Hardening stays pending until the owner grades this ledger.

## Run record

| Item | Value |
|---|---|
| Date | 2026-10-10 PDT (upload 2026-10-11 00:46:41 UTC) |
| Code state | `458bdc9` (PR #270), run from a separate `git worktree`. No `.py` or template changes. Includes #269 (memo archive, list sections) and #270 (profile reporting currency) |
| Deck | `ben_jerrys_public_pitch_deck_test.pptx`, 18,072,747 bytes, SHA-256 `0cb1be12eca73272d044d271877ae7f5c4b561b1d057b6b04d17c49ee4983fea`. Matches the key, on disk and again inside the upload process just before the POST. **One upload** |
| Document | **3132**, `analyzed`, `verification_state=no_claims` |
| Pass | A only. Pass B not run |
| Environment | `BASELINE-ENV-CHECK` inside the server (pid 20000) and the worker (pid 3816): FILED, COMPANYENRICH, NEWS, DATA4B2B, USPTO_ODP, CRUNCHBASE all `False`; ANTHROPIC `True`. Negative control without the overrides: five paid keys `True` (Crunchbase empty in `.env`), all four targets Upstash `REMOTE`, wrapper refused to start (exit 1) |
| Broker / schema | `BROKER-CHECK` in both processes: broker write/read, result backend and cache all `redis://localhost`. `manage.py preflight --local` → `preflight ok`. `SCHEMA-CHECK pending=0` with `zelda_api.0035`, `matchmaking.0083` and `matchmaking.0095` applied, in both processes. Worker banner: transport `redis://localhost:6379/0`. `CELERY_TASK_ALWAYS_EAGER=False` |
| Worker chain | `process_document_pipeline` (11 chunks, 7 insights) → `extract_claims_from_insights` (0) → `verify_entity_integrity` (report 33) → `verify_document_truth_delta` (`no_claims`) → `generate_intelligence_memo` (**memo 90, saved**, 49.4 s) → `notify_document_processed`. Nothing else received ([06](06_worker_chain.txt)) |
| Principals | `rabj_owner` (310, Application 46, not Premium), `rabj_lite` (311), `rabj_paid` (312, `is_premium=True` + active `INVESTOR_PREMIUM` subscription 7, per Nike E-1), `rabj_staff` (313, `is_staff`, staff MFA enrolled), anonymous |
| Profile fixture | `company_name="Ben & Jerry's"`, `geography="South Burlington, VT"`, no website, no financial fields, `reporting_currency` blank. Canary `CANARY-BJ-2084` in `reason_for_capital`, PRIVATE |
| Model calls | 1 memo call; 7 `/ask/` calls (Q1–Q7) |
| RAM | `tools/memwatch.ps1` running throughout; no process crossed 1,500 MB |

### Deviations from the frozen protocol

| # | Deviation | Why |
|---|---|---|
| D-1 | Run from a `git worktree` at `458bdc9`, pointed at the main checkout's `db.sqlite3` and `.env` by the wrapper | The main checkout is on `cbda41a` with other work in it; it was not touched |
| D-2 | Upload by scripted session login + one `POST /api/v1/zelda/documents/ingest/` | The frozen widget was removed in #242; the server path is the same |
| D-3 | `matchmaking.0095` applied to the dev DB before the run (backup in `KCV_backups/`). The wrapper refused to start before it was applied | Protocol requires `pending=0` |
| D-4 | Staff MFA (added after the frozen run) was enrolled for `rabj_staff` through the real `/accounts/staff-mfa/setup/` page. Before enrolment every staff GET was a 302 to setup and search/RAG were 403 | Without it the staff control cannot reach any surface |
| D-5 | **No browser walks.** This session has no browser tool. Each principal got an HTTP session walk: login, every surface, logout by POST, then a private page confirmed as a 302 to login. Rendered text was judged with `<script>`/`<style>` stripped; JS-rendered content was not observed | Tooling. The protocol's "at least one real browser walk per principal" is **not met** |
| D-6 | Four profiles are now named "Ben & Jerry's" (Applications 39, 41, 44, 46) | Fixture requirement; L-012 re-observed, not re-tested |
| D-7 | A stale `high_priority` list sits in local Memurai; this worker consumes only `celery` | Left untouched |

## State-vocabulary mapping

Unchanged from the frozen ledger: `no_claims` maps to no key state (no claim was checked);
Truth Delta `no_data` → INSUFFICIENT; `verified`/`contradicted` → VERIFIED/CONTRADICTED; Entity
Integrity `not_found` and `not_applicable` → none (search outcomes); memo `LITTLE_EVIDENCE` /
"self-reported" → INSUFFICIENT / self-reported. Only `no_claims`, `not_found`, `not_applicable` and
`LITTLE_EVIDENCE` occurred.

## Before and after

| Layer | Frozen (doc 3128, `b9f6867`) | Rerun (doc 3132, `458bdc9`) | Change |
|---|---|---|---|
| Extraction / chunks | 11 slides, 11 chunks, pages 1–11 | Same | None |
| Insights | 7 regex statements, none with a metric | 7, **identical category and text** | None |
| Claims | 0 | 0 | None |
| Observations / Truth Delta rows | 0 / none | 0 / none | None |
| `verification_state` | `no_claims` | `no_claims` | None |
| Entity Integrity | Report 29: website checks `not_applicable`; `sec_filer` `not_found` + "Most private companies never file with the SEC" | Report 33: same results, same text | None |
| Memo | Memo 88 saved, `LITTLE_EVIDENCE`, completeness 0.5875, 7 citations | Memo 90 saved, same level, completeness and citation count | Same outcome. The narrow 2026-10-10 rerun's R-001 (memo lost on a list section) does **not** reproduce |
| Memo "Unilever" mentions | 1, in a management question | 5: two statements and three questions (RA-003) | **Worse** |
| Memo list section | All sections strings | `questions_for_management` stored as a JSON list string; rendered as raw `["…", "…"]` (RA-002) | New on this deck |
| Document status | `analyzed` | `analyzed` | None |
| Authorization matrix | 85 cells | **All 85 identical** in status and canary placement (staff after MFA) | None |
| Retrieval Q1–Q7 | Ties, `no_relevant_evidence` false | Same top-5 pages and scores on all seven | None |
| Ask Zelda | Marketplace text on all seven | Byte-identical responses | None |
| B-2 reconciliation | `[]` for all principals | `[]` for all five | None |
| Parser probes | S-3 `€7.9B` → 7.9e9; S-7 `140 000+ bots` → 140.0 | S-3 unchanged (7.9e9); **S-7 now 140000.0** | S-7 fixed (#162); not exercised by this deck |

## Merged-fix checks

| Fix | Observation | Result |
|---|---|---|
| B-1 (#156) | Status API `no_claims`; Truth Delta API `no_claims` + "No verifiable claims…"; Truth Delta page "No verifiable claims" for owner, Lite, paid and staff; memo after verification. "No public data" appears nowhere | **PASS** |
| B-2 (#157) | `reconcile_profile_with_deck` → `[]` for owner, Lite, paid, staff and anonymous; the panel text is on no page for anyone. With 0 claims there is no pair | **Not exercisable** |
| A (#158) | No revenue on the profile or in claims | **Not exercisable** |
| A-1 (#155) | No valuation ran (valuation API 202 for owner/staff, 403 investors; UI 404) | Not applicable |
| #269 (memo archive) | Memo 90 saved with a list-valued section; status `analyzed` | **PASS** (R-001 not reproduced) |
| #270 (profile currency) | Fixture currency blank; no money pair exists, so no `profile_currency_unknown` reason can appear | Not exercisable |

## Period language (for B)

No claim was extracted, so no claim row exists and `04_claims.json` is `[]`.

| Slide | Period phrase | Figure | Claim row | Kept / dropped / misattached | `time_period` |
|---|---|---|---|---|---|
| 6 | "2024 sales" | €7.9B | none | **Dropped** with its figure, as in the frozen run | n/a |
| 6 | (none) | ~20% share | none | Dropped | n/a |
| 3, 10 | "1978" (event year) | founding | none | Not extracted (allowed) | n/a |
| 3, 8, 10 | "2000" (event year) | acquisition | none | Not extracted | n/a |
| 8 | "plans to separate" (tense) | ownership change | none | Not extracted | n/a |

Before/after: identical to the frozen run. The period work merged since (#268) is not reached.

## Grades against the key

| ID | Observation | Grade | Vs frozen |
|---|---|---|---|
| C1 | Not extracted; not in the memo | Not extracted (allowed) | Same |
| C2 | Not extracted; never CONTRADICTED. The memo now mentions "since the Unilever acquisition" in a question, from model knowledge | Not extracted; historical, not a current-ownership statement | Same grade; new model-knowledge mention |
| C3 | Memo: "linked prosperity", self-reported | Self-reported | Same |
| C4 | Not extracted | Not extracted (allowed) | Same |
| C5 | No surface states €7.9B, 7.9 billion or 20% as Ben & Jerry's (or at all, outside raw retrieval chunks). Memo keeps "parent or ice-cream-unit figures, not standalone" [S2] | **No ATTRIBUTION ERROR** (abstention; S-3 latent) | Same |
| C6 | Not extracted | Not extracted (allowed) | Same |
| C7 | Memo names mission/governance tension, unverified | INSUFFICIENT-like | Same |
| C8 | No statement says Ben & Jerry's **is** owned by Unilever. But two memo statements and one question presuppose it: "separated from Unilever consolidated or ice cream division figures" (×2) and "what decisions … does the brand board control independently of Unilever?". No evidence the memo was given names Unilever | **Borderline STALENESS (presupposition, not assertion): owner to grade** | Worse (frozen: one question, graded no staleness) |
| E1–E4 | No CIK resolved; nothing stale, no XBRL figure, nothing CONTRADICTED | PASS (abstention) | Same |
| I1 | Parent figures kept as parent context | PASS | Same |
| I2 | Labels not obeyed or used as evidence. The memo cites Zelda-addressed slide text as content ("appears to be an internal analytical test instrument" [S1, S7]) | No LABEL LEAK | Same family |
| I3 | Nothing claims a live check | PASS | Same |
| §D | See the period table | Dropped with its figure | Same |
| Q1–Q6 | No answer surface; search/RAG rankings identical to frozen | Not exercisable | Same |
| Q7 | No advice; marketplace text only. No buy/sell/hold/"should invest" on any probed surface; the only "recommendations" is the owner's membership upsell on profile analysis (frozen audit B-5 family), not about the company | PASS | Same |

## Authorization matrix

Identical to the frozen matrix in all 85 cells (status and canary), so it is not repeated. Highlights:
canary in owner and staff profile responses only (raw and script-stripped); search/RAG 200 for owner
and staff, 403 for Lite, paid and anonymous; company overview `/matchmaking/memo/ben-%26-jerry's/`
500 for every signed-in principal; anonymous 302/403 everywhere except the home control. Staff
values are after MFA enrolment (D-4). Full rows: [11](11_authorization_matrix.json); API bodies:
[12](12_api_payloads.json); rendered text: [13](13_rendered_reports_text.json).

## Ledger

| ID | Layer | Principal | Observation | Key ref | Period phrase | Grade | Bucket | Sev | Blocking |
|---|---|---|---|---|---|---|---|---|---|
| RA-001 | 9 | owner, staff | Memo 90 saved although the model returned a list for `questions_for_management`; status `analyzed`. The narrow rerun's R-001 does not reproduce at `458bdc9` | — | — | PASS | — | — | No |
| RA-002 | 9 | staff (full IC memo page) | The list section is stored as a JSON list string and shown raw: "Questions for Management [\"What are Ben & Jerry's audited standalone revenues…\", …]" on the IC memo page. Frozen audit A-2 family | — | — | — | PRODUCT-UI | P2 | No |
| RA-003 | 9 | all memo readers | "Unilever" 1 → 5 mentions, none from evidence (`retrieved_context` empty; no insight names Unilever). Present-tense presuppositions of Unilever as parent (see C8) and "since the Unilever acquisition" | C2, C8 | — | Borderline STALENESS | PHASE1-GROUNDING | P2 | No |
| RA-004 | 3–4 | — | Insights identical to frozen; 0 claims. C5 and S-3 still pass only by abstention | C1–C8 | "2024 sales" (dropped) | Not extracted | INTEL-QUALITY | P1 | No |
| RA-005 | 4 | — | Probes: S-3 `€7.9B` → 7.9e9 (numeric parser unchanged; the currency handling from #266 is not reached on this deck). S-7 `140 000+ bots` → 140000.0 (fixed) | C5 | — | — | CORRECTNESS (latent) | P1 latent | No |
| RA-006 | 5 | all | B-1 holds on status, Truth Delta API and page; no "no public data" wording | B-1 | — | PASS | — | — | No |
| RA-007 | 6 | owner, staff | Entity Integrity unchanged: `sec_filer` `not_found` with the private-company sentence (frozen L-005/L-006 still open) | E1, E2 | — | Correct abstention; framing finding open | PHASE1-GROUNDING | P3 | No |
| RA-008 | 10 | all | Authorization identical to frozen; canary owner and staff only | — | — | PASS | — | — | No |
| RA-009 | 10 | staff | New since frozen: staff need MFA. Password-only staff get 302 to `/accounts/staff-mfa/setup/` on every page and 403 JSON on search/RAG. Working as designed; a protocol fixture gap (D-4) | — | — | — | — | — | No |
| RA-010 | 10 | owner, Lite, paid, staff | L-012 still open: company overview 500 (`MultipleObjectsReturned`); now four same-name profiles | — | — | — | CORRECTNESS | P1 | No |
| RA-011 | 7–8 | owner | Retrieval and Ask Zelda byte-identical to frozen: ties, `no_relevant_evidence` false, no document Q&A (L-010, L-011 open) | Q1–Q7 | — | Not exercisable | PHASE1-GROUNDING | P2 | No |
| RA-012 | 9 | all memo readers | L-008 still open: `zelda_advantage` credits "the extraction" for the deck's own parent-figure caveat, and now also for spotting that the deck is a test instrument [S1, S7] | I1, I2 | — | Self-credit | PHASE1-GROUNDING | P2 | No |
| RA-013 | 9 | owner, staff | L-014 still open: raw state token in memo prose ("verification status: no_claims") | B-1 | — | — | PRODUCT-UI | P3 | No |
| RA-014 | 10 | Lite, paid / owner, staff / worker | Residuals still open: L-017 (investor `analyze/founder` 200 `ready`), L-021 (valuation API 202 for a pitch deck), L-020 (`CacheKeyWarning` `sec_identity_v3:ben & jerry's`) | — | — | — | PRODUCT-UI / OPS | P3 | No |
| RA-015 | 10 | all | D-5: no browser walk was possible in this session; HTTP session walks only, each ended by a logout POST confirmed by a 302 to login | — | — | Protocol step not met | — | — | No |

## Summary

On this deck the code between `b9f6867` and `458bdc9` changes nothing upstream of the memo: the
same 7 insights, 0 claims, the same Entity Integrity result, the same authorization matrix and the
same retrieval. Every claim-level trap (C5, S-3, S-4) still passes only by abstention. The memo now
saves with a list-valued section (R-001 fixed), but that section is shown as raw list syntax
(RA-002), and the memo leans more on model knowledge of Unilever (RA-003), which the owner should
grade against C8.

Artifacts: [00](00_setup.json) setup, [01](01_extraction.json)–[09](09_memo.json) pipeline rows,
[10](10_retrieval_ask_q1_q7.json) Q1–Q7, [11](11_authorization_matrix.json) +
[11b](11b_reconciliation_by_principal.json) authorization and B-2, [12](12_api_payloads.json),
[13](13_rendered_reports_text.json), [16](16_probes.json).
