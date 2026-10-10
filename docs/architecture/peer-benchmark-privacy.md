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

New internal snapshots carry privacy version 2 and internal cohort/contributor
IDs. Both views recheck discoverability and public field permissions before
showing frozen aggregates; revoking any contributor's disclosure suppresses
that metric. Cohort-field revocation or deletion suppresses the cohort. IDs
are stripped before rendering. Both owner and public views
reject older internal aggregates, whose source permissions and sample sizes
cannot be established from their stored JSON. This protects existing links
without paid regeneration or a database migration.

P-1a: numeric fields that default to zero (funding raised, current raise,
asking price, and years in business) have no explicit-disclosure marker. Their
zeros are treated as unknown for subjects and contributors, including external
subject comparisons. This conservatively excludes deliberately entered zeros
in those fields too; supporting them requires a separate disclosure marker or
nullable field design. Nullable financial fields still admit an explicit zero,
and EBITDA still admits negative values. Version 1 internal snapshots are
suppressed because they may contain default-zero aggregates. Saved contributor
values are rechecked for presence as well as current visibility.

P-1b: public links recheck the subject's current public field permissions on
every request, even if the viewer is the owner or staff. Private and connected
subject values and derived percentiles are masked in both tables. Private
cohort fields suppress comparisons that disclose them, including external
geographic comparisons. Model prose, cohort labels and citation excerpts are
withheld when supplied subject fields are not public, since they may repeat
owner-only data. Owner pages retain their private values. Rendering does not
rewrite saved reports, incur research charges or alter sharing controls.

`zelda_api.tests_peer_benchmark` checks both roles, four/five-peer boundaries,
small city/state cohorts, per-metric suppression, hidden-versus-absent parity,
private cohort fields, activity independence and legacy owner/public rendering.

E-1 (selected SEC identity), P-2 (external figure provenance), and claim
extraction attribution/currency/period handling remain separate follow-ups.
