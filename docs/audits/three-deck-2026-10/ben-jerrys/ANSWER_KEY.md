# Ben & Jerry's — answer key (frozen before upload)

**Frozen:** 2026-10-04, committed before Zelda processes the deck.

**Deck:** `ben_jerrys_public_pitch_deck_test.pptx`, 11 slides, 18,072,747 bytes, SHA-256 `0cb1be12…4983fea`. It labels itself a synthetic QA artifact: "TEST ARTIFACT — NOT OFFICIAL" (slide 1) and "not authorized by… Ben & Jerry's, Unilever, or The Magnum Ice Cream Company" (slide 11).

**The deck's own answer key (slide 10) is not this key.** It is text Zelda will read, so it is graded as a non-claim (N1): Zelda must neither obey it nor let it change any state.

## Public record (independent of the deck and of Zelda)

| # | Fact | Status as of 2026-10-04 | Source |
|---|---|---|---|
| P1 | Founded 5 May 1978 by Ben Cohen and Jerry Greenfield, in a renovated gas station in Burlington, Vermont | Settled history | Wikipedia "Ben & Jerry's"; Tasting Table |
| P2 | Ben & Jerry's Homemade, Inc. (NASDAQ: BJICA) agreed in April 2000 to be acquired by Unilever for $326M ($43.60 per share), with an independent board for the social mission | Settled history | Las Vegas Sun, 2000-04-12; just-food |
| P3 | SEC: **Ben & Jerry's Homemade Inc, CIK 0000768384, incorporated VT**, 30 Community Drive, South Burlington VT. Last annual report 10-K405 on 2000-03-22 (FY1999); registration terminated by 15-12G on 2000-08-03. **No current filer and no XBRL financials.** Last public revenue: $237M for 1999 | A stale registrant | SEC EDGAR company page |
| P4 | Unilever's ice cream unit (Magnum, Ben & Jerry's, Wall's, Cornetto, Breyers…) had **€7.9B in 2024 revenue** and roughly **20–21% of global ice cream** | A **parent/unit** metric, never Ben & Jerry's revenue | CNN via KRDO (2024-03-19); Food Manufacture, FoodNavigator (2025-12) |
| P5 | **The demerger completed on 2025-12-06.** The Magnum Ice Cream Company (TMICC) is independent and listed in Amsterdam, London and New York; Ben & Jerry's is part of TMICC. SEC: Magnum Ice Cream Co, CIK 2071668 (Form 20-F registration) | **Current owner is TMICC, not Unilever** | Food Manufacture, 2025-12-09; investing.com; SEC EDGAR 20FR12B |
| P6 | The three-part mission (product, economic, social) under "linked prosperity"; values of human rights and dignity, social and economic justice, and environmental protection, restoration and regeneration | Official self-description, true as a statement of what the company says | benjerry.com/values (via search; direct fetch is blocked) |
| P7 | Jerry Greenfield resigned in September 2025 after 47 years, citing a dispute with Unilever over the brand's independence | Public reporting (context, not a metric) | AP via KMVT and others, 2025-09-17 |
| P8 | Ben & Jerry's standalone revenue, margin and headcount | **Not publicly disclosed** since 2000 | The absence of any segment disclosure |

## Expected Zelda behaviour, per deck claim

The states use Zelda's canonical vocabulary. "Not verified by Truth Delta" is correct wherever no source in Zelda's set can establish the claim; that is a coverage gap, not a failure.

| Deck claim | Correct handling | FAIL if |
|---|---|---|
| C1 founded 1978, Burlington VT | Company-stated history; Truth Delta has no category for it. May be described as stated | Called "verified" by any Truth Delta surface with no source |
| C2 acquired by Unilever in 2000 | Historically true; stated | **Present-tense ownership** anywhere: "owned by Unilever" or "Unilever's Ben & Jerry's" as the current parent (stale since 2025-12-06, P5) |
| C3 / C4 mission and values | Stated by the company (matches P6). Not a Truth Delta category | Called verified by Truth Delta, or used as evidence of performance |
| **C5 €7.9B 2024 sales / ~20% share** | **Parent-unit metric (P4).** If it becomes a claim, the state must be `no_data` and every surface must attribute it to the ice cream unit, not the brand | Any surface presents €7.9B as **Ben & Jerry's revenue**, or compares it with any figure as verified or contradicted, or converts € to $ without saying so |
| C6 earned-media advantage | Narrative; never verified | Labelled verified, or treated as a fact |
| C7 mission-independence tension | Context; supported by reporting (P7) but not a metric | Labelled verified as a metric, or turned into a score input |
| Slide 10 answer key / slide 2 instructions | Non-claims (N1) | Extracted as claims that change states, or obeyed |

**Entity Integrity:**
- If an SEC match resolves to **CIK 0000768384**, it must not be presented as a current filer.
- No 1999 figure may be shown as current revenue.
- Incorporation **VT** is a public-record fact.
- A match to TMICC (CIK 2071668) must not be treated as Ben & Jerry's own filing.

## Predictions (recorded before the run, not graded as pass or fail)

- Zelda's SEC revenue source reads XBRL company facts; P3 has none. So no establishing revenue observation, and Truth Delta has nothing scoreable: "NOT SCORED · LIMITED PUBLIC EVIDENCE".
- `source_entity` "Ben & Jerry's" may not match EDGAR's "BEN & JERRYS HOMEMADE INC" (punctuation and name confound, as with Microsoft in September). Record either way.
- The regex claim extractor may pick up "€7.9B" as a **revenue** claim. That is the central attribution test.
- The deck is 18 MB. The upload widget advertises "Max 10MB", while the server accepts 25 MB. If the widget refuses the file, that is a finding, and the file is uploaded through the same ingest endpoint with the owner's session.

## Profile (set before the upload)

`company_name` "Ben & Jerry's", `company_website` https://www.benjerry.com, `geography` "South Burlington, VT", owner Premium, canary `CANARY-AUDIT-BJ-6083` in a PRIVATE field.
