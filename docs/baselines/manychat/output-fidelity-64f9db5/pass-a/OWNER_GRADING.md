# Independent grade — ManyChat memo 99 (document 3141), after PR #284

**Additive:** this file changes nothing in [RERUN_LEDGER.md](RERUN_LEDGER.md), the run's artifacts, memo 99, memo 98, memo 97, any earlier run, the frozen key, protocols or accepted grades. The deterministic correction accepted in PR #284 is not reversed by this grade; this live sample exposes additional output shapes within the existing measurement-basis and source-context requirements.

## Decision: PARTIAL PASS

**Pass:**
- **NP-604 funding as runway:** corrected live.
- **Recurrence:** the previously reviewed shapes did not recur: the cumulative/overstatement wording (UB-604) and, in statements, the funding total and company-owned narrative (NP-603).

**RA-109 live output acceptance stays OPEN.** Two P2 errors remain in the newly generated output:
- **OF-704:** an unsupported contradiction label;
- **OF-705:** incorrect shared-slide attribution.

| Item | Value |
|---|---|
| Code | `64f9db5286213e9d7f38dce6aab170bd26a15cc2`, merge of PR #284 |
| Evidence | `d821cca1ab345d2a63d28fb0236b7ca3bce033ee` on `docs/manychat-output-fidelity-64f9db5` |
| Folder | `docs/baselines/manychat/output-fidelity-64f9db5/pass-a/` |
| New rows | Document 3141; claims 2373–2376; Entity Integrity 40; Truth Delta 93; memo 99 |
| Calls | One memo generation plus seven Ask Zelda query-extraction calls; eight in all |

## Accepted results

- **Claims:** the four expected claims survive.
  - Page 10 has 140,000 bots and 500M messages with no explicit interval; page 12 has 500M messages/month.
  - Units, values, pages and chunk hashes match the prior run.
  - No platform-user claim or invented rate period-end appears.
- **Payload:** the sent payload equals the committed rebuilt context, and, excluding source `document_id`, memo 98's payload. The C3/C2 note correctly asks for clarification; the funding narrator and usage sources stay distinct.
- **UB-604:** the old "the cumulative figure … materially overstated" shape does not recur. The basis guard makes zero edits. This is non-recurrence in one sample, not a demonstrated live correction by that guard.
- **NP-603:** the unsupported "total amount raised" statement and the company-owned fundraising narrative do not recur in statements. The model explicitly distinguishes Pitch Deck Hunt from the company's own slide text.
- **NP-604, corrected live:**
  - **Runway clause:** the raw reply says "how long the company can operate on its reported funding [S4]"; the stored reply separates historical funding from the dated cash/burn basis.
  - **"Remaining runway":** the separate raw wording gains the missing cash/burn qualification.
  - **Replay:** both edits replay independently.
- **Truth Delta:** zero external observations, four INSUFFICIENT (`no_data`) claims and no score. The internal note creates no machine contradiction or verification result and is visible to authorised owner, Lite, paid and staff readers.
- **Replay:** all 17 stored fields match the actual normalisation → time → funding → basis replay, including reversed-item stability, idempotence and citation-sequence preservation.
- **Funding sentences:** all 49 sentences stating the funding amount across 51 captured surfaces name Pitch Deck Hunt. The count is independently reproduced; clause meaning is graded separately below.
- **Other checks:** UTF-8 Markdown, counts/lists, the 90-row authorisation comparison, owner-only reconciliation, canary boundaries and preservation records pass the checks below.

## OF-704 — P2: an ambiguity is labelled a contradiction

`open_concerns` begins:

> Measurement-basis contradiction in the headline usage metric: the deck states '500M messages' without an interval on page 10 and '500M messages/month' on page 12 [C2, C3].

The next sentence says the two are not necessarily the same figure and asks management to clarify. That qualification is useful, but the heading has already classified the relationship as a contradiction. The admitted facts and normalised note support measurement-basis ambiguity and clarification, not a contradiction: both figures could be true under different windows or definitions.

**Where it appears:** the label is present in the raw reply and survives unchanged in:
- the stored memo;
- the Lite memo sections;
- the staff memo and overview;
- the Markdown export.

The staff overview repeats it in "Worth investigating" beside zero machine contradictions. This is a narrative grounding error; it did not change Truth Delta's state or score.

The guard's lexical judgment list does not cover "contradiction", so the new live shape reaches readers despite prompt rule 11. This is a P2 within the existing RA-109 acceptance condition, not a stylistic preference for a different heading.

**Required behaviour:** when this admitted measurement-basis pair is the only support, label it an ambiguity or clarification question and keep the actual facts and refs. Preserve legitimate external contradictions and unrelated metrics, and never rewrite a statement saying there is no contradiction into an assertion of one. Keep the accepted pair-resolution and bridge-containment rules.

The `zelda_advantage` phrase "internal inconsistency" is less precise, but it also calls the issue a measurement-basis ambiguity. Its unmeasured plain-AI comparison remains RA-108, separate from this correction.

## OF-705 — P2: different source pages presented as one dated slide

`supported_points` says:

> The company states a messages figure of either 500M total or 500M/month (measurement basis unresolved; see open concerns) on the same traction slide [S2, S3] …

**What the payload shows:** S2 is on page 10, with `source_context: Traction by Apr-16`; S3 is on page 12, with no such context. They are two admitted statements from different pages, not alternative forms of one statement on the same slide.

**The wording blurs it further:** "either …/total" hides the known source distinction. The page-10 interval is unspecified; page 12 explicitly states a monthly rate.

**A second section:** `business_model_analysis` cites [S1, S2, S3] for metrics said to be on a slide headed "Traction by Apr-16". S1 and S2 support that context; S3 does not. Other sections correctly place the rate elsewhere / on page 12, which confirms this is an output inconsistency rather than missing source metadata.

This is a source-location and context error, not just a mistyped citation. It moves the monthly-rate source into the dated page-10 block and defeats the distinction RA-109 was meant to preserve. Preserving citation tokens does not preserve attribution meaning.

**Required behaviour:** keep each fact paired with its actual source page and its own context.
- **Allowed:** page-10 bots and messages may share the traction heading.
- **Separate source:** the page-12 monthly rate must stay separately sourced.
- **No promotion:** an unspecified interval must not become a stated total.
- **Repair options:** split the affected clause into accurately sourced facts, or use neutral wording.
- **Never:** invent a new date, unit, page or event, or silently discard the rate or its ref.
- **Inputs:** use normalised item and source metadata only, without bringing raw chunks, key prose or grading hints into generation.

## Remaining notes — separate from the two P2 corrections

| Item | Grade |
|---|---|
| OF-706: a management question asks what rounds make up "this total" | P3 presupposition/clarity. It asks rather than asserts an amount, date or current balance; prefer asking whether the reported amount is an aggregate and, if so, what it includes. Do not reopen a broad funding-total redesign in this focused correction |
| OF-706: "its reported funding" after the guard | P3 source continuity. The S4 citation maps to Pitch Deck Hunt and the sentence expressly denies cash equivalence; the standalone clause would be clearer naming the narrator. The reviewed company-narrative statement defect did not recur |
| Doubled parentheticals / conditional deployment speculation | P3 wording. No received/available balance or numeric runway is established. Keep historical evidence intact |
| OF-709: Lite/paid overview says "see open concerns" but does not show that section | P3 surface coverage/navigation. The summary now signals the basis question, and Truth Delta exposes the note to entitled readers. Separate from the P2 source error above |
| OF-711 | RA-108 OPEN. "Structured extraction" is a more accurate attribution than "verification process", but the plain-AI comparison remains unmeasured |
| OF-712: chatbot/messaging product category | P3 inference/source clarity. The problem section labels the inference; the executive summary states it more directly. Not part of this pair/source correction |

RA-103 audit framing, FF-413 styling, RA-114 Ask Zelda, RA-105 currency, PF-206/FF-311 coverage, NP-508/509 and P3 note rounding stay as separately recorded. They are not closed by a passing layer in this sample.

## Independent verification by the reviewer

The immutable evidence commit adds 82 files confined to the new run folder.
- **Artifacts:** 54 non-image, non-script artifacts were retrieved, and all match their Git blob hashes exactly, including the captured payload and reply, stored memo, Markdown, snapshots, matrices and relevant process logs. Binary text-log encodings were accounted for when checking original bytes.
- **Replay source:** the merged helper source already pinned in the accepted PR #284 review was used for replay; the merge tree equals that reviewed head.

| Check | Independent result |
|---|---|
| Sent payload vs rebuilt artifact | Equal; C3/C2 neutral note present |
| Payload vs memo 98 | Equal after excluding source document IDs |
| Full four-step replay | All 17 stored fields match |
| Reversed items / second pass / refs | Same output and edits / unchanged, no further edits / citation sequence preserved |
| Actual edits | `cash_premise`; `funding_not_runway`; three `attribution:Pitch Deck Hunt` edits |
| Basis / narrator-provenance / unsupported-total rules | No live edit in this sample |
| Claims / states | Four expected units/pages; no invented period end; zero observations; four `no_data`; score None |
| Markdown | 11,755 bytes; SHA-256 `58e596bf121955c9a14179970213485cbd50dd19c5c3ec0c6143dd95a99194b5`; strict UTF-8; 20 bullets, 22 em dashes |
| Six before/after snapshot pairs | Original, memos 94, 95, 96, 97 and 98 byte-identical within this run |
| Older committed snapshot comparison | Original/94/95/96/97 match the memo-98 run snapshots after the documented startup-warning removal and line-ending normalisation |
| DB hashes and process records | All recorded source hash pairs match; server/worker show the local isolated copy, pending=0, paid-provider keys false and Anthropic present |
| Memo-97/98 field comparisons | Records show 24 fields with no differences before and after; the reviewer did not reopen those SQLite DBs |
| Authorisation | All 90 status/panel/canary rows match memo 98; reconciliation owner-only; canary only on the owner/staff profile |
| Funding sentences | 49/49 name Pitch Deck Hunt across 51 captured surfaces |
| Q3 retrieval | Top two pages 10 and 12 |
| Calls | Eight captured calls; one memo generation |
| Browser supporting records | Five principal walks, direct staff verification route, MFA and logout in DOM/server-log records |
| New P2 passages | Reproduced from the raw reply through unchanged stored output; contradiction label confirmed on the staff overview; source pages independently checked in the payload |

**Not repeated by the reviewer:** a fresh database-backed context build, model call, suite, mutation campaign or browser session.
- **Browser conclusions:** they rely on recorded DOM/rendered text and server logs; the JPEG screenshots were not independently inspected.
- **Not done:** no production access, memo regeneration, deployment or Pass B occurred during this grade.

The run is valid evidence of a partial pass. These output errors did not invalidate isolation or justify repairs during the measured run.

## Status

- **Deterministic corrections:** the prior ones stay accepted.
- **NP-604:** its focused live correction is demonstrated.
- **UB-604 and NP-603:** the former statement shapes did not recur.
- **RA-109:** live output acceptance stays **OPEN** for OF-704 and OF-705.
- **RA-106:** its earlier scoped acceptance is unchanged.
- **Still open:** RA-108 and overall Zelda hardening.
- **Focused next step:** a correction branch from `64f9db5` scoped to OF-704 and OF-705 only, with failing regressions from the actual memo-99 reply and normalised payload first, and no new live generation during correction and review.
