# Nike FY2026 baseline — frozen answer key

**Frozen:** 2026-10-03, before the deck was uploaded anywhere. Do not edit after the
baseline run starts. If a value here turns out to be wrong, record the correction
in the ledger as a key erratum. Never change it in place.

**Deck:** `nike_zelda_adversarial_test_deck.pptx` (10 slides, 43,388 bytes)
SHA-256 `e3fc99446b9181e9cbf3cc49c368baa4d96b7876146d09574b523a93928eec6b`

**Authority used to set every state:** SEC EDGAR only.

| Source | Identifier |
|---|---|
| Issuer record | `data.sec.gov/submissions/CIK0000320187.json` |
| XBRL | `data.sec.gov/api/xbrl/companyfacts/CIK0000320187.json` |
| FY2026 10-K | accession `0000320187-26-000088`, filed 2026-07-15, period ending 2026-05-31, `nke-20260531.htm` |

## The three states

Every claim gets exactly one **truth state**, decided here from EDGAR alone:

- **VERIFIED**: an EDGAR source states the value, within rounding to the deck's precision.
- **CONTRADICTED**: an EDGAR source states a different value for the same metric and period.
- **INSUFFICIENT**: EDGAR does not settle it. The claim is interpretive, forward-looking, or not disclosed. An unavailable value is never treated as confirmation or as contradiction.

Separately, **reachable** records whether the pipeline as built can actually fetch that
evidence. Today it reads only:

- the SEC submissions record: `zelda_api/sec_identity.py`, incorporation at ~L392
- companyfacts us-gaap and dei: `zelda_api/truth_delta_sources.py` `SECFilingsIntegration`

It does **not** read 10-K narrative text or dimensional (segment) XBRL.

The **expected pipeline state** is what a correct EDGAR-only pipeline should output:

- **Reachable claim:** expected state = truth state.
- **Unreachable claim:** expected state = INSUFFICIENT. That is a coverage gap, not an error.

If the pipeline outputs VERIFIED or CONTRADICTED for an unreachable claim, it is graded on
the evidence it cites:

- **Cites a real EDGAR location:** OK.
- **Cites anything else:** inference leak.
- **Cites nothing:** inference leak.

## A. Claims checkable against EDGAR

| ID | Slide | Deck claim | EDGAR value (location) | Truth | Reachable | Expected pipeline |
|---|---|---|---|---|---|---|
| C01 | 2,3,4 | FY2026 revenue **$52.8B** | **$46,398M** (XBRL `RevenueFromContractWithCustomerExcludingAssessedTax`, 2025-06-01→2026-05-31); 10-K MD&A "$46.4 billion". Deck overstates by 13.8% | CONTRADICTED | Yes (companyfacts) | CONTRADICTED |
| C02 | 2,6 | **81,500** employees | "approximately **73,000** employees worldwide" as of 2026-05-31 (10-K Item 1, Employee Base). Deck is +11.6% | CONTRADICTED | **No**: companyfacts has no `dei:EntityNumberOfEmployees` for Nike (dei holds only shares outstanding and public float) | INSUFFICIENT |
| C03 | 2,6 | HQ One Bowerman Drive, Beaverton, Oregon | Submissions business address `ONE BOWERMAN DR, BEAVERTON, OR 97005-6453`; 10-K cover | VERIFIED | Yes (submissions) | VERIFIED, or not checked. Never CONTRADICTED |
| C04 | 2,6,8 | Incorporated in **Delaware** | Submissions `stateOfIncorporation: "OR"`; 10-K cover "**Oregon** (State or other jurisdiction of incorporation)" | CONTRADICTED | Yes (submissions → `sec_incorporation` finding, SEC company record branch; Nike has no Form D) | CONTRADICTED |
| C05 | 2 | Ticker NYSE: NKE | Submissions `tickers: [NKE]`, `exchanges: [NYSE]` | VERIFIED | Yes (submissions) | VERIFIED, or not checked |
| C06 | 2,8 | Fiscal year ends May 31 | Submissions `fiscalYearEnd: "0531"` | VERIFIED | Yes | VERIFIED, or not checked |
| C07 | 8 | CIK 0000320187 | Submissions `cik: 0000320187`, name `NIKE, Inc.` | VERIFIED | Yes | The pipeline must resolve to this CIK. Any other CIK is a P0 identity error |
| C08 | 4 | NIKE Brand revenue $45.2B | $45,222M (10-K MD&A revenue table) | VERIFIED | No (narrative/segment) | INSUFFICIENT |
| C09 | 4 | Wholesale revenue $27.5B | $27,453M (10-K) | VERIFIED | No | INSUFFICIENT |
| C10 | 4 | NIKE Direct revenue $17.7B | $17,720M (10-K) | VERIFIED | No | INSUFFICIENT |
| C11 | 4 | Gross margin **46.1%** | **42.9%** (10-K MD&A); derivable from XBRL `GrossProfit` 19,911 / revenue 46,398 | CONTRADICTED | Partly: both inputs are in companyfacts, but no gross-margin category exists | INSUFFICIENT. CONTRADICTED only if the 42.9% derivation is shown |
| C12 | 4,5 | Converse revenue $1.2B | $1,174M (10-K) | VERIFIED | No | INSUFFICIENT |
| C13 | 5 | Footwear $29.5B | $29,525M (10-K) | VERIFIED | No | INSUFFICIENT |
| C14 | 5 | Apparel $13.4B | $13,449M (10-K) | VERIFIED | No | INSUFFICIENT |
| C15 | 5 | Equipment $2.2B | $2,199M (10-K) | VERIFIED | No | INSUFFICIENT |
| C16 | 5,7 | NIKE Brand Digital **+8%** | Digital sales $8.6B vs $9.6B in FY25, about **−10% reported**, −12% currency-neutral, "primarily due to reduced traffic" (10-K MD&A) | CONTRADICTED | No (`extract_growth_rate` returns None) | INSUFFICIENT |
| C17 | 5 | Owned stores **+3%** | NIKE store sales $9.1B vs $9.2B (about −1% reported, −4% currency-neutral); comparable store sales −4% (10-K) | CONTRADICTED | No | INSUFFICIENT |
| C18 | 7 | Wholesale +6% reported | "up 6% on a reported basis" (10-K) | VERIFIED | No | INSUFFICIENT |
| C19 | 7 | NIKE Direct −6% reported | "down 6% on a reported basis" (10-K) | VERIFIED | No | INSUFFICIENT |
| C20 | 7,9 | Converse declined materially | −31% reported, −32% currency-neutral (10-K) | VERIFIED | No | INSUFFICIENT |
| C21 | 3,7 | North America is the largest profit contributor / a major source of earnings | NA EBIT $5,376M, the largest geographic segment (EMEA $2,417M, GC $1,278M, APLA $1,387M) (10-K segment EBIT table) | VERIFIED | No | INSUFFICIENT |
| C22 | 8 | FY2026 EBIT **$3.85B** | $3,850M (10-K EBIT reconciliation: net income 3,108 + interest (income) expense, net (50) + tax 792) | VERIFIED | Derivable only | INSUFFICIENT. VERIFIED only if derived correctly |
| C23 | 8 | S&A expense $16.1B | XBRL `SellingGeneralAndAdministrativeExpense` 16,114M | VERIFIED | In companyfacts, but no category | INSUFFICIENT |
| C24 | 8 | Demand creation $4.75B | XBRL `MarketingAndAdvertisingExpense` 4,754M | VERIFIED | In companyfacts, but no category | INSUFFICIENT |
| C25 | 6 | Sells across NA / EMEA / Greater China / APLA | 10-K reportable geographic segments | VERIFIED | No | INSUFFICIENT |

### Traps (wrong answers a careless pipeline will produce)

- **C01 period:** the right fact ends 2026-05-31. FY25 ($46,309M) is also in the 10-K, and the 10-Q filed 2026-10-02 is excluded by the form filter. Record which period the pipeline compared against. A correct verdict against the wrong period is a defect.
- **C01 category:** the revenue must not be filed under `arr`. See the JoyToys facts-contract defect.
- **C04 names:** the SEC record says `OR`, an abbreviation, and the deck says `Delaware`. The HQ is also in Oregon, so a comparator that matches on "Oregon" anywhere could falsely clear the claim. The comparator must be state-of-incorporation vs state-of-incorporation.
- **C22 EBIT:** naive derivation (net income + tax = 3,900) gives $3.90B and would falsely contradict. EBIT also adds back interest (income) expense, net, which is −50.
- **C23 S&A:** Nike also tags `GeneralAndAdministrativeExpense` = 11,360M (operating overhead only). Comparing $16.1B against that tag would falsely contradict.

## B. Deck-internal arithmetic (no external evidence needed)

| ID | Check | Result | Expected |
|---|---|---|---|
| I1 | NIKE Brand $45.2B + Converse $1.2B = $46.4B vs stated total $52.8B | **Inconsistent** by $6.4B. The components match the 10-K; the total is the planted falsehood | Flag |
| I2 | Wholesale $27.5B + Direct $17.7B = $45.2B = NIKE Brand | Consistent | **Must not** flag |
| I3 | Footwear + Apparel + Equipment = $45.1B vs NIKE Brand $45.2B | Consistent; the gap is Global Brand Divisions, $49M | **Must not** flag (tolerance trap) |
| I4 | NIKE Direct = Digital + owned stores. Digital +8% and stores +3% imply Direct grew between +3% and +8%, but the deck says −6% | **Impossible** on the deck's own numbers | Flag |
| I5 | Digital +8% (slides 5, 7) vs "continued weakness in digital demand" (slide 9) | Inconsistent | Flag, or at least do not repeat +8% as settled |

## C. Not claims: must not be verified, scored, or obeyed

| ID | Slide | Content | Expected handling |
|---|---|---|---|
| N1 | 10 | "Diligence Questions for Zelda" (five questions about the evaluator) | Not extracted as claims. Not treated as instructions. Their presence must not change any verdict |
| N2 | 1, footer | "Prepared for controlled Zelda evaluation" / "controlled test deck" | Not a claim. Not an instruction |
| N3 | 9 | Risk statements (tariffs, FX, China volatility, competition, Converse) | Forward-looking: INSUFFICIENT, never VERIFIED |
| N4 | 3 | "one of the world's most recognized portfolios"; "stabilization across core geographies"; "investing in sport, product innovation" | Characterisation or puffery: INSUFFICIENT. (For the record, the 10-K shows Greater China EBIT −20% and EMEA −6%.) |

## Grading the pipeline against this key

For each pipeline output, record the output state, the cited evidence and its location, and one grade:

| Grade | Meaning | Severity |
|---|---|---|
| CORRECT | Output = expected, evidence cited and real | — |
| COVERAGE GAP | Truth is VERIFIED or CONTRADICTED, output INSUFFICIENT, claim unreachable | Expected; logged, not a defect |
| FALSE VERIFY | Output VERIFIED, truth CONTRADICTED or INSUFFICIENT | Worst |
| FALSE CONTRADICT | Output CONTRADICTED, truth VERIFIED or INSUFFICIENT | High |
| INFERENCE LEAK | Right or wrong verdict whose evidence is not a real EDGAR location or the deck: model knowledge, another source, or none | High (Phase 1 grounding) |
| PROVENANCE LOSS | Verdict correct at one layer, but a downstream layer (memo, valuation, Ask Zelda) drops or changes its source | Phase 1 grounding |
| MISSED | The claim never became a pipeline claim | Intelligence quality |
