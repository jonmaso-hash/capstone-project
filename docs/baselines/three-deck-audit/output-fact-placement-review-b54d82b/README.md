# Review of the OF-704/OF-705 fact placement at `b54d82b` (changes required)

**Separate, additive record.** It edits no earlier evidence, grade, memo, ledger or frozen fixture.

| Item | Value |
|---|---|
| Decision | **Changes required.** Leave `fix/basis-label-source-context` unmerged |
| Reviewed evidence head | `b54d82b65241f74d5b1c97b047c52148b985f2e7` |
| Application commit | `8dfe5f5`; tests-only follow-up `91a9071` |
| Basis helper Git blob | `696cbc5e16dac0aa402a6e6d560d5138f4c179ae` |
| Test module Git blob | `6de4d63f9db92a0ffa59d893b1d68c8a95e33e79` |

## Earlier findings corrected (per the reviewer)

- The memo-99 replay states each fact with its own basis, page, context and citation in the two affected sections. Page 12 keeps the explicit monthly rate; the dated page-10 heading and bots stay on page 10. The "either/or" formulation is gone. The affirmative contradiction label still becomes ambiguity.
- The previous probes behave as requested: denials and insufficient-evidence statements unchanged; the tested conditional scenarios unchanged; interleaved refs keep S1, S3, S2. The accepted memo-98 conditional-overstatement correction is still active.
- Independent execution: 83 helper test methods pass (helper bodies and memo-98/99 fixtures under unittest adapters; database-backed classes excluded). The four supporting pure modules and four memo-98/99 fixture files match the reviewed head.

## New findings

### P2: location repair deletes an unrelated clause and transfers its narrator

`_place_clause_start` treats only `;`, `:` and em dashes as boundaries; `_reporting_verb` takes the first reporting verb before the location phrase; `_location` replaces everything between that verb and the citation group, so a comma-linked earlier clause is swallowed.

Through the full normalisation → time → funding → basis sequence on the memo-99 normalised payload:

| Input | Output at `91a9071` |
|---|---|
| "Pitch Deck Hunt reports $23.1M raised [S4], while the usage figures appear on the same slide [S2, S3]." | "Pitch Deck Hunt reports 500M messages with no explicit interval [S2] on page 10, under 'Traction by Apr-16', and separately 500M messages/month [S3] on page 12 (…)." Only `basis_source_location` fires; the funding fact and S4 disappear and Pitch Deck Hunt becomes the narrator of company usage facts |
| "The company reports revenue of $10M [C8], while the message figures appear on the same slide [S2, S3]." | a company usage statement; the revenue fact and C8 deleted |
| "Revenue is $10M [C8], and the message figures appear on the same slide [S2, S3]." | the revenue clause and C8 deleted |

**Required:** repair only a confidently identified offending usage clause; preserve unrelated clauses and every citation in order; never borrow a subject or reporting verb from a different fact or narrator; keep the sentence unchanged when the boundary or subject cannot be resolved safely. Treating every comma as a boundary is not acceptable (numbers, parentheticals, valid clauses): bounded recognition with a conservative fallback.

### P2: location repair changes what a negation denies

| Input | Output at `91a9071` |
|---|---|
| "The company does not state that the figures appear on the same slide [S2, S3]." | "The company does not state 500M messages with no explicit interval [S2] on page 10, … [S3] on page 12 (…)." The negation's object changes from a common-slide attribution to the admitted metrics |

**Required:** preserve this sentence and comparable denials/qualifications; restrict reconstruction to an affirmative source-location assertion whose subject, predicate and scope are known; keep the memo-99 affirmative corrections.

## Follow-up requested

1. Record this review additively (this file).
2. Red regressions first for the funding/narrator probe, the two revenue probes and the negated-placement probe, with full guard-sequence and memo-writer coverage for the funding/narrator example.
3. Bound reconstruction to its own clause and reporting subject; preserve the sentence when ambiguous. No dropped citations, no generic narrator for the whole sentence, no extra model call.
4. Assert unrelated prefixes/suffixes and citations stay intact; each emitted fact keeps its narrator, metric, basis, page and context; include different narrators on either side of a comma and a valid negated common-slide statement.
5. Keep memo 99's three repaired sections and unchanged other fields, memo 98's accepted corrections, the denial/condition controls, interleaved order, item/note-order stability and second-pass idempotence.
6. Focused mutations removing the clause/narrator boundary and negating the reconstruction guard; affected checks and established batches sequentially with the watchdog; SHAs, commands, outputs and restore/hash checks in a new additive folder.
7. Push application and evidence commits separately; leave the branch unmerged. No historical memo regeneration, frozen-artifact edits, live generation, deployment or paid-source Pass B.

## Reviewer's verification limits and status

The 1,378 passing tests and 49/49 mutations were not independently rerun; no live model call, browser session, production access, application edit, merge or deployment by the reviewer. RA-109 live acceptance, RA-108 and overall hardening remain open; RA-106's prior scoped acceptance is unchanged.
