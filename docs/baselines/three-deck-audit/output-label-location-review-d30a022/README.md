# Review of the OF-704 / OF-705 correction at `d30a022`: changes required

**Additive.** This records the independent review of `fix/basis-label-source-context`. It changes nothing in `output-label-location-620cefa/`, the memo-99 run evidence or grade, any historical memo, frozen fixture, ledger or earlier accepted correction. The branch stays unmerged.

| Item | Value |
|---|---|
| Application commit | `979bf493d0a3b199d5819c1db0ed69e5ebf65d1f` |
| Tests-only follow-up | `620cefa` |
| Evidence head | `d30a022bfd87de8c4ecc5a3b9378de9da42876ec` |
| `zelda_api/basis_fidelity.py` blob at review | `564fa907010da63b395da750dd5ddb4eed3200e3` |

## Reviewer's independent checks and limits

**What the reviewer ran:**
- **Sources:** retrieved the implementation, tests, supporting pure modules and the memo-98/99 fixtures through GitHub.
- **Helper tests:** ran 77 helper test methods with unittest adapters, using the production helper bodies and fixtures unchanged. Database-backed classes were excluded.
- **Replay:** the memo-99 raw reply through list normalisation, time, funding and basis guards. The three proposed changed sections reproduce the committed expectations.
- **Probes:** ran additional probes against the unchanged helper. The findings below are observed outputs.

**Not rerun:** the Django writer/database tests, the full 1,372-test batch, the mutation campaign, a browser session or live generation.

## Findings

1. **P2 — OF-705 still does not pair each fact with its own basis and page.**
   - **`business_model_analysis` replay:** "the company states 140,000+ bots and 500M messages (measurement basis questioned; see open concerns) on page 10 (slide headed 'Traction by Apr-16') [S1, S2] and page 12 [S3]". The shared metric predicate remains: the monthly rate is not stated under S3, and the text reads as though the grouped figures occur on both pages.
   - **`supported_points` replay:** it keeps the alternative-form framing ("either 500M with no stated interval or 500M/month … on page 10 … [S2] and page 12 [S3]").
   - **Required:** bounded fact-specific clauses from normalised items and source metadata. Page 10 reports 140,000+ bots [S1] and 500M messages with no explicit interval [S2], under 'Traction by Apr-16'; page 12 separately reports 500M messages/month [S3]. The relation stays a clarification question, with no transfer of bots or the dated heading to page 12 and no invented cumulative reading.
   - **Tests:** `test_every_placed_citation_supports_its_page_and_context` checks only page/context tuples, not the metric and basis attached to each citation, and the exact-string expectations encode the incomplete repair.
2. **P2 — the label rule changes valid denials and evidence qualifications.**
   - "The messages cannot establish a contradiction [C3, C2]." became "… cannot establish an ambiguity …".
   - "… provide insufficient evidence to establish a contradiction [C3, C2]." became "… an ambiguity …".
   - Both recorded `basis_contradiction_label`.
   - **Required:** act only on an unsupported affirmative classification; keep denials, inability and insufficient-evidence qualifications.
3. **P2 — the new rules rewrite valid conditional scenarios.**
   - "If the message figures are contradictory [C3, C2], management should explain the difference." became "… are ambiguous …".
   - "If 500M total is the correct interpretation [S2, S3], …" became "If 500M with no stated interval is …".
   - **Required:** keep valid conditional statements for the new label/total/location rules, without a blanket "if" exemption that would regress the accepted memo-98 correction.
4. **Citation order.** "The figures appear on the same slide [S1, S3, S2]." became "… page 10 (…) [S1, S2] and page 12 [S3]", reordering refs S1, S3, S2 to S1, S2, S3.
   - **Cause:** `_location` grouped non-adjacent refs in a dictionary.
   - **Required:** keep the flattened ref order (group only adjacent refs, or emit each ref with its own clause), with an interleaved-location regression.

## Status

- **RA-109:** live output acceptance remains open.
- **RA-106:** its prior scoped acceptance is unchanged.
- **Still open:** RA-108, the separately recorded P3 items and overall hardening.
- **Follow-up:** work on the same branch; failing regressions first; bounded repairs from normalised items, notes and source metadata; no live generation, historical regeneration, frozen-evidence edits, deployment or paid-source Pass B.
