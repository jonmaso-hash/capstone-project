# Independent grade — ManyChat memo 98 (document 3140)

**Reviewed:** 2026-10-15 (America/Tijuana). **Additive:** this file changes nothing in [RERUN_LEDGER.md](RERUN_LEDGER.md), the run's artifacts, memo 98, memo 97, any earlier run, frozen key, protocol or accepted grade.

## Decision: PARTIAL PASS

**Pass:**
- extraction;
- distinct measurement bases;
- the normalised clarification note;
- live detection;
- delivery on Truth Delta;
- verification and permission boundaries.

**RA-109 live output acceptance stays OPEN.** The generated memo adds an unsupported cumulative basis and an overstatement premise. Separate funding-source and funding-as-cash wording also needs correction.

The deterministic code review stays valid. This live sample exposes a generation/output gap that the code review did not establish as solved.

| Item | Value |
|---|---|
| Application code | `d276918cb0e1a4e7fa109a86c5e9336ef180f9a3` (merge of PR #283) |
| Evidence | `0dd8e91c06b69f3761eb76cd8e20c497a3a6e310` on `docs/manychat-usage-basis-d276918` |
| Rows | Document 3140; claims 2369–2372; Entity Integrity 39; Truth Delta 92; memo 98 |
| Live generations | One memo generation plus seven Ask Zelda probe calls: eight calls in all |

## Accepted results

- **Claims:** four, including page-10 `140 000+ bots`, page-10 `500M messages` and page-12 `500M messages/month`, with correct values, pages and distinct units. The monthly rate has no invented period-end date, and no platform-user claim was recovered.
- **Model input:** the request equals the committed rebuilt payload. It contains the neutral note with refs C3/C2 and prompt rule 11. Funding C1/S4 is narrated by Pitch Deck Hunt, and the usage refs stay separate. No canary or profile funding amount is in the input.
- **Detection:** the model identified the measurement-basis issue itself in seven sections, and the stored memo preserves them. No output guard created that detection.
- **Truth Delta:** zero observations, four INSUFFICIENT, zero verified, zero contradicted, no score. Its note says it is not a verification result and does not affect the score. It is visible to the principals entitled to that page.
- **Replay:** all 17 stored fields match an independent replay through the actual normalisation, time and funding guards. Reversed context gives the same output, a second pass changes nothing, and citations are preserved. There were only two funding-attribution edits (`open_concerns`, `questions_for_management`).
- **Funding attribution:** the 39/39 amount-sentence attribution count is correct across the 51 surfaces. It establishes that the narrator is named; it does not establish that every clause is attributed correctly.
- **Other checks:**
  - Markdown bytes/hash, UTF-8 header and decoding, lists and counts are consistent.
  - Q3's top search pages are 10 and 12.
  - The 90 authorization rows match memo 97 on status, panel and canary.
  - Reconciliation is owner-only.
  - The canary stays on the owner's and staff's profile surfaces only.

## Grading decisions

| ID | Decision |
|---|---|
| **UB-604** | **P2, blocks RA-109 live acceptance.** `risk_assessment` 1: "If the cumulative figure is being presented as a monthly figure, the key traction claim is materially overstated." The preceding sentences correctly say page 10 has no explicit interval. This sentence then calls it *the cumulative figure* as if that were established, and "materially overstated" adds an error judgment the two bounded facts cannot support. Rule 11 already forbids that. The raw reply contains it and the stored memo keeps it. The hypothetical scenarios and the management question that ask whether the figure is cumulative state uncertainty and should be preserved. `information_readiness` "cumulative vs. monthly" and `open_concerns` "inconsistency" are P3 clarity issues. **Required:** state the two actual bases and ask how they relate, with their real refs. Do not promote an unspecified interval to cumulative, or infer overstatement from matching numbers alone. Preserve explicit cumulative evidence when it exists, and properly qualified questions and scenarios |
| **NP-603** | **P2, funding source ownership blurred.** `supported_points` adds "total amount raised", then credits "the fundraising narrative the company has put forward". Only Pitch Deck Hunt narrates C1/S4, and "total" asserts an unstated aggregation basis. This does **not** assert a current total (the memo says no date is stated and calls the figure historical), so RA-106's scoped acceptance stays intact. **Required:** keep the narrative assigned to its narrator; no unsupported total; no transfer to the company. Preserve the company's genuine bot/message statements |
| **NP-604** | **P2 for the funding-to-operating-cash link; P3 otherwise.** `what_would_change_the_picture`: "how long the company can operate on the capital narrated as raised [S4]". The management question: "runway against the $23.1M … narrated as raised [S4]". Historical funding is not the operating cash balance. Naming the narrator does not repair the link, and the current guard leaves these clauses unchanged. The run has no numeric runway or asserted balance, and the financial analysis disclaims cash and runway; these limit the failure but do not fix it. "May have been consumed" and "has been deployed" are statements of missing information (P3), as is the duplicated narrator phrase. **Required:** questions may request dated cash and burn and ask what runway they support, and may separately ask whether the funding occurred, when, and how confirmed proceeds were used. Never use the historical funding amount as the cash/runway denominator |
| **UB-605** | RA-108 recurrence. The note is credited to a "verification process" and compared with an unmeasured plain AI summary. No state or score was manufactured. Kept separate from the focused correction |
| **UB-606** | P3 surface coverage. The Lite/paid overview omits the monthly figure and the note; their Truth Delta page and the Lite memo API carry them. It does not independently block acceptance |
| **UB-607 / UB-608** | P3. Prefer the admitted metric wording to "deployed"/"processed". The Facebook Messenger example is in a question; the name is in the original deck but absent from the admitted items. Record it as a normalised-input boundary wording issue; this run does not prove where the model got it |
| Other | No buy/sell/hold recommendation in the memo (the scanner's "Buy" hits are credit-pack UI text). P3 basis-note rounding and NP-508/509 stay separate |

## Independent verification by the reviewer

The immutable evidence commit was retrieved directly. Its 68 added files are confined to the new run folder.
- **Artifacts:** of 46 non-image, non-script artifacts, 44 match their Git blobs exactly, including the raw reply, stored memo, payload, Markdown, matrices and snapshots. `worker.log.txt` and `probe_stdout.txt` were read as decoded text; no exact-byte claim is made for them.
- **Replay inputs:** the three replay helper sources match merged-code blobs.

| Check | Result |
|---|---|
| Sent request vs rebuilt payload | Equal, including the C3/C2 note |
| Raw reply → list/time/funding replay | All 17 stored fields match |
| Reversed context / second pass / citations | Stable / unchanged / preserved |
| Guard changes | Two `attribution:Pitch Deck Hunt` edits only |
| Claims | Four expected; count and rate distinct |
| Observations and score | None; no score; four `no_data` |
| Markdown | 11,774 bytes; SHA-256 `079d9c8d94a8a78fba23e12e53847e939c1f9f247321d5f9e60c3ba712d403c3`; strict UTF-8; 18 bullets, 20 em dashes |
| Five snapshot pairs | Byte-identical within the run |
| Historical comparison | Original/94/95/96 match the memo-97 run snapshots after omitting `Invalid line` warnings and normalising line endings, as the ledger states |
| Memo-97 field comparison | The run records 24 fields with no differences, before and after (the reviewer did not reopen that DB) |
| DB hashes / process gates | Recorded pairs match; isolated copy, local broker, pending=0, six paid keys false, Anthropic present |
| Authorization | 90 rows match memo 97; owner-only reconciliation |
| Funding sentences | Recomputed 39/39 with narrator across 51 surfaces |
| Q3 search | Top two pages 10 and 12 |
| Model calls | Eight, one memo generation |

**Not repeated by the reviewer:** a fresh DB-backed `GroundedContext.build`, the provider call, the browser walks, and inspection of the JPEGs. No retry, suite, mutation, production access, regeneration, deployment or Pass B was run.

The sentence scan is a triage aid. Some inherited ref patterns use the older mapping (S3 for funding), whereas this run uses S4 for funding and S3 for the rate. The grade uses the actual mapping from the payload, and the 39/39 count is unaffected.

## Status

- **RA-109:** extraction, normalisation and live detection are **accepted**. RA-109 live **output** acceptance stays **OPEN** (UB-604).
- **RA-106:** the memo-97 scoped acceptance is not revoked. NP-603 and NP-604 are recorded for future-output correction.
- **Still open:** RA-108 and overall Zelda hardening.
- **Memos:** memo 98, memo 97 and all earlier memos stay as generated.
- **Focused next step:** a new application branch from `d276918` correcting UB-604, NP-603 and the funding-as-runway part of NP-604, using deterministic regressions on this run's normalised facts and no new live generation.
