# Independent grading — ManyChat post-merge run at 9b6d215 (document 3138, memo 96)

**Recorded:** 2026-10-13. **Additive:** this file changes nothing in [RERUN_LEDGER.md](RERUN_LEDGER.md), the run's
artifacts, memo 96 or any earlier memo, document or evidence.

## Grade

**Partial pass.**

| Ledger | Grading decision |
|---|---|
| FF-405 | **Confirmed P2, PHASE1-GROUNDING (provenance failure).** The stored `zelda_advantage` sentence assigns Pitch Deck Hunt to [C1, C2, C3] and calls it "the narrator of the funding and traction claims". The grounded metadata gives Pitch Deck Hunt only for C1/S3. C2/C3 are the checked company traction statements that correspond to S1/S2 and have no narrator |
| FF-411 | Markdown export without a charset: to be fixed in a separate focused commit (`text/markdown; charset=utf-8`) |
| D-6 | Closed by the staff Truth Delta browser addendum: [addendum-staff-td/STAFF_TRUTH_DELTA_ADDENDUM.md](addendum-staff-td/STAFF_TRUTH_DELTA_ADDENDUM.md) |

The follow-up fix validates narrator assignments against each cited reference's metadata and is made on its own branch from
main. It preserves company self-reports, citations, correct third-party attribution and legitimate questions, and changes no
ownership, currency, structured periods, scoring, tiers or raw-source boundary.

## Status after grading

- **Memo 96:** kept as generated; not regenerated or edited.
- **RA-106:** pending. Not marked complete.
- **Zelda hardening:** not complete. Nothing was deployed; paid-source Pass B was not run.
