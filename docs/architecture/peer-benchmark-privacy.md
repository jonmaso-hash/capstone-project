# Peer benchmark privacy remediation (P-1)

The Interlink peer comparison is a shareable company-data snapshot. Investor
and buyer activity events have no peer-disclosure policy and are excluded
entirely, including memo opens, Truth Delta opens, introductions and messages.

Cohort selection and numeric fields use the existing profile visibility
authority with a public viewer. Owner, staff and connection privileges cannot
be carried into a public report. Founder sector and stage are authorized before
filtering; private geography cannot determine geographic cohort membership.

Each geographic cohort needs at least five peers. Each metric separately needs
five publicly visible numeric contributors. Smaller cohorts publish no count or
metrics; smaller metric samples publish no median, percentile or sample count.
Five is a suppression threshold, not a guarantee of anonymity.

New internal snapshots carry privacy version 1 and internal cohort/contributor
IDs. Both views recheck discoverability and public field permissions before
showing frozen aggregates; revoking any contributor's disclosure suppresses
that metric. Cohort-field revocation or deletion suppresses the cohort. IDs
are stripped before rendering. Both owner and public views
reject older internal aggregates, whose source permissions and sample sizes
cannot be established from their stored JSON. This protects existing links
without paid regeneration or a database migration. External research and the
owner's report-sharing controls are unchanged by this remediation.

`zelda_api.tests_peer_benchmark` checks both roles, four/five-peer boundaries,
small city/state cohorts, per-metric suppression, hidden-versus-absent parity,
private cohort fields, activity independence and legacy owner/public rendering.

E-1 (selected SEC identity), P-2 (external figure provenance), and claim
extraction attribution/currency/period handling remain separate follow-ups.
