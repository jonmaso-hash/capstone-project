# ManyChat — post-fix Pass A ledger at `a975af3`

**A separate, live post-fix run.** It does not replace the frozen narrow run (document 3129), the 458bdc9
rerun (document 3133, memo 91; ledger on branch `docs/two-deck-rerun-458bdc9`,
`docs/baselines/manychat/rerun/pass-a/RERUN_LEDGER.md`) or any earlier evidence folder. **None of those
files, rows or memos was edited.** Graded against the frozen [../../ANSWER_KEY.md](../../ANSWER_KEY.md)
under [../../../three-deck-audit/PROTOCOL.md](../../../three-deck-audit/PROTOCOL.md) and
[../../../nike-fy2026/PROTOCOL.md](../../../nike-fy2026/PROTOCOL.md). The key was read for grading only.
None of its text reached any model input (checked in [09b](09b_model_call.json); see Run record).

**Status: ungraded by the owner. RA-106 stays PENDING until the owner grades this run.** The grades
below are the run's own reading. Zelda hardening is not complete. Nothing was deployed.

## Run record

| Item | Value |
|---|---|
| Date | 2026-10-11 PDT (upload 2026-10-12 03:21:26 UTC) |
| Code state | `a975af307f87d6d488762d091fde518ada028817` (origin/main, Merge PR #278). Contains `d93f2e3` and `d192779` (and `8c5253c`). Detached worktree `KCV-mc-postfix`, no `.py` or template changes |
| Deck | `manychat_series_a_audit_deck.pptx`, 175,622 bytes, SHA-256 `be7a7171bbc84b9895a45adfbc41f2533f3d23b3a4a561c82a8d9de6b94f3ef1`. Matches the key on disk and inside the upload process just before the POST. **One upload** |
| IDs | Document **3136** (`analyzed`, `verification_state=complete`). Chunks 12 (one per slide). Insights 5169, 5170, 5171. Claims **2357** `funding_raised`, **2358** `usage` messages, **2359** `usage` bots. Entity Integrity report **35**. Truth Delta report **88**. Memo **94**. No valuation report |
| Database | An sqlite backup **copy** of the dev DB. Migration `zelda_api.0044` applied to the copy only. Original `db.sqlite3` SHA-256 `5a0b8c1c…7e9a2` identical before and after; it has no document 3136, no `pfmc_` users and no 0044 |
| Broker / cache | Local Memurai, **isolated databases**: broker 8, results 9, cache 10, all empty before the run. Worker `mcpostfix@…`, solo pool, queue `celery` on db 8 only. Redis db 0 (`high_priority` 18, the stale list) and db 2 unchanged |
| Gates | `preflight --local` ok. Before migrating the copy, the run wrapper refused to start (`pending=1 ['zelda_api.0044_claim_source_context']`), proving the gate. Server and worker: `BASELINE-ENV-CHECK` six paid keys `False`, `ANTHROPIC_API_KEY` `True`; `BROKER-CHECK` all four targets `redis://localhost` (db 8/8/9/10); `DB-CHECK is_copy=True is_original=False`; `SCHEMA-CHECK pending=0` with `zelda_api.0035`, `zelda_api.0044`, `matchmaking.0083`, `matchmaking.0095`; `CELERY_TASK_ALWAYS_EAGER=False` ([00](00_setup.json)) |
| Memory | `tools/memwatch.ps1` ran for the whole run; no process crossed 1,500 MB |
| Worker chain | `process_document_pipeline` (12 chunks, 3 insights) → `extract_claims_from_insights` (3) → `verify_entity_integrity` (35) → `verify_document_truth_delta` (88) → `generate_intelligence_memo` (**memo 94**, 49.95 s) → `notify_document_processed` ([06](06_worker_chain.txt)) |
| Model | Memo: one live call, `claude-sonnet-4-6`, `max_tokens` 4000, `stop_reason` `end_turn`, 3,026 input / 2,288 output tokens. Plus seven `/ask/` query-extraction calls from the HTTP probe (server). All eight recorded in-process ([09b](09b_model_call.json), [09c](09c_all_model_calls.json)) |
| Principals | `pfmc_owner` (321, Application **50**, not Premium), `pfmc_lite` (322), `pfmc_paid` (323, `is_premium=True` + active `INVESTOR_PREMIUM` subscription 9), `pfmc_staff` (324, staff MFA enrolled through the real setup page), anonymous |
| Profile fixture (key §E) | `company_name="ManyChat"`, `prior_amount_raised=163000000`, `raising_amount=0`, revenue blank, **`reporting_currency` blank** (as the protocol's run). Canary `CANARY-MANYCHAT-4417` in `reason_for_capital`, PRIVATE. Same-name profiles: 42, 45, 47, 50 |
| Pass | A only. Pass B not run |

### Deviations

- **D-1:** a detached worktree at origin/main, not the main checkout. Same as earlier reruns.
- **D-2:** upload through the session-authenticated ingest API as the owner, not the upload form. Same as earlier reruns.
- **D-3 (new):** the run used a DB **copy** and isolated Redis databases, as instructed. The original dev DB was never opened for writing.
- **D-4 (new):** instrumentation. The run wrapper (scratchpad, [scripts/run_pf.py.txt](scripts/run_pf.py.txt)) wraps `anthropic` `Messages.create` in each process to record request kwargs and the reply. No repo code changed.
- **D-5:** staff MFA was enrolled by the HTTP probe's first staff session. The browser walk then used the real verify page.
- **D-6 (new):** the staff "Download Markdown" walk made Chrome save `~/Downloads/manychat-ic-memo.md` (11,455 bytes, the local memo export). It is left in place and copied here as [browser/staff_markdown_download.md](browser/staff_markdown_download.md).
- **D-7:** the HTTP matrix ran before the browser walks. They used separate sessions.

## Memo input and output (the RA-102 / RA-106 question)

**Input** ([09b](09b_model_call.json); identical to the payload rebuilt from stored rows, [09a](09a_grounded_context_rebuilt.json)):

| Ref | Statement | `as_of` | `narrator` | `source_context` | `dates_not_as_of` |
|---|---|---|---|---|---|
| C1, S3 | `$23.1M raised` | not stated | **Pitch Deck Hunt** | — | **["2015"]** |
| C2, S2 | `500M messages` | not stated | — | **Traction by Apr-16** | — |
| C3, S1 | `140 000+ bots` | not stated | — | **Traction by Apr-16** | — |

- No source sentence reached the model: "Series A deck with" and "SlideShare deck has" are absent.
- No answer-key text reached the model: "Bessemer", "TechCrunch", "2019", "$18M", "STALENESS" and "ATTRIBUTION ERROR" are all absent.
- No canary and no 163M fixture value reached the model.

**Output** (memo 94). The stored sections equal the model's reply, after the list-to-text step, in all 16 sections. **The time-wording guard removed nothing**: the worker logged no removal.

| Check | Result |
|---|---|
| Unsupported current or cumulative wording ("to date", "so far", "currently", "at present", "as of today/now") | **None** in any stored section |
| Funding attribution | Executive summary: "**Pitch Deck Hunt lists $23.1M raised [S3]**, though this figure has not been independently verified." Financial analysis says the same |
| 2015 | Never used as the funding amount's date; it appears nowhere in the memo |
| "Traction by Apr-16" | Kept as context: "As of the slide context dated 'Traction by Apr-16,' the company states it had deployed 140,000+ bots and processed 500M messages [S1, S2]". The scenarios say "as of April 2016" (PF-205) |
| "The company states it has raised" | Absent (memo 91 had "…has raised $23.1M **to date**") |
| Remaining wording to grade | See PF-203 / PF-204 / PF-214 |

## State-vocabulary mapping

| Pipeline state | Key state | Note |
|---|---|---|
| Truth Delta `no_data` / `no_external_evidence` | INSUFFICIENT | All three claims |
| `verification_state=complete` | — | B-1 terminal state |
| Truth Delta score `null`, risk `unknown`, "NOT SCORED · LIMITED PUBLIC EVIDENCE" | — | Nothing scoreable |
| Entity Integrity `sec_filer` `not_found` | No SEC match (E1) | |
| B-2 `not_comparable` / `profile_currency_unknown` | none | Reconciliation outcome |
| Memo `LITTLE_EVIDENCE` | INSUFFICIENT / self-reported | |

## Before (458bdc9, doc 3133) and after (a975af3, doc 3136)

| Layer | 3133 / memo 91 | 3136 / memo 94 | Change |
|---|---|---|---|
| Chunks / insights / claims | 12 / 3 / 3 | 12 / 3 / 3, same figures | None |
| Claim periods | All blank | All blank (`time_period`, `period_kind`, `period_fiscal_year`, `period_end`) | None (as intended) |
| Claim context | (fields did not exist) | 2357: `narrator` **Pitch Deck Hunt**, `source_sentence` "Source: Pitch Deck Hunt lists ManyChat as a 2015 Series A deck with $23.1M raised". 2358, 2359: `source_context` **Traction by Apr-16** | New, as designed |
| Truth Delta | Report 87, `td.5`, 3 × `no_data`, score null | Report 88, `td.5`, 3 × `no_data` / `no_external_evidence`, score null, risk unknown; comparison rows `claim_period_kind` "" | **Unchanged** |
| Displayed counts | "2 Claims Analyzed … (of 2)" vs "Claims checked: 3" (RA-104) | **3 / 0 / 3**, "(of 3)", "none of the 3 claims" on every surface | Fixed (#274/#275) |
| Memo funding sentence | "The company states it has raised $23.1M **to date**" | "**Pitch Deck Hunt lists** $23.1M raised [S3], though this figure has not been independently verified." | Fixed (RA-106 pending grading) |
| Memo traction | "140,000+ bots deployed and 500M messages processed", undated | Dated by the slide context "Traction by Apr-16" | Better |
| Memo list sections | Python list repr shown raw (RA-107) | `- ` lines; rendered as HTML lists and Markdown items | Fixed (#276) |
| Company overview | 500 for all signed-in (RA-112) | `/matchmaking/memo/profile/50/`: 200 for Lite, paid, staff; owner 403 (investors/staff only, by design); legacy `/matchmaking/memo/manychat/` 404 (4 same-name profiles) | Fixed (#273) |
| B-2 owner | `not_comparable` / `profile_currency_unknown` | Same, claim 2357, 163,000,000 vs [23,100,000] | Unchanged (RA-105) |
| Entity Integrity | Report 34, `sec_filer` `not_found` | Report 35, same | None |

## Period language (for B)

| Claim | category | claimed_value | numeric | unit | time_period | narrator | source_context | slide | Period phrase on slide | Kept / dropped / misattached |
|---|---|---|---|---|---|---|---|---|---|---|
| 2357 | `funding_raised` | "$23.1M raised" | 23100000.0 | "" | "" | Pitch Deck Hunt | "" | 2 | "a **2015** Series A deck with $23.1M raised" | **Kept as context**: sentence stored; 2015 given to the memo as `dates_not_as_of`; not a period (as intended) |
| 2358 | `usage` | "500M messages" | 500000000.0 | messages | "" | "" | Traction by Apr-16 | 10 | "Traction **by Apr-16**" | **Kept as context**, not a period |
| 2359 | `usage` | "140 000+ bots" | 140000.0 | bots | "" | "" | Traction by Apr-16 | 10 | "Traction **by Apr-16**" | **Kept as context**, not a period |
| — | — | "500M messages/month" | — | — | — | — | — | 12 | "/month", "this month" | Not extracted (slide 12) |

No phrase was attached to the wrong figure. The chart's axis months were not attached.

## Grades against the key (run's reading; owner grading pending)

| ID | Observation | Grade | Vs 3133 |
|---|---|---|---|
| M1 $23.1M | INSUFFICIENT. Memo attributes it to Pitch Deck Hunt, unverified, undated, never current. The Lite sections call it "self-reported" (PF-203); `base_scenario` says "stated funding of $23.1M" (PF-204) | INSUFFICIENT (pass). **No STALENESS ERROR found** | Fixed (RA-106, pending grading) |
| M2–M4 platform users | Not extracted; memo names no platform user count | No ATTRIBUTION ERROR | Same |
| M5 140,000+ bots | INSUFFICIENT, self-reported, dated by "Traction by Apr-16" | INSUFFICIENT, **dated** | Better |
| M6 / I1 | Only slide 10's "500M messages"; conflict with slide 12's "/month" not flagged | INSUFFICIENT; I1 missed | Same (RA-109) |
| M7 | Not extracted; not in the memo | Correct abstention | Same |
| M8 | Not extracted | Allowed | Same |
| E1–E3 | `sec_filer` `not_found`; no CIK, Form D, incorporation or address anywhere | PASS | Same |
| I2–I4 | Not flagged; funding claim still from the audit-framing slide | Expected failure | Same (RA-103) |
| Q1–Q7 | Search/RAG 200 for owner (and staff), ties, `no_relevant_evidence` false on all seven; Q3 ranks slides 10 and 12 first. `/ask/` returns "I couldn't find specific search criteria…" for all seven (marketplace parser). No advice wording | Q1–Q6 not exercisable; Q7 PASS | Same (RA-114) |

## Authorization and privacy (HTTP matrix [11](11_authorization_matrix.json) + Chrome walks [15](15_browser_walks.json))

| Surface | Owner | Lite | Paid | Staff (after MFA) | Anon |
|---|---|---|---|---|---|
| Home (control) | 200 | 200 | 200 | 200 | 200 |
| Profile `/accounts/profile/pfmc_owner/` | 200, canary | 200 | 200 | 200, canary | 302 login |
| Company overview `/matchmaking/memo/profile/50/` | 403 (by design) | 200 Lite report | 200 Lite report | 200 Full report | 302 login |
| Legacy `/matchmaking/memo/manychat/` | 404 | 404 | 404 | 404 | 302 login |
| IC memo / Markdown | 200 Lite memo / 302 → IC memo | 404 / 404 | 404 / 404 | 200 Full / 200 attachment | 302 / 302 |
| Truth Delta page | 200, **B-2 panel** | 200 | 200 | 200 | 302 login |
| Memo API | 200 | 200 `lite_sections` | 200 `lite_sections` | 200 full | 403 |
| Truth Delta API | 200 | 200 | 200 | 200 | 403 |
| Status API | 200 | 403 | 403 | 200 | 403 |
| Valuation API / UI | 202 / 404 | 403 / 404 | 403 / 404 | 202 / 404 | 403 / 302 |
| Identity-check status (35) | 200 | 404 | 404 | 200 | 302 |
| Search / RAG (POST) | 200 / 200 | 403 / 403 | 403 / 403 | 200 / 200 | 403 / 403 |

- **Canary:** only in the owner's and staff's profile responses (raw and script-stripped). It was absent from every memo, overview, API payload and Markdown file, and from the model input.
- **B-2 panel:** owner only, on the Truth Delta page, confirmed in Chrome. Lite, paid and staff pages have no panel; each loaded with its positive control.
- **Reconciliation function:** owner `not_comparable`; Lite, paid, staff and anonymous `[]`.
- **Counts:** every surface says 3 claims, 0 verified, 3 not established ("(of 3)").
- **Lists:** HTML `<ul>` lists (questions: 10 items) and Markdown `- ` items. No `['` or `["` anywhere.

## Ledger

| ID | Layer | Principal | Observation | Key ref | Period phrase | Grade | Bucket | Sev | Blocking |
|---|---|---|---|---|---|---|---|---|---|
| PF-201 | 4 | — | RA-102 context fix works on a live run. Claim 2357 stores narrator Pitch Deck Hunt and its sentence. 2358/2359 store "Traction by Apr-16". All structured periods stay blank; Truth Delta 88 is unchanged in states, score and comparison periods | M1, M5, §D | "2015", "by Apr-16" | Kept as context | INTEL-QUALITY | — | No |
| PF-202 | 9 | all memo readers | **RA-106:** memo 94 has no "to date" or other current or cumulative wording; funding is attributed to Pitch Deck Hunt; 2015 is not used as its date. The model complied; the guard had nothing to remove | M1 | "2015" | No STALENESS ERROR found (**owner grading pending**) | PHASE1-GROUNDING | — | No |
| PF-203 | 9 | owner, Lite, paid (Lite views) | `information_readiness`: "Funding raised figure (**self-reported**, unverified): $23.1M [S3]". The figure is a third party's listing, but the Lite memo, Lite memo API and the owner's IC memo show this line without the narrator. The full memo names Pitch Deck Hunt | M1, RA-103 | — | Attribution softened | INTEL-QUALITY | P3 | No |
| PF-204 | 9 | full-memo readers | `base_scenario`: "…meaningful early platform traction as of April 2016 [S1, S2] and **stated funding of $23.1M** [S3]". The narrator is not named, though the figure is not presented as current | M1 | — | Minor | INTEL-QUALITY | P3 | No |
| PF-205 | 9 | full-memo readers | The scenarios turn the heading "Traction by Apr-16" into "**as of April 2016**". This dates the figures as historical, matching the deck's "by Apr-16"; no structured period is set. For the owner to grade against the "context only" decision | M5, M6 | "by Apr-16" | For owner | — | — | No |
| PF-206 | 9 | owner vs staff | The same memo shows **Section Coverage 31.2%** in the owner's Lite IC memo and **100.0%** in the full IC memo and Markdown, while the page defines it as "how much of this memo Zelda could generate" | — | — | — | PRODUCT-UI | P3 | No |
| PF-207 | 5, 9 | all report readers | RA-104 resolved on live data: 3 / 0 / 3 and "(of 3)" on the Truth Delta page (owner, Lite, paid, staff), IC memo, Markdown and overview | — | — | PASS | — | — | No |
| PF-208 | 9 | all | RA-107 resolved on live data: list sections stored as `- ` lines, rendered as HTML lists and Markdown items; no list repr anywhere | — | — | PASS | — | — | No |
| PF-209 | 10 | signed-in | RA-112 resolved: overview by id 200 for Lite, paid, staff. Legacy slug 404 with four same-name profiles. Owner 403 is the existing investor-or-staff rule | — | — | PASS (owner 403 by design) | — | — | No |
| PF-210 | 6 | paid | RA-113 not reproduced: the paid investor's rendered Truth Delta page shows 3 / 0 / 3, with no "Verification Not Available" or "Loading" text | — | — | Not reproduced | — | — | No |
| PF-211 | 5–9 | — | RA-109 / I1 still missed: slide 12's "500M messages/month" not extracted; no conflict flagged | M6, I1 | "/month" | Missed | INTEL-QUALITY | P2 | No |
| PF-212 | 4 | — | RA-103 persists: claim 2357 comes from slide 2 (audit framing, I4) with ownership `named`; the narrator is now recorded beside it | M1, I4 | — | — | INTEL-QUALITY | P2 | No |
| PF-213 | 9 | all memo readers | RA-108 persists: `zelda_advantage` credits "the verification pass" and the "structured verification" for finding nothing | — | — | Self-credit | PHASE1-GROUNDING | P3 | No |
| PF-214 | 9 | full-memo readers | Questions for management assume a live raise: "what runway does **the stated raise** provide", "use of proceeds from **this raise**". The fixture has `raising_amount=0`, and $23.1M is a historical listing. These are questions, so the guard keeps them (as designed) | M1 | — | Minor framing | INTEL-QUALITY | P3 | No |
| PF-215 | 6 | owner | RA-105 unchanged: B-2 `not_comparable` / `profile_currency_unknown`; key §E's `differs` stays unreachable with a blank profile currency and a bare `$` deck | §E | — | Boundary PASS | — (owner decision) | — | No |
| PF-216 | 7–8 | owner | RA-114 unchanged: retrieval ties, `no_relevant_evidence` never true; `/ask/` is marketplace query extraction (7 model calls) | Q1–Q6 | — | Not exercisable | PHASE1-GROUNDING | P2 | No |
| PF-217 | 10 | all | Privacy: canary only to owner and staff profile; B-2 owner only; search/RAG owner and staff only; anonymous refused everywhere; no canary or fixture money value in the model input | — | — | PASS | — | — | No |
| PF-218 | — | worker | The fixture saves enqueued two `refresh_matches_for_investor_task` runs (as RA-115); both succeeded on the isolated broker | — | — | — | OPS | P3 | No |

No defect was repaired during the run.

## Summary

Live, the RA-102 / RA-106 fix behaves as intended:
- The claims keep Pitch Deck Hunt, the 2015 deck year and "Traction by Apr-16" as context, with no structured period and an unchanged Truth Delta.
- The model was told `as_of: not stated` and wrote "Pitch Deck Hunt lists $23.1M raised … not independently verified", with no "to date" or other current wording.
- The guard never had to act.

RA-104, RA-107 and RA-112 are resolved on this live data, and RA-113 did not reproduce in the browser. Still open:
- RA-109 (I1), RA-103, RA-108 and RA-114;
- small attribution and framing slips (PF-203, PF-204, PF-214);
- Section Coverage depending on tier (PF-206);
- the "as of April 2016" wording for the owner to grade (PF-205).

**RA-106 stays pending until the owner grades this run.** Frozen memo 91 was not regenerated.

## Artifacts

- [00](00_setup.json): setup, gates, fixtures, upload and isolation checks.
- [01](01_extraction.json)–[09](09_memo.json): pipeline rows. [04](04_claims.json) carries `source_sentence`, `narrator`, `source_context` and `_slide_text`.
- Memo input: [09a](09a_grounded_context_rebuilt.json) and [09b](09b_model_call.json). All model calls: [09c](09c_all_model_calls.json).
- HTTP matrix and payloads: [10](10_retrieval_ask_q1_q7.json), [11](11_authorization_matrix.json), [11b](11b_reconciliation_by_principal.json), [12](12_api_payloads.json), [13](13_rendered_reports_text.json).
- Chrome: [15](15_browser_walks.json) and [browser/](browser/), which holds 3 screenshots and the Markdown export.
- Probes: [16](16_probes.json).
- [process/](process/): server and worker logs. [scripts/](scripts/): the run's scratchpad scripts.
