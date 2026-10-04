# Three-deck intelligence audit — ledger

Graded against [PROTOCOL.md](PROTOCOL.md), which was frozen at `cef12b2` before the first upload. Findings are recorded, not fixed: the pipeline completed every time, so nothing needed repair.

## 1. Nike

**Run:** 2026-10-04 on `main` @ `3d05561`.
- **Documents:** 3122 (`pitch_deck`), 3123 (`business_valuation`).
- **Owner:** `audit_nike_owner` (user 295, Application 38, Premium, Beaverton OR, nike.com).
- **Setup control:** `preflight --local` passed in the shell. The server and worker each printed the broker, result backend and cache as `localhost` and 0 pending migrations.
- **Providers:** Filed, CompanyEnrich, NewsAPI and DataForB2B configured; Crunchbase not configured. DataForB2B balance 2,993.9 before and after (0 credits spent).
- **Model spend:** three calls. Truth Delta explanation 1,082 in / 117 out tokens; memo 3,026 / 2,685; valuation 894 / 798.
- **Worker:** ran only this run's tasks: the pipeline, claims, Entity Integrity, Truth Delta, the memo, notify and the valuation, plus two match refreshes from creating the investors.
- **Setup incident:** the first setup script ran before local Redis was up. It committed the rename of Application 36 and a partial owner, then failed in a save signal. Those rows were deleted and the setup was rerun cleanly, all before any upload.

### Layer results against the protocol

| Layer | Result | Evidence |
|---|---|---|
| Extraction / chunks | **PASS** | 10 slide markers, none in the preview; chunks on pages 1–10; `semantic-hash-v1` |
| Claims | **PASS** | `employees` cites slide 6; `revenue` cites slide 3 (the excerpt is still the truncated regex capture, L-024) |
| Truth Delta state | **PASS** | Revenue `no_data`/`period_unknown` with SEC 46,398,000,000 FY2026 10-K (`can_establish`, `sec_filing`); employees `no_data`/`no_external_evidence`; DataForB2B `ambiguous`, 0 credits |
| Score | **PASS** | None / `unknown` / `td.3` |
| Summary | **PASS** | Begins "Limited public evidence: none of the 2 claims could be verified or contradicted against a public source." No "overstated", "red flag", "contradicts" or "inaccurate" anywhere in the report |
| Rows | **PASS** | One per claim. Revenue reads "$46.4 billion (SEC EDGAR, FY2026 10-K (period ending 2026-05-31))"; employees "No external data found". Both model explanations passed the guard (each says the claim could not be established) |
| Truth Delta page (browser) | **PASS** | "N/A · NOT SCORED · LIMITED PUBLIC EVIDENCE"; cards 2 analyzed / 0 verified / 2 not established; chart Verified 0 / Contradicted 0 / Not established 2 (one amber bar, screenshot); the rollup is the Limited-public-evidence sentence; no % in coverage |
| IC memo / Intelligence Report | **PASS** on coverage; **FAIL** on two other defects (A-1, A-2) | "Evidence Credibility: not scored" plus the Limited sentence; bars one amber 100% segment, "Not established — 2 (of 2)"; no "No external data —". "What Zelda noticed": "An external figure was found for revenue, but its period could not be confirmed as comparable." |
| Readiness card | **PASS** | "Evidence Credibility: Not enough comparable public evidence to score" |
| Entity Integrity | **PASS** | nike.com matches (loaded `/mx/`); name matches; Filed `couldnt_check` (ambiguous, OR); SEC filer matches CIK 0000320187; SEC incorporation OR `public_record`; founder name `not_found` on the site |
| Memo | **PASS, with a note** | Generated after the report; "The company states revenue of $52.8 billion [S1], though the period for this figure is unknown; SEC EDGAR establishes… $46.4 billion"; "cannot be confirmed as comparable". No "500 people", no canary, no advice. *Note:* the literal label "INSUFFICIENT" is absent this run; the meaning is stated in prose |
| Valuation | **PASS against the pre-registration; finding A-3** | The preview hides the range. It describes revenue as "disclosed", never "verified", and says its method is a revenue multiple on the disclosed figure |
| Authorization | **PASS** | Canary visible only to the owner and staff (in-process probe, and absent from the Lite browser text and HTML); search and RAG 403 for both investors; anonymous redirected or 403 everywhere; valuation API owner/staff only |
| Residuals | As pre-registered | L-007, L-010, L-011, L-012, L-024 |

### Findings

| ID | Sev | Surface | Observation |
|---|---|---|---|
| A-1 | **P1** | IC memo page and download | **The IC memo shows the paid valuation range.** The owner (a Premium founder; founder valuations are pay-per-use) has a preview-tier valuation whose page says "The exact range is included in the full Zelda AI report… Upgrade to Zelda AI — $9.99". The same owner's IC memo shows "Range: $105,600,000,000 – $184,800,000,000" with the methodology sentence. The IC memo is built to be shared with investors, so the paid number reaches them too |
| A-2 | **P2** | IC memo page; Intelligence Report "Worth investigating" | **Memo list fields are stored as Python list strings and rendered raw.** `supported_points`, `open_concerns` and `questions_for_management` hold `"['…', '…']"`. Readers see `['What fiscal period does…` and `["The revenue figure discrepancy…`, including investors. Pre-existing: the Nike rerun's memo already had it in `questions_for_management` |
| A-3 | **P2** | Valuation (3123), and the valuation section of the IC memo | **The valuation is built on the deck's figure with no reference to established evidence.** "Disclosed annual revenue of $52.8 billion"; a revenue multiple applied to $52.8B (range $105.6B–$184.8B); scorecard "Revenue A+". It does not mention SEC's $46.4B or that Truth Delta could not establish the figure. The valuation pipeline does not consult Truth Delta (by design, `intelligence_pipeline.process_valuation_document`). "Disclosed" is accurate, but a reader gets a precise range on an unconfirmed number |
| A-4 | P3 | Profile Analysis | "Upload a Pitch Deck or Video — Profiles without pitch materials get far fewer memo opens" is shown after the owner uploaded a deck through the Zelda widget, which does not set `Application.pitch_deck` |
| A-5 | P3 | Valuation page | A Premium founder is shown "Zelda Lite Report" and "Upgrade to Zelda AI — $9.99". That matches the pricing (founder valuations are pay-per-use), but "Upgrade" and "Lite" read as if the subscription were missing |
| A-6 | P3 (carry) | Profile Analysis | Probe GETs became real engagement: "2 investor views", "Analyzed with Zelda", memo and Truth Delta views. The L-025 GET side effect is still open |
| A-7 | P3 (ops) | Environment | `.env` holds `USPTO_ODP_API_KEY`, but no code reads it. The key is inert |

**Passing controls:**
- Every canonical surface agrees: state, score, summary, rows, cards, chart, bars, the coverage sentence and the readiness card.
- No coverage percentage appears anywhere. The remaining percentages are memo prose ("a 13.8% discrepancy that cannot be reconciled"), Section Coverage, and funnel conversion rates.
- Truth Delta model spend fell to 117 output tokens (explanation only).
- No DataForB2B credits were spent on an ambiguous domain.
- The canary held.

Artifacts: [`nike/`](nike/), files 01–16 (13 = the rendered surfaces, 15 = the browser walks, 16 = the valuation).
