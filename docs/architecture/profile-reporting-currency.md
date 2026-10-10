# Profile reporting currency (R-104)

Owner decision, 2026-10-10: one explicit reporting currency per profile.

Founder, investor, seller and buyer profiles each record `reporting_currency`.
Every money field on that profile uses it. The editor asks the owner to confirm
that all amounts use the selected currency. Changing the selection labels the
recorded amounts; it never converts or changes their numbers.

Existing profiles remain blank. New forms also offer “Not stated”; neither a
displayed dollar sign, location, equal number nor platform billing currency is
evidence of the currency. Supported codes are centralized in
`matchmaking/currencies.py`; form choices validate them.

Money comparisons require explicit matching currencies:

- Owner-only profile/deck reconciliation preserves both values but abstains
  if either currency is unknown or if they differ. Revenue-period and default-zero
  rules still apply. Reconciliation is self-reported consistency, never Truth Delta
  verification or an investment recommendation.
- Money in grounded memo inputs carries the selected currency or “currency unknown”.
  The valuation facts' profile/document reconciliation also records currency and
  refuses confirmation/conflict on unknown or differing units.
- Asking price versus budget, minimum cheque versus whole round and prediction
  price comparisons abstain on unknown or differing currencies. Hard-filter cache
  keys include the currencies while respecting hidden raise fields.
- Monetary search filters use the viewer's explicit profile currency on deal
  dashboards, and an explicit selector for founder search. Unknown currencies
  produce no monetary-filter results. Existing field-visibility gates run first.
  Ask Zelda money searches also need a currency explicitly supplied in the request
  or question. A model-guessed currency or a bare dollar sign does not establish it;
  relaxation cannot introduce companies using other currencies.
- Interlink peer money metrics need at least five public contributors using the
  subject's explicit currency. Counts are independent of currency. Saved aggregates
  recheck contributors' current currencies and permissions. Privacy version 3
  withholds older aggregates until the existing offline refresh command rebuilds
  them; no paid research is required for that refresh. External benchmark unit,
  period and source admission rules remain in force.

Public money displays show the recorded code or unknown currency. None of this
infers FX rates, annualizes a figure, rewrites a historical Truth Delta verdict,
or implements Zelda-Assessed Match.

ManyChat's frozen `$23.1M` claim stays currency-unknown. Selecting USD on its
profile does not resolve the deck currency and does not make that pair comparable.
Frozen audit ledgers and expectations are unchanged.
