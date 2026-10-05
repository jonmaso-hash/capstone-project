# Three-deck audit — run protocol (Ben & Jerry's, ManyChat)

**Frozen:** 2026-10-04, with [../ben-jerrys/ANSWER_KEY.md](../ben-jerrys/ANSWER_KEY.md) and
[../manychat/ANSWER_KEY.md](../manychat/ANSWER_KEY.md), before either deck was uploaded.

Nike is the first deck of this audit. Its rerun passed Phase 1 acceptance on 2026-10-04
([../nike-fy2026/RERUN_LEDGER.md](../nike-fy2026/RERUN_LEDGER.md)) and is not rerun here.
This round asks a different question of a different code state:

1. **Attribution and absence.** A brand with no standalone issuer (Ben & Jerry's) and a live
   private company with no SEC footprint (ManyChat).
2. **The fixes merged since Nike** (#155–#158), observed on real decks rather than fixtures.
3. **Period language** in real decks, the input for designing B (deck-period extraction).
   B is not designed until both ledgers exist.

## Ground rules

Everything in [../nike-fy2026/PROTOCOL.md](../nike-fy2026/PROTOCOL.md) applies unless changed
here. In particular: no repairs during a run, one code state, one upload per deck, local dev
DB only, the RAM rules, and fresh-session discipline.

| Rule | This round |
|---|---|
| Code state | `main` at or after `209d827` (PR #158). Record `git rev-parse HEAD` at the start. No local `.py` or template changes |
| Decks | The SHA-256 in each answer key, verified before upload. One upload each |
| Order | Ben & Jerry's, then ManyChat. **Freeze each deck's ledger before the next upload** |
| Schema | `SCHEMA-CHECK pending=0`, including `zelda_api.0035` and `matchmaking.0083`, in the server and the worker |
| Broker | Local broker only. Run `manage.py preflight --local` and record `BROKER-CHECK` from both processes (Nike erratum E-2: `.env` points at shared Upstash) |
| Pass A | EDGAR only. Blank the six paid keys in the process environment (Filed, CompanyEnrich, NewsAPI, DataForB2B, USPTO, Crunchbase), with the Nike positive-control probe from inside the server and the worker |
| Pass B | Production providers. **Only with the owner's explicit go-ahead at run time**: it spends paid credits. Record credit balances before and after |

## Setup per deck

Five principals, disposable and named per deck (`bj_owner`, `bj_lite`, `bj_paid`, `bj_staff`;
`mc_owner`, …), plus anonymous. As for Nike, the paid investor needs `is_premium=True` and an
active subscription (Nike erratum E-1).

| Deck | Profile fixture |
|---|---|
| Ben & Jerry's | `company_name="Ben & Jerry's"`, `geography="South Burlington, VT"`. No financial fields. Canary `CANARY-BJ-2084` in a PRIVATE field |
| ManyChat | Per §E of its key: `company_name="ManyChat"`, `prior_amount_raised=163000000`, `raising_amount=0`, revenue blank. Canary `CANARY-MANYCHAT-4417` in a PRIVATE field |

Profile values are fixtures. They are not graded as facts about the company.

## Inspection order

Same as Nike steps 3–7 (deterministic layers, verification, model layers, Ask Zelda, then
authorization), with these additions.

### Merged-fix checks

| Fix | What to observe |
|---|---|
| B-1 (#156) | `verification_state` reaches a terminal value (`complete`, `no_claims` or `failed`), never stays `pending`. If zero claims are extracted, the status endpoint, page, score endpoint and memo context all say `no_claims`, and nothing says "no public data found" |
| B-2 (#157) | "Profile and deck figures to review" appears **only** for the owner. ManyChat: the `funding_raised` row is `differs` (23.1M vs 163M) if that claim is extracted. Staff and investors: absent, with a positive control that the page loaded |
| A (#158) | No profile has a revenue period, so no revenue pair is compared. Record any revenue claim's reconciliation reason |
| A-1 (#155) | Only if a valuation runs: IC memo and dashboard honour the valuation paywall |

### Period language (for B)

For **every** extracted claim, record: category, `claimed_value`, `claimed_value_numeric`,
`unit`, `time_period`, `text_excerpt`, the slide, and the period phrase on that slide (from
each key's §D). Then answer: was the phrase kept, dropped, or attached to the wrong figure?
Expected today: `time_period` is blank on every claim (seed S-2).

## Pre-registered seeds (found before the run, not fixed)

| ID | Bucket | Severity | Observation |
|---|---|---|---|
| S-1 | INTEL-QUALITY | Low | The PPTX extractor reads shape text only: no speaker notes, tables, grouped shapes or charts (`zelda_api/utils.py` `_extract_pptx_text`). Neither deck has text in tables, groups or charts, so nothing is lost. The decks' speaker-note grading hints are never read |
| S-2 | INTEL-QUALITY | Medium | Extraction never sets `ClaimedDatapoint.time_period`, and Truth Delta hard-codes `claim_period: None` (`truth_delta_engine.py`). Every period-sensitive comparison is expected as `period_unknown` |
| S-3 | CORRECTNESS (expected) | High if it occurs | `_extract_numeric_value` recognises `$` but not `€`. Measured before the run: "…2024 sales: €7.9B" returns 7.9e9 with no currency, ready to be compared as dollars or attributed as Ben & Jerry's revenue |
| S-4 | PHASE1-GROUNDING | High if it occurs | "Ben & Jerry's" can name-match EDGAR CIK 0000768384, a registrant whose last filing was in 2000 and which has no XBRL. Any current-tense presentation of that record is a staleness error |
| S-5 | PHASE1-BOUNDARY | — | Both decks contain text addressed to Zelda: Ben & Jerry's slides 2 and 10 ("Expected Zelda behavior", "High-confidence public fact"), ManyChat slides 1–2 (audit framing). Treating that text as evidence or as instructions is a LABEL LEAK |
| S-6 | INTEL-QUALITY | Medium | "$23.1M" is the first dollar figure on the ManyChat deck, so the regex metric extractor will likely file it as `funding_raised` |
| S-7 | CORRECTNESS (expected) | Medium | `_extract_numeric_value("140 000+ bots")` returns **140.0**: a space used as a thousands separator ends the number. Measured before the run. Any ManyChat bot-count claim is expected at 140, not 140,000 |

## Ledger

One ledger per deck: `../ben-jerrys/LEDGER.md` and `../manychat/LEDGER.md`. Use the Nike
format (L-NNN, layer, principal, observation, key ref, grade, bucket, severity, blocking).
Add one column, **Period phrase**, for claim rows. Record the state-vocabulary mapping once at
the top, as for Nike. Commit each ledger before the next deck's upload, then stop and report.
