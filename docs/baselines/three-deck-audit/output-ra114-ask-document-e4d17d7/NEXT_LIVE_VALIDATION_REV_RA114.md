# Next live validation, revision 1: RA-114 criteria (prepared, not run)

This file **revises** the procedure committed at `1aab9e3`, `docs/baselines/three-deck-audit/output-f1-f2-post-merge-b278364/NEXT_LIVE_VALIDATION.md`.
- **What stays the same:** everything in that procedure that this file does not change, including:
  - the preconditions and isolation;
  - the memory limits and the browser gate;
  - the F-1, F-2 and regression criteria;
  - F-2's **"not exercised"** outcome.

  That file is not edited.
- **When to run it:** only after the RA-114 fix (`fix/ask-document-routing-ra114`) has been independently reviewed and merged, with the post-merge byte check repeated at the new merge commit.
- **What it needs:** an explicit owner go-ahead, because it makes model calls and starts the worker.

## What changes

1. **Q1–Q7 are asked twice through `/api/v1/zelda/ask/`, as the owner:**
   - **Document form:** `{"q": <question>, "document_id": <the run's new document>}`. This is the RA-114 path. It makes **no model call**: no query extraction and no generation.
   - **Marketplace form:** `{"q": <question>}`, exactly as in every earlier run. This is the marketplace control and keeps the runs comparable. It makes one query-extraction call per question.
2. **Authorization probe of the document form:** Q1 with the run's `document_id`, sent as the Lite, paid and an unrelated investor account by the HTTP probe. It makes 0 model calls.
3. **The `/search/` and `/rag/` probes stay as before.** The document form's evidence is compared with `/search/` for the same question.

## Call budget (unchanged ceiling)

| Step | Expected calls |
|---|---|
| Memo | 1 |
| Q1–Q7, marketplace form | 7 (query extraction, once each) |
| Q1–Q7, document form | **0** |
| Authorization probe, browser checks, replays, restarts | 0 |
| **Ceiling** | **8. No retries.** A 9th attempted call fails the run |

The call ledger's line count and SHA-256 are recorded at four points:
- immediately before and after the seven document-form questions, where any new line fails RA-114 and the run;
- before the upload;
- after the marketplace questions;
- at the end.

## RA-114 pass / fail criteria (document form)

**Every question must meet all of these.** Any miss fails RA-114 for the run:
1. HTTP 200, `status` `success`, `document_id` equal to the run's document, and `results` an empty list (no marketplace cards).
2. The response is **not** the marketplace fallback ("I couldn't find specific search criteria …").
3. **Grounded:** every `evidence` item's `chunk_id` belongs to the run's document. Its `page` equals that chunk's page, and its `text` equals that chunk's text byte for byte. This is checked read-only against the run's DB copy.
4. **Same retrieval as `/search/`:** the `evidence` list (ids, pages, text, relevance, in order) equals `/search/`'s `results` for the same question and document.
5. **Insufficient evidence said outright:** `no_relevant_evidence` is true exactly when `evidence` is empty, and the response then reads "No relevant evidence was found in this document for that question."
6. **Nothing composed:** the response text is the fixed excerpt or no-evidence sentence. It contains no figure, year, name, SEC statement or advice. Any fact appears only inside a verbatim excerpt.
7. **0 model calls** across the seven document-form questions (ledger unchanged).

**Authorization.** All must hold, or RA-114 fails:
- Lite, paid and the unrelated investor each get **403** with no document text in the body;
- the owner gets 200;
- no extraction is attempted.

**Per-question grounding**, against the frozen answer key (`docs/baselines/manychat/ANSWER_KEY.md`, "Fixed questions"):

| Q | Pass | Fail |
|---|---|---|
| Q1 raised | evidence includes the chunk stating "$23.1M raised" (page 2) | it does not |
| Q2 users | evidence includes the page-10 traction chunk (140,000+ bots), and the response states no user count | missing, or a user count stated outside an excerpt |
| Q3 messages | evidence includes **both** page 10's 500M messages and page 12's 500M messages/month | either page missing |
| Q4 SEC | the response says nothing about SEC registration. Either `no_relevant_evidence` is true, or the excerpts are verbatim deck text | any SEC or CIK statement outside an excerpt |
| Q5 revenue | no revenue figure outside an excerpt; ideally `no_relevant_evidence` | a revenue figure composed in the response |
| Q6 Series A date | evidence includes the page-2 chunk (2015 Series A); no year outside an excerpt | missing, or a year stated outside an excerpt (the 2019 inference leak) |
| Q7 invest? | no advice in the response; verbatim excerpts or no evidence | any advice wording |

**Recorded, not RA-114 failures:**
- **Ranking quality:** ties, near-uniform relevance, and `no_relevant_evidence` false for Q4 or Q5 because the company name matches every chunk. This is the known retrieval gap (L-002 / L-013, Phase 1 known gap 3), recorded for the grader.
- **Marketplace form:** the fallback for Q1–Q7 is the expected, unchanged marketplace behavior. It is the control, not an RA-114 result. A marketplace answer that changes from earlier runs is recorded and investigated.
- **The panel's Ask tab** sends no `document_id` (`templates/includes/zelda_ai_assistant_enhanced.html`). The browser surface therefore does not exercise RA-114, and the run checks it at the API. Wiring the panel to the document form is a separate, owner-scoped item.

**Outcome for RA-114:** a run meeting every criterion above is proposed to the grader as RA-114 live evidence. It does not close RA-114 by itself, and it does not close RA-108, RA-109, Q-2–Q-4 or overall acceptance.

## Offline prediction (from memo 104's own chunks; not a live result)

`output/replay_after_e4d17d7.json` replays Q1–Q7 at `e4d17d7` on memo 104's 12 recorded chunks, in a throwaway test database. The replay is faithful to the live run: its `/search/` ranks equal the ones memo 104's run recorded for all seven questions, and the marketplace form's body equals the recorded one byte for byte. If the live deck chunks the same way, the criteria above predict:

| Q | Evidence pages (in order) | Predicted |
|---|---|---|
| Q1 | 2, 1, 3, 4, 5 | pass: page 2 ($23.1M) is first |
| Q2 | 1, 2, 3, 4, 5 | **fail**: page 10 is not reached. The deck never says "users", so only "ManyChat" matches, and every chunk ties |
| Q3 | 10, 12, 1, 2, 3 | pass: both pages |
| Q4 | 2, 1, 3, 4, 5 | pass (nothing composed); `no_relevant_evidence` false (recorded) |
| Q5 | 2, 1, 3, 4, 5 | pass (nothing composed); `no_relevant_evidence` false (recorded) |
| Q6 | 1, 2, 3, 4, 5 | pass: page 2 is included |
| Q7 | 1, 2, 3, 4, 5 | pass (no advice) |

**So, on current retrieval, RA-114 is predicted to fail live on Q2's grounding.** The fix removes the routing cause of the marketplace fallback. Whether the right page is reached depends on retrieval ranking, which is the known gap L-002 / L-013, not part of this fix. The Q2 criterion stays as written. It is not weakened to fit the prediction. Whether to run before improving retrieval is an owner decision.
