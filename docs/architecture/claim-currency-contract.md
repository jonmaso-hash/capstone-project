# Claim currency and comparison contract

Frozen before implementation on main `2222058`, 2026-10-10. Expectations live
in `zelda_api/data/claim_currency/expectations.json`. The original PR 1 fixtures,
audit answer keys and stored chunks are not edited. This is the currency part
of claim-extraction PR 2; periods and general company attribution stay separate.

An amount retains an explicit currency code. EUR/€, GBP/£, USD/US$, CAD/C$,
AUD/A$ and the declared supported ISO codes are recognised adjacent to the
amount. A bare dollar sign is unknown. Conflicting currency labels are unknown.
Decimal-comma notation and ambiguous suffixes are refused rather than partially
parsed. A percentage or year cannot win over a currency amount. No FX conversion
or annualisation occurs. Counts and their units keep PR 1's meaning.

New Truth Delta comparisons require both monetary currencies to be explicitly
known and identical before any agreement, divergence percentage, corroborating
agreement or contradiction is calculated. The reasons are `currency_unknown`
and `currency_mismatch`; both are unscored. Existing authority, tolerance,
provenance, estimate and period rules still apply after the currency gate. A
compatible establishing observation is preferred to an incompatible one, with
the existing credibility ordering inside each set.

Claims and observations store currency separately from their existing unit.
Existing rows stay blank: the old dollar formatter is not currency evidence.
SEC revenue is explicitly USD because the reader selects companyfacts' USD
unit; Crunchbase total_funding_usd is explicitly USD. Its unqualified numeric
annual_revenue field has unknown currency. Provider labels, source location,
company geography and model knowledge do not supply a missing currency.

New reports carry semantics `td.4`. Stored historical reports retain their
recorded older semantics and the existing historical warning; this change does
not rewrite their verdicts, prose or scores. New comparison rows carry currency
metadata even when unknown, so their gate also applies if a caller forgets the
semantics stamp. Reverification uses td.4 and blank legacy input currencies
remain unknown. No paid or live deck rerun is performed by this PR.

Currency travels with both sides into the report and grounded memo context.
New observed figures are formatted with their recorded currency, never an
assumed dollar sign. Profiles do not record currency, so their monetary
reconciliation remains not comparable even if the raw numbers agree. Counts
remain comparable, and ownership/privacy checks are unchanged.

Frozen-deck controls: ManyChat keeps its three PR 1 claims, with the bare-$
funding amount's currency unknown. Ben & Jerry's still yields no company
claims under unchanged keyword/attribution gates, while its €7.9B parses as
7,900,000,000 EUR in isolation. Parent sales, shares and event years remain
negative company-claim controls. The final frozen-deck audit follows all three
bounded extraction PRs, not this one in isolation.
