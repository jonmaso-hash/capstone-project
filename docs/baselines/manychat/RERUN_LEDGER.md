# ManyChat — rerun ledger (after claim-extraction PR 2, Pass A, narrow)

Graded against the frozen [ANSWER_KEY.md](ANSWER_KEY.md), [LEDGER.md](LEDGER.md) (the narrow
run, doc 3129) and [../three-deck-audit/PROTOCOL.md](../three-deck-audit/PROTOCOL.md). None of
those files is edited. Run immediately after the Ben & Jerry's rerun, whose ledger was committed
first ([../ben-jerrys/RERUN_LEDGER.md](../ben-jerrys/RERUN_LEDGER.md), `43aceea`).

## Run record

| Item | Value |
|---|---|
| Date | 2026-10-10 (upload 22:41:00 UTC) |
| Code state | `main` @ `cbda41a` (PR #268), semantics `td.5`. No local `.py` or template changes |
| Deck | `manychat_series_a_audit_deck.pptx`, 175,622 bytes, SHA-256 `be7a7171…3ef1`, matched the key immediately before the request. One upload |
| Document | 3131, `document_type=pitch_deck`, `source_entity="ManyChat"` |
| Principal | `rmc_owner` (user 309, application 45): per key §E, `company_name="ManyChat"`, `prior_amount_raised=163000000`, `raising_amount=0`, revenue blank, canary `CANARY-MANYCHAT-4417` PRIVATE |
| Pass / scope | A only, narrow: same setup controls and deviations D-1 to D-4 as the Ben & Jerry's rerun |

## Results, before and after

| Layer | Frozen live run (doc 3129, `c3c26ca`, before PR 1) | Rerun (doc 3131, `cbda41a`, after PR 1 + PR 2) | Change |
|---|---|---|---|
| Chunks / insights | 12 / 1 | 12 / 3 | +2 insights (PR 1 recall) |
| Claims | 1: `$23.1M raised` | 3: `$23.1M raised`, `500M messages`, `140 000+ bots` | +2 (PR 1) |
| Bot count | — | 140,000 (S-7 fixed: not 140) | Fixed (PR 1) |
| Ownership | — | `$23.1M`: **named** ("Pitch Deck Hunt lists ManyChat…"); bots, messages: **implied** | New (PR 2, #265) |
| Currency | `$` treated as dollars | `$23.1M`: **unknown** (a bare `$` is not USD) | New (PR 2, #266) |
| Periods | none | none attach (see R-105) | New rule, nothing to attach (PR 2, #268) |
| Platform counts (900M / 275M / 100M) | not claims | not claims | Unchanged; still held by line separation, not by the ownership rule |
| Truth Delta | `no_data`, EDGAR only | Report 86, `td.5`: every claim `no_data` / `no_external_evidence`; score none, risk unknown | Unchanged verdicts, new semantics stamp |
| Entity Integrity | SEC filer `not_found` | Report 32: SEC filer `not_found` | Unchanged |
| B-2 (owner) | `differs`: $163,000,000 vs $23,100,000 | Panel present; row `not_comparable`, reason `profile_currency_unknown` | Changed by design (#266) — R-104 |
| Memo | Generated | **Not saved: R-001** (same failure as Ben & Jerry's) | Regression |
| Document status | `analyzed` | `error` (set by the memo failure) | Regression (R-001) |

## Ledger

| ID | Layer | Principal | Observation | Key ref | Period phrase | Grade | Bucket | Sev | Blocking |
|---|---|---|---|---|---|---|---|---|---|
| R-001 | 7 (memo) | owner | **Recurs (2 of 2 decks).** Anthropic 200 (2,619 input / 2,319 output tokens), then `Memo error: 'list' object has no attribute 'encode'`. Same cause as recorded in the Ben & Jerry's rerun: `archive_generated_memo` (`e566bea`, #245). Production impact: pitch-deck memos are lost after a billed call whenever a section comes back as a list | M1–M8 memo grounding, Q1–Q7 | — | Blocks memo checks | CORRECTNESS | **P1** | Memo layer |
| R-101 | 4 | — | Claims 1 → 3 with categories, units and source sentences matching the frozen PR 1 fixture (`zelda_api/data/claim_recall/manychat.json`) on a real upload. Bots are a usage count, never customers | M1, M5, M6 | — | PASS | — | — | No |
| R-102 | 4 | — | Ownership: `$23.1M` is `named` (the sentence names ManyChat, though a third party is quoted); usage claims `implied`. No platform count is stored as ManyChat's | M2–M4, I4 | — | PASS. M2–M4 still hold by line separation; the ownership rule is not what blocks them on this deck | — | — | No |
| R-103 | 5 | owner | Truth Delta `td.5`: M1 `$23.1M` is `no_data` / `no_external_evidence`, never verified, never current. Currency unknown would also block any comparison | M1 | "2015" (not attached) | PASS (INSUFFICIENT, as keyed) | — | — | No |
| R-104 | 5 | owner | B-2 panel still owner-visible (page 200, 58 KB, company name present; canary absent). The funding row is now `not_comparable` / `profile_currency_unknown` instead of `differs`, because profiles record no currency and #266 refuses money comparisons with an unknown currency. Correct under the currency contract, but it means **no profile money figure can be compared with any deck figure** until profiles record a currency. That also blocks the revenue/EBITDA comparison planned for the Zelda-Assessed Match | B-2 | — | Changed by design | PRODUCT DECISION | P2 | No (blocks reassessment v1 design) |
| R-105 | 4 | — | Period language: no claim attaches a period. "Traction by Apr-16" is a heading on its own line (excluded by decision); "messages/month" sits on slide 12 across lines, not recovered; "2015" is a bare year. Every claim keeps today's comparison rule | D | "by Apr-16", "messages/month", "2015", "this month" | PASS (by the frozen boundaries) | — | — | No |
| R-106 | 6 | owner | Entity Integrity: no SEC filer, no CIK, incorporation or Form D attributed to ManyChat | E1 | — | PASS | — | — | No |
| R-107 | 5 | owner | B-1: `verification_state` reaches `complete` (claims exist); nothing says "no public data found" | B-1 | — | PASS | — | — | No |
| R-108 | 7 (status API) | owner | As R-002 in the Ben & Jerry's rerun: the raw internal memo error reaches the owner's status endpoint | — | — | — | UX / hygiene | P3 | No |

## Summary

On a real private-company deck, PR 1 and PR 2 behave as designed: three correctly categorised
claims instead of one, the bot count no longer truncated, each claim's ownership recorded, a bare
`$` left as unknown currency, no period invented, and nothing verified, contradicted or presented
as current under EDGAR-only evidence. The platform user counts stay out, though by line
separation rather than the new ownership rule.

Two findings need decisions before the next phase:

1. **R-001 (P1, production):** memo saves fail when a section comes back as a list, on both decks.
2. **R-104 (P2, product):** profiles record no currency, so every profile-vs-deck money comparison
   is refused. That blocks the seller revenue/EBITDA comparison planned for reassessment v1.

Artifacts: [rerun/3131_dump.json](rerun/3131_dump.json), [rerun/upload.txt](rerun/upload.txt).
