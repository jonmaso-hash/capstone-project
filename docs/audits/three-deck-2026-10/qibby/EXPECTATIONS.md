# Qibby Saves — pre-registered expectations (addendum to PROTOCOL.md)

**Frozen:** 2026-10-04, committed before the upload. This is the launch-market test: a private company with little or no public evidence. Per the protocol, it is graded on extraction, evidence labelling, Entity Integrity and the usefulness of the memo, **not** on how many claims verify.

**Deck:** `media/decks/Qibby_Saves_LLC_Pitch_Deck.pptx`, 11 slides, 40,498 bytes, SHA-256 `90958bc78efef83a…`. This is a fresh upload. Local document 1's earlier outputs are not used: leaked tasks overwrote them (rerun erratum E-2).

**Setup:**
- Seed Application 6 (`founder6`, "Qibby Saves LLC") is renamed "Qibby Saves LLC (seed founder6)" to avoid a name collision, as was done for Nike.
- New owner `audit_qibby_owner`, Premium. Profile: `company_name` "Qibby Saves LLC", `geography` "New York, NY", stage "Series C", sector Healthcare Technology, no website (the deck gives none), canary `CANARY-AUDIT-QIBBY-2290`.

**Privacy:** slide 10 has a contact email and phone number. Committed artifacts redact both (`[redacted-email]`, `[redacted-phone]`).

## What the deck states

| # | Statement | Slide | Kind |
|---|---|---|---|
| Q1 | 200 employees ("Company Size", and again on "Traction") | 2, 7 | Checkable metric |
| Q2 | Current revenue $4.5M | 7 | Checkable metric |
| Q3 | Prior capital raised $20M | 7 | Checkable metric (Form D could speak to it) |
| Q4 | Seeking a $20M Series C; 15 months of runway | 8 | **The ask, not something raised** |
| Q5 | Founded by William Quibby; HQ New York; 4 years in business | 2, 10 | Entity and history |
| Q6 | Problem, solution, market and growth narrative | 3–6, 9, 11 | Narrative |

## Expected

| Layer | Must show |
|---|---|
| Extraction | 11 slides; 11 chunks on pages 1–11 |
| Claims | Whichever of Q1–Q3 the extractor finds, each citing its slide. Q4 must not become a `funding_raised` claim of $20M *raised* by misreading the ask (Q3 is also $20M, so check which slide each claim cites) |
| Truth Delta | No public source for a private LLC, so each claim is `no_data`/`no_external_evidence` (or `source_unavailable` if a source fails). If no claims are extracted, the B-1 presentation recurs; record it, do not re-grade it |
| Score | None / `unknown`. Score card "NOT SCORED · LIMITED PUBLIC EVIDENCE" (when a report exists) |
| Coverage | "Limited public evidence: none of the N claims could be verified or contradicted against a public source."; counts only; bars all "Not established" |
| Entity Integrity | No website on the profile, so nothing is checked there. Filed: one NY-scoped search; a miss is silent and is never a finding against the company. SEC: no filer, no Form D, reported plainly. **Nothing may present absence of public records as evidence that the company is not real** |
| Memo | Every figure labelled company-stated (self-reported). The $20M ask is not described as raised. No advice. No canary. Not graded on whether it notices that $4.5M of revenue for 200 employees (about $22.5K per employee) is unusual, since L-012 is a known residual; recorded either way |
| Valuation | May use the stated $4.5M, but must say the figure is company-stated, not verified |
| Private-company presentation (PR #154) | Nothing reads as a failing grade: no "%" in coverage, no "Unverified", no "0/3 verified (0%)". "Not established" means a missing source, not a judgement of the company |
| Authorization | Canary only for the owner and staff; search/RAG 403 for investors |
