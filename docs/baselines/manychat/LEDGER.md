# ManyChat — ledger (three-deck audit, deck 3, Pass A, NARROW run)

Graded against [ANSWER_KEY.md](ANSWER_KEY.md) and [../three-deck-audit/PROTOCOL.md](../three-deck-audit/PROTOCOL.md) (frozen at `b9f6867`). Neither is edited.

**Scope, by the owner's instruction (2026-10-04, low remaining credit):** run the deck from upload to claims, then exercise only what the Ben & Jerry's run could not: B-1, B-2, A and the Truth Delta outcome. The five-principal browser matrix, retrieval and Ask Zelda (Q1–Q7), Pass B and cosmetic residuals were **deliberately not run**. Other principals were used only to prove the B-2 boundary.

**Run:** 2026-10-04 23:06 PDT. **Code:** `main` @ `bcb295a` (merge of #160, docs only; no `.py`/template diff from `b9f6867`). **Deck:** SHA-256 `be7a7171…3ef1` matched on disk, from the served copy, and in the page. Uploaded **once** as `mc_owner` through the Zelda widget → document **3129** (201). **Nothing was repaired.**

## The question, answered

> Can a normal private-company pitch deck currently make it from upload → claims → Truth Delta/reconciliation, and do A/B-1/B-2 behave correctly when real claims exist?

**Mechanically, yes.** Upload → 12 chunks → 1 insight → **1 claim** → Truth Delta report 85 → reconciliation → memo all ran, in order, on a local broker with paid keys off.

**When a claim exists, B-1 and B-2 behave exactly as designed:**
- B-1: `complete`, a terminal state.
- B-2: the owner sees `differs` (profile $163,000,000 vs deck $23,100,000). Lite investor and staff see no panel; anonymous is redirected. The raise guard does not fire.
- A could not be exercised: the deck has no revenue figure.

**In substance, no.** Claim extraction is the launch blocker, and it now fails across both deck types:

- Ben & Jerry's: 7 insights → **0** claims.
- ManyChat: 1 insight → **1** claim. That claim (`$23.1M raised`) comes from **slide 2, the audit-framing slide** (key I4), not from the company's own deck. The company's own ten slides produced **zero** claims, though they contain 140,000+ bots, 500M messages, 500M messages/month and three platform user counts.

The two failures share **one cause** with two symptoms (see Diagnosis). It is structural, not deck-specific.

## Run record

| Item | Value |
|---|---|
| Environment | `BASELINE-ENV-CHECK` from inside the server (pid 23216) and the worker (pid 14632): all six paid keys `False`, Anthropic `True` (`run/00`) |
| Broker / schema | `BROKER-CHECK` all four `redis://localhost` in both processes; `SCHEMA-CHECK pending=0`, with 0035 and 0083 applied, in both. Fresh local Memurai (`dbsize 0`). No migrations run |
| Principals | `mc_owner` (305, Application 42), `mc_lite` (306, Lite investor). `bj_staff` (304) reused as the staff control. Paid investor not needed for B-2 |
| Profile fixture (key §E) | `company_name="ManyChat"`, `prior_amount_raised=163000000`, `raising_amount=0`, revenue blank, `revenue_period` blank. Canary `CANARY-MANYCHAT-4417` in `reason_for_capital` (PRIVATE). `stage="Series A"` and `sector="Software"` are fixture choices, not graded |
| Worker chain | pipeline (12 chunks, 1 insight) → claims (1) → Entity Integrity (report 30) → Truth Delta (report 85) → memo 89 (42.9 s) → notify |
| Rows | chunks for slides 1–12; insight 4864; claim 2350; observations none; Truth Delta report 85; Entity Integrity report 30; memo 89 |
| Pre-existing rows | None for ManyChat (checked before the upload) |

## Claims (period language, for B)

| Claim | category | claimed_value | numeric | unit | time_period | text_excerpt | slide | Period phrase on slide | Kept / dropped |
|---|---|---|---|---|---|---|---|---|---|
| 2350 | `funding_raised` | "$23.1M raised" | 23100000.0 | "" | "" | "$23.1M raised" | 2 (`page_number` 2, "Insight: Funding") | "a **2015** Series A deck with $23.1M raised" | **Dropped**: "2015" and "Series A" cut from the excerpt; `time_period` blank (S-2) |

The other §D phrases have no claim to attach to: "Traction by Apr-16" and the Jul-15…Apr-16 axis (slide 10), "messages/month" vs "messages" (slides 12 / 10), and "this month" (slide 12). All are **dropped** with their figures.

## Merged-fix checks

| Fix | Observation | Result |
|---|---|---|
| B-1 (#156) | `verification_state=complete` within 5 s; never `pending`. With a claim present, "no public data could be found… (checked SEC EDGAR)" is the correct wording, scoped to the claim | **PASS** |
| B-2 (#157) | Function: owner → one row `prior_amount_raised`, `differs`, 163,000,000 vs (23,100,000), claim 2350; `mc_lite`, `bj_staff`, anonymous → `[]`. Browser, owner: panel shows "Previously raised: your profile says $163,000,000; the deck says $23,100,000", with save dates and "not when the figures were true". In-process page, Lite and staff: 200, page marker present (positive control), no panel section; anonymous 302 to login. `raising_amount=0`, so `deck_claim_may_be_the_raise` correctly does not fire | **PASS** (positive and negative controls) |
| A (#158) | No revenue claim in the deck and no profile revenue, so no revenue pair | **Not exercisable** (neither audit deck states revenue) |
| Truth Delta, EDGAR only | Report 85: score `null`, risk `unknown`, "NOT SCORED · LIMITED PUBLIC EVIDENCE", 1 claim, 0 verified, 1 not established. `source_diagnostics.sec=not_found`, `provider_outcomes.dataforb2b=unconfigured`, `claim_period` null | **PASS**: INSUFFICIENT, as the key expects for M1 |

## Grades (only rows this narrow run reached)

| ID | Observation | Grade | Outcome class |
|---|---|---|---|
| M1 $23.1M | Extracted as `funding_raised` (S-6 as predicted), but from the audit-framing slide 2. Truth Delta: not established. Memo: "The company states it has raised $23.1M in total funding [S1]… could not be confirmed or denied". Never "verified". Undated: "2015" was dropped, so the memo's "has raised" reads as current | INSUFFICIENT (pass); **undated stale total** | True pass on state; new failure on staleness wording (MC-4) |
| M2–M4 platform users | Not extracted, so no attribution | No ATTRIBUTION ERROR | Correct abstention |
| M5 140,000+ bots | Not extracted, so S-7 (→ 140) was never reached | — | Expected observed failure (latent S-7) |
| M6 500M vs 500M/month | Not extracted; I1 not flagged | — | Expected observed failure |
| M7 "launching this month" | Not extracted | — | Correct abstention |
| E1 SEC identity | `sec_filer` `not_found`; no CIK, Form D, incorporation or address anywhere | No INVENTED IDENTITY | True pass |
| I4 audit framing | The **only** claim came from the audit-framing slide | — | New failure (MC-2) |
| Canary | Absent from the Truth Delta page for owner, Lite, staff and anonymous (only the page was probed) | — | — |

## Diagnosis: where candidate claims are lost (read-only replay)

`run/13_extraction_trace.json` replays the analyzer (`ZeldaIntelligencePipelineV2._smart_extract` and `_select_insights`) and the claim gate (`extract_claims_from_insights`) on the stored chunks of both documents. Nothing is written. It reproduces both runs exactly: 3128 gives 7 insights and 0 claims; 3129 gives 1 insight and 1 claim.

**The only path from a deck to a claim** is: one keyword-scored regex sentence per category (8 categories) → the claim stage keeps only 5 of those categories (Revenue, Traction, Team, Funding, Market) → admissibility check → `$`-only money parse. **A deck can therefore never yield more than 5 claims, one per category**, however many figures it states.

| Stage | Ben & Jerry's (3128) | ManyChat (3129) |
|---|---|---|
| 1. Keyword candidates (`_smart_extract` per chunk) | 19 candidates across 7 categories; Funding 0 | **2** candidates in total, both Funding (slides 1–2). **0** for Traction, Market, Revenue, Team, Product, Problem, Risk. Slide 10 is titled "Traction" and states "140 000+ bots", "500M messages", but "traction", "bots" and "messages" are not keywords (Traction's keywords are "customers users growth adopted retention metric"). Slide 4's "100M / 275M / 900M people" matches no category |
| 2. Selection (`_select_insights`: one per category) | 7 kept. Revenue picks slide 6's caveat sentence over the €7.9B line; Market and Risk pick slide 2 audit text | 1 kept: the slide-2 framing sentence over slide 1 |
| 3. Category whitelist | Problem, Product and Risk dropped (not mapped) | — |
| 4. Admissibility + numeric | Market and Revenue: no `$` number (€ is not money to `currency_value`); Team and Traction: inadmissible (no people or customer noun) → **0 claims** | Funding: "raised" + `$23.1M` → **1 claim** |

**Shared cause:** the claim layer is fed by a keyword-gated, one-best-sentence-per-category regex analyzer, with a `$`-only money parser and a 5-category whitelist. It is not a deck-specific edge case.
- **Ben & Jerry's** fails at stages 2–4: candidates exist, but selection picks the wrong sentence and € is not money.
- **ManyChat** fails at stage 1: the vocabulary misses almost every slide, including one literally titled "Traction".

A realistic deck whose metrics are not phrased as "$N revenue", "N customers" or "raised $N" yields zero to one claims. Truth Delta, B-2 and A are unreachable for most of what a deck says.

## Findings

| ID | Layer | Observation | Bucket | Sev | Class |
|---|---|---|---|---|---|
| MC-1 | 3–4 | Claim extraction caps out at ≤1 per category. On a real private deck it yields 1 claim, and 0 from the company's own slides. Cause shared with B&J L-001 (diagnosis above). **Top Zelda launch blocker** | INTEL-QUALITY / PHASE1-GROUNDING | **P0 for launch** | New failure (systemic) |
| MC-2 | 4 | The only claim is extracted from slide 2, the audit-framing meta slide (I4), which quotes a third party ("Pitch Deck Hunt lists…") rather than the company | INTEL-QUALITY | P2 | New failure |
| MC-3 | 4 | `text_excerpt` "$23.1M raised" drops "2015" and "Series A"; `time_period` blank (S-2) | INTEL-QUALITY | P2 | Expected observed failure (S-2) |
| MC-4 | 9 | The memo states "has raised $23.1M in total funding" with no date. That is a stale 2016-era total presented in a current-reading tense. It never says verified, and it is attributed to the company ("The company states") | PHASE1-GROUNDING | P2 | New failure (staleness wording) |
| MC-5 | 6 | Entity Integrity: "No SEC filer with this name was found on EDGAR. Most private companies never file with the SEC." Correct for ManyChat (contrast B&J L-006) | — | — | True pass |
| MC-6 | — | S-6 confirmed: "$23.1M" filed as `funding_raised`. S-7 latent (no bot claim) | — | — | Expected observed failure |

## Verdict by class

- **True pass:** B-1 (terminal `complete`); B-2 owner-only `differs` with positive and negative controls and the raise guard idle; Truth Delta INSUFFICIENT for M1 under EDGAR only; no INVENTED IDENTITY (E1); no ATTRIBUTION ERROR (M2–M4).
- **Correct abstention:** M2–M4 and M7 not extracted, so nothing misattributed or forward-dated.
- **Expected observed failure:** S-2 period dropped (MC-3); S-6 (MC-6); S-7 latent; I1 unflagged.
- **New failure:** MC-1 systemic claim-extraction ceiling (shared cause with B&J L-001); MC-2 claim from audit framing; MC-4 undated funding total in memo prose.
- **Not exercised (by scope):** A (no revenue in either deck); five-principal matrix; Q1–Q7; Pass B.

## Not done (by instruction)

No fixes. No Pass B. No full authorization matrix, retrieval or Ask Zelda probes. The `mc_*` users and document 3129 remain in the local DB.
