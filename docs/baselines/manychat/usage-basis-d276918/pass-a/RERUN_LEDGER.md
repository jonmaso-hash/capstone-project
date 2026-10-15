# ManyChat — usage-basis (RA-109) Pass A ledger at `d276918`

**A new, separate live run after PR #283.** It edits or replaces no earlier record:
- earlier runs: documents 3129, 3133, 3136, 3137, 3138; memos 91, 94, 95, 96;
- the memo-97 run (document 3139) and its grading (`narrator-provenance-b9cddec/pass-a/`, including `OWNER_GRADING.md`);
- the RA-109 code-review evidence (`three-deck-audit/usage-basis-*`);
- the frozen answer key and protocols, unchanged ([00](00_setup.json) `frozen_artifacts`).

Graded against the frozen [../../ANSWER_KEY.md](../../ANSWER_KEY.md) under [../../../three-deck-audit/PROTOCOL.md](../../../three-deck-audit/PROTOCOL.md) and [../../../nike-fy2026/PROTOCOL.md](../../../nike-fy2026/PROTOCOL.md). The key was used for grading only; none of its text, nor any fixture or expected-note text, reached the model ([09d](09d_memo_input_output_check.json)).

**Status: ungraded.** These are the run's own readings.
- **RA-109:** live acceptance stays **pending** until independent grading.
- **RA-106:** its scoped acceptance (memo-97 grading) is unchanged.
- **Still open:** RA-108 and overall Zelda hardening.
- **Not done:** nothing was deployed, paid-source Pass B was not run, and no application code was changed.

## Key interpretation carried forward (additive; the key is not edited)

- **M6 / I1 (messages basis):** the key describes slide 10's 500M messages as cumulative "by context" and the pair as a conflict. The accepted implementation records only what each bounded text states:
  - slide 10 states **500M messages with no explicit interval**;
  - slide 12 states **500M messages/month**.
  The expected behaviour is to keep both, detect the different measurement bases, and ask for clarification. It must not label slide 10 cumulative without support, annualise, or declare a contradiction because the numbers match.
- **Currency erratum (unchanged):** a blank reporting currency gives owner reconciliation `not_comparable / profile_currency_unknown`, not the key's `differs`.

**State mapping (unchanged):** `no_data` → INSUFFICIENT; `verified` → VERIFIED; `contradicted` → CONTRADICTED. The basis note is not a state.

## Run record

| Item | Value |
|---|---|
| Date | 2026-10-15 local. Upload 08:22:39 UTC |
| Code | `d276918cb0e1a4e7fa109a86c5e9336ef180f9a3`, "Merge pull request #283 …". Parents: fbb9161 and the final PR head 3525d3b. origin/main was exactly d276918 when fetched (no mismatch). 0 non-`docs/` files differ from the reviewed 9b3d264. No migrations since b9cddec. Worktree `KCV-mc-ub`, branch `docs/manychat-usage-basis-d276918`. Server and worker print `non_pyc_files_differing_from_d276918=0` |
| Deck | `manychat_series_a_audit_deck.pptx`, 175,622 bytes, SHA-256 `be7a7171…3ef1`, matching the key. **One upload** |
| IDs (all new) | **Document 3140** (`analyzed`, `complete`)<br>Chunks: 12<br>Insights: 5181 `140 000+ bots`, 5182 `500M messages`, 5183 `500M messages/month` (all Traction), 5184 `$23.1M raised` (Funding)<br>**Claims 2369–2372**<br>Entity Integrity **39**; Truth Delta **92**; **memo 98** |
| Database | A new SQLite backup copy, `scratchpad/ub/db_ub_copy.sqlite3`, made with the backup API from the original opened `mode=ro`; `integrity_check` ok. `zelda_api.0044` was applied to the copy only, after the gate refused `pending=1`.<br>The run wrapper refuses the original and every earlier run copy, including memo 97's. The ID sequences were advanced in the copy only, to the memo-97 copy's maxima (read `mode=ro`) |
| Broker / cache | Local Memurai db **9** (broker), **12** (results), **15** (cache). Empty and without clients before the fixtures. Worker `mcub@inventoroftues`, queue `celery`, solo, concurrency 1. Every other Redis db is unchanged |
| Gates (from inside both processes) | Server pid 6424 and worker pid 10312 each report:<br>• six paid keys `False`: `FILED_API_KEY`, `COMPANYENRICH_API_KEY`, `NEWS_API_KEY`, `DATA4B2B_API_KEY`, `USPTO_ODP_API_KEY` (read by no code here; blanked anyway), `CRUNCHBASE_API_KEY`;<br>• `ANTHROPIC_API_KEY` `True`;<br>• broker local on db 9/9/12/15;<br>• `DB-CHECK is_copy=True is_original=False is_historical_copy=False`;<br>• `SCHEMA-CHECK pending=0`, heads zelda_api 0044, matchmaking 0095, accounts 0017, billing 0007;<br>• `CELERY_TASK_ALWAYS_EAGER=False`.<br>`preflight --local`: ok |
| Memory | `tools/memwatch.ps1` (1,500 MB threshold) ran throughout; nothing crossed it. Free RAM was low (0.6–1.1 GB), so every step ran serially. No tests or mutations ran alongside the live run |
| Task order ([06](06_worker_chain.txt)) | 1. 3 fixture match refreshes.<br>2. `process_document_pipeline` (12 chunks, 4 insights).<br>3. `extract_claims_from_insights` (**4**).<br>4. `verify_entity_integrity` (39).<br>5. `verify_document_truth_delta` (92).<br>6. `generate_intelligence_memo` (**98**, 52.1 s).<br>7. `notify_document_processed` |
| Model calls | **8 in all:**<br>• **1 memo call** (worker): `claude-sonnet-4-6`, `max_tokens` 4000, `end_turn`, 3,771 in / 2,372 out tokens;<br>• **7 `/ask/` query-extraction calls** (server) from the Q1–Q7 probe.<br>No retry and no second generation ([09b](09b_model_call.json), [09c](09c_all_model_calls.json)) |
| Principals | `ubmc_owner` (321, Application 50); `ubmc_lite` (322); `ubmc_paid` (323, Premium plus an active local `INVESTOR_PREMIUM` subscription 9 with fake Stripe IDs); `ubmc_staff` (324, real staff-MFA setup and verify); anonymous |
| Profile fixture | ManyChat; `prior_amount_raised=163000000`, `raising_amount=0`, revenue blank, reporting currency blank. Canary `CANARY-MANYCHAT-4417` in PRIVATE `reason_for_capital` |
| Preserved | Read-only snapshots of memos 90/91 (with documents 3132/3133), 94, 95, 96 and **97** (with document 3139, from the memo-97 run copy) are **byte-identical** before and after. The source DB hashes are unchanged. The memo-97 copy (`28126505…`) was not used as a run DB.<br>The original/94/95/96 before-snapshots equal the committed ea3ab13 after-snapshots once **carriage returns and lines starting with `Invalid line`** (a startup `.env` warning present in this run's files, absent from ea3ab13's) are removed.<br>Memo 97's 24 stored fields equal its committed `09_memo.json` (ea3ab13), before and after |

### Deviations

- **D-1: ingest API upload.** Upload used the session-authenticated ingest API, as before; the only UI intake leads to Stripe checkout or credit redemption.
- **D-2: repeated ID numbers.** User IDs 321–324 and Application 50 repeat earlier runs' numbers, as separate rows in a separate DB.
- **D-3: instrumentation.** In-process recording of `Messages.create`; no repo change and no credentials.
- **D-4: Chrome mechanics.** As before: form fields set, then `requestSubmit()`. The staff TOTP was computed for the next 30-second window and submitted once it began. The Lite/paid IC memo 404s and the staff Markdown were read by in-page fetch, and long page text is truncated by the extension ([15](15_browser_walks.json)).
- **D-5: process stop.** Server and worker were stopped by exact PID.
- **D-6: probe marker.** The probe's "Form D" marker (false positive on "platform dependency") was dropped from the marker list; markers were added for this run.

## Primary RA-109 checks

### Extraction and claims ([02](02_chunks.json)–[04](04_claims.json))

| Source | Claim | Value | Unit | Ownership / narrator | Period fields | Context |
|---|---|---|---|---|---|---|
| p2 | `$23.1M raised` (2369) | 23,100,000 | (none), currency blank | named / **Pitch Deck Hunt** | none | — |
| p10 | `140 000+ bots` (2372) | 140,000 | `bots` | implied / none | none | `Traction by Apr-16` |
| p10 | `500M messages` (2371) | 500,000,000 | `messages` | implied / none | **none** (not labelled cumulative) | `Traction by Apr-16` |
| p12 | `500M messages/month` (2370), from adjacent lines `500M` + `messages/month` | 500,000,000 | **`messages/month`** | implied / none | `period_kind` monthly, `time_period` `/month`, **no `period_end`, no fiscal year** | none |

**PASS:**
- **Count:** four claims, as the deterministic fixtures predicted.
- **Bots dedup:** slide 12's repeated `140 000+ bots` deduped.
- **The two 500M figures:** the equal-valued count and rate stayed separate.
- **Slide 4:** no claim (no platform user counts).
- **Monthly rate:** no as-of date.
- **Slide context:** stays context.
- **Chunk hashes:** p10 `4981cd72…`, p12 `a6ff6361…`, p2 `c80948f9…`.

### Payload and note ([09a](09a_grounded_context_rebuilt.json), [09b](09b_model_call.json), [09d](09d_memo_input_output_check.json))

- **Request = rebuild:** the request equals the dump's rebuilt payload and a fresh `GroundedContext.build` for the generation principal (owner 321, `ORIGIN_TASK`).
- **Ref mapping (this run):**

| Ref | Item |
|---|---|
| C1 | funding, Pitch Deck Hunt, `dates_not_as_of ["2015"]` |
| C2 | `500M messages/month`, p12 |
| C3 | `500M messages`, p10, context `Traction by Apr-16` |
| C4 | `140 000+ bots`, p10 |
| S1 | bots |
| S2 | `500M messages` |
| S3 | `500M messages/month` |
| S4 | funding, Pitch Deck Hunt |
| P1, P2 | profile stage and sector |

- **`consistency_notes`**, identical in the request and the rebuild:

  ```json
  [{"kind": "measurement_basis", "refs": ["C3", "C2"],
    "note": "Page 10 states 500M messages without an explicit interval; page 12 states 500M messages/month. These use different measurement bases and need clarification before comparison."}]
  ```

- **Prompt:** rule 11 is present, and the user prompt points to it. `time_wording_allowed` is empty for every dated item.
- **Absent from the input:** the canary; 163,000,000; Bessemer, TechCrunch and Summit Partners; 2019, $18M and $140M; the founders; the key's labels and "cumulative by context"; the fixture file name; the fixture owner/description. Pitch Deck Hunt is the narrator of C1/S4 only.

### Memo 98: the model's reply vs. the stored memo

**Replay.** All 17 stored fields equal the pipeline replay of the raw reply (list normalisation, then the time guard with the recorded `time_wording_allowed`, then the funding guard). Every field is also order-stable on the reversed context, idempotent on a second pass, and keeps its citations in order.
- **Time guard:** removed nothing.
- **Funding guard:** 2 edits, both `attribution:Pitch Deck Hunt`, in `open_concerns` and `questions_for_management` ([09e](09e_guard_changes.txt)). The narrator-provenance rule did not fire.

**The model itself identified the basis mismatch, and the stored memo preserves it** (no guard was involved):

| Section | Text (stored = raw reply) |
|---|---|
| `risk_assessment` 1 | "the deck's page 10 ('Traction by Apr-16') states 500M messages without an explicit interval [C3, S2], while page 12 states 500M messages/month [C2, S3]. These use different measurement bases and cannot be compared or reconciled without clarification from management. **If the cumulative figure is being presented as a monthly figure, the key traction claim is materially overstated.**" |
| `information_readiness` | "A second messages figure (500M messages/month) on a separate page [S3]"; Needs Validation: "Measurement basis of messages metric: cumulative vs. monthly [C2, C3]" |
| `open_concerns` | "stated with two different measurement bases … without an interval on page 10 … and as a monthly figure on page 12 [C2, S3]. This **inconsistency** has not been reconciled and must be clarified …" |
| `upside_scenario` / `downside_scenario` | Conditional both ways ("If … represents a monthly run rate [S3] rather than a cumulative total"; "If … is a cumulative total rather than monthly [C3 vs. C2]") |
| `zelda_advantage` | "The **verification process** specifically identified that the 500M messages figure appears twice … with different measurement bases … a consistency issue that a plain AI summary would likely report as a single confirmed data point …" |
| `questions_for_management` 1 | "Is the 500M messages figure a cumulative total or a monthly run rate, and which page of the deck reflects the correct measurement basis [C2, C3, S2, S3]?" |
| `executive_summary` | Mentions only "140,000+ bots deployed and 500M messages processed … [S1, S2]"; no basis |

**Reading against the RA-109 requirements:**
- **Kept separate:** the two figures are never merged and never called verified; there is no annualisation or conversion (scan: 0).
- **Clarification:** it is asked for, with the correct pages and refs, and historical context is kept.
- **Unsupported labels:** in `risk_assessment` 1 the model calls page 10 "**the cumulative figure**" and adds "materially overstated". Elsewhere the cumulative reading is conditional or a question. `open_concerns` uses "inconsistency".
- **Note credited to verification:** `zelda_advantage` credits the "verification process" for a finding that came from the normalised note; the note is not a verification result. This is RA-108's self-comparison again.

### Reader surfaces

| Surface | Basis distinction visible? |
|---|---|
| Truth Delta page: owner, Lite, paid, staff (staff by direct navigation after login and MFA) | **Yes.** A "Measurement basis to clarify" block with the exact note and "This is not a verification result and doesn't affect the score." Counts 4/0/4; score N/A, "NOT SCORED · LIMITED PUBLIC EVIDENCE"; no contradiction wording. Anonymous: redirected |
| IC memo: owner (Lite) | Yes, in `information_readiness` and `open_concerns` |
| IC memo: staff (full), Markdown | Yes, in 8 sentences (Chrome) and 8 Markdown lines |
| Memo API: Lite and paid (`lite_sections`) and staff | Yes (probe markers `messages/month`, `measurement bases`, `cumulative`, `monthly`) |
| Company overview: staff (full) | Yes |
| **Company overview: Lite and paid** (Lite report: executive summary only) | **No.** Its only 500M sentence is "500M messages processed … [S1, S2]"; the monthly figure and the basis question are absent from that surface |

### Truth Delta ([07](07_truth_delta_reports.json), [05](05_observations.json))

- 0 observations; all four claims INSUFFICIENT (`no_data`); 0 verified, 0 contradicted.
- `overall_truth_score` is None ("N/A").
- The note manufactured no state and did not change the score. No external data appeared.

## Regression checks

| Check | Result |
|---|---|
| Funding narrated by Pitch Deck Hunt | **PASS on amounts.** All 39 sentences stating $23.1M across 51 surfaces name Pitch Deck Hunt (Chrome: owner 3/3, Lite/paid overview 1/1, staff 7/7). Undated ("no date is stated"). No current total, live raise or cash. Bots/messages carry no narrator. Notes NP-603 and NP-604 below |
| Counts, lists, citations | **PASS.** "(of 4)", "none of the 4 claims", 4/0/4. Lists render in HTML (owner 2/4; staff 2/4/9/5) and Markdown. Citations unchanged by the guard edits |
| Markdown | **PASS.** `text/markdown; charset=utf-8`; 11,774 bytes; 18 `•` and 20 `—` intact; the reader's text equals strict UTF-8; no mojibake ([14](14_markdown_utf8.json)) |
| Q1–Q7 ([10](10_retrieval_ask_q1_q7.json)) | As before: owner search/RAG 200 with near-uniform relevance; Q3's top pages are 10 and 12; `/ask/` returns the marketplace query-extraction message for all seven (**RA-114 unchanged**) |
| Authorization ([11](11_authorization_matrix.json)) | **All 90 principal × surface rows identical to the memo-97 run** (status, owner panel, canary, redirect). The new note follows the existing Truth Delta page entitlement; there is no new route |
| Reconciliation | Owner-only (staff `[]`): `not_comparable / profile_currency_unknown` |
| Canary | Only on the owner's and staff's profile; never in the model input, memo or report outputs |

## Ledger

| ID | Layer | Principal | Observation | Key ref | Grade | Bucket | Sev | Blocking |
|---|---|---|---|---|---|---|---|---|
| UB-601 | 3–5 | all | Four claims; p12 `500M messages/month` recovered from adjacent lines as its own claim (`messages/month`, implied, no as-of date); p10 `500M messages` kept with no interval; bots deduped; no platform counts | M5, M6, M2–M4 | PASS | — | — | No |
| UB-602 | 9 | model input | `consistency_notes` has the measurement-basis note citing the real refs C3/C2. Request = rebuild; rule 11 present; no key, fixture or canary text | M6 / I1 | PASS | — | — | No |
| UB-603 | 9 | all memo readers | The model raised the basis mismatch itself in 7 sections and the stored memo preserves it (no guard involved). Both figures stay distinct, are never merged or verified, and are never annualised; clarification is asked for with correct refs | M6 / I1 | **PASS on detection and preservation** (for grader) | — | — | No |
| UB-604 | 9 | staff (full) | `risk_assessment` 1 calls page 10 "the cumulative figure" and says "materially overstated", an unsupported cumulative label. Other sections keep it conditional. `open_concerns` calls it an "inconsistency" (not a contradiction) | M6 | Wording defect; for grader | INTEL-QUALITY | P2 (provisional) / P3 | No |
| UB-605 | 9 | staff | `zelda_advantage` credits the "verification process" for the basis finding (it came from the normalised note) and repeats the plain-AI comparison | — | RA-108 recurrence; note mislabelled as verification | INTEL-QUALITY | P3 | No |
| UB-606 | 10 | Lite, paid | The Lite company overview shows only the executive summary's bare "500M messages processed … [S1, S2]". The basis distinction is not on that surface (it is on their Truth Delta page and in the Lite memo sections of the memo API) | M6 | Observation (surface coverage) | PRODUCT-UI | P3 | No |
| UB-607 | 9 | all | `executive_summary` / `supported_points` say bots "deployed" and messages "processed"; the deck says neither | M5, M6 | Wording | INTEL-QUALITY | P3 | No |
| NP-603 | 9 | staff | `supported_points`: "Pitch Deck Hunt lists $23.1M as the **total amount raised** [S4] … it establishes the fundraising narrative **the company has put forward**". "Total" reads as a cumulative amount, and the narrative is credited to the company although only Pitch Deck Hunt narrates it | M1 | Provenance/total wording; for grader | PHASE1-GROUNDING | P2 (provisional) | No |
| NP-604 | 9 | Lite (`open_concerns`), staff | "how the $23.1M (per Pitch Deck Hunt) narrated as raised [S4] has been **deployed**"; risk 4 "how much of it may have been **consumed**"; "how long the company can operate on the capital narrated as raised [S4]" (`what_would_change_the_picture`). These presuppose received and available funds (the NP-508 / FF-303 shape). The guard's insertion makes "(per Pitch Deck Hunt) narrated as raised" redundant | M1 | Carried-forward shape; for grader | INTEL-QUALITY | P3 | No |
| UB-608 | 9 | staff | A question names "Facebook Messenger" as an example platform; no grounded item mentions it (the deck's slides 11–12 do, but they are not in the evidence items) | — | Possible outside knowledge in a question | PHASE1-GROUNDING | P3 | No |
| UB-609 | 10 | all | Truth Delta: 0 observations, 4 INSUFFICIENT, score N/A. The note manufactured no state and did not change the score | — | PASS | — | — | No |
| UB-610 | 9–10 | all | Funding attribution on every amount sentence, counts/lists/citations, UTF-8 Markdown and the authorization matrix all hold | M1 | PASS | — | — | No |
| UB-611 | — | — | Unchanged and **not closed by this run**: RA-108 (UB-605), RA-103 (funding claim from the audit-framing slide 2), FF-413 (unstyled Truth Delta page), RA-114 (`/ask/`), RA-105 (currency), PF-206/FF-311 (Section Coverage 31.2% vs 100%), NP-508/509, P3 basis-note rounding | — | Open | — | — | No |

No defect was repaired during the run, and no isolation or data-integrity problem occurred.

## Summary

At merged `d276918`, one live generation (memo 98):
- **Extraction:** the frozen deck produces the four expected claims. Slide 12's monthly rate is a separate, correctly sourced claim, and slide 10's count stays uncategorised by interval.
- **Model input:** the neutral measurement-basis note reaches the model with the real refs.
- **Memo:** the model raised the clarification itself across the memo, and the stored memo preserves it.
- **Truth Delta:** the page shows the note to every principal who may see the page, without any state or score effect.

**For grading:**
- **Weak points:** one risk sentence names page 10 "the cumulative figure" (UB-604), and the advantage section calls the finding a "verification" result (UB-605).
- **Lite overview:** it does not carry the distinction (UB-606).
- **Funding wording:** two notes, NP-603 and NP-604.

**RA-109 live acceptance stays pending until independent grading.** RA-106's scoped acceptance is unchanged; RA-108 and overall hardening stay open.

## Artifacts

- [00](00_setup.json): setup, gates from both processes, isolation, sequences, Redis, DB hashes, preservation, frozen-artifact checks.
- [01](01_extraction.json)–[09](09_memo.json): pipeline rows.
- [09a](09a_grounded_context_rebuilt.json)–[09f](09f_section_scan.txt): rebuild, model call, all 8 calls, input/output check, guard edits, sentence scan. Scan hits are candidates for reading, not grades.
- HTTP probe:
  - [10](10_retrieval_ask_q1_q7.json): Q1–Q7.
  - [11](11_authorization_matrix.json): matrix, logouts, content types.
  - [11b](11b_reconciliation_by_principal.json): B-2 per principal.
  - [12](12_api_payloads.json) and [13](13_rendered_reports_text.json): API payloads and rendered text.
- Markdown: [14](14_markdown_utf8.json) and the exported bytes [14_ic_memo_export.md](14_ic_memo_export.md).
- Chrome: [15](15_browser_walks.json) and [browser/](browser/).
- [16](16_probes.json): numeric-parse probes carried from earlier runs.
- [process/](process/): server, worker, memwatch logs and probe stdout. [scripts/](scripts/): every run script, plus the derivation scripts that list each change from the memo-97 harness. [snapshots/](snapshots/): before/after snapshots, DB hashes, Redis, memo-97 field comparison.
