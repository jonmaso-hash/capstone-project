# Next live validation, revision 2: RA-114 after the retrieval and panel changes (prepared, not run)

This file **revises** two earlier procedures:
- `1aab9e3`'s procedure, `docs/baselines/three-deck-audit/output-f1-f2-post-merge-b278364/NEXT_LIVE_VALIDATION.md`;
- revision 1, `6917e84`'s `docs/baselines/three-deck-audit/output-ra114-ask-document-e4d17d7/NEXT_LIVE_VALIDATION_REV_RA114.md`.

Neither file is edited. Everything they say still applies unless this file changes it, including:
- the preconditions, isolation, memory limits and browser gate;
- the F-1, F-2 and regression criteria;
- F-2's **"not exercised"** outcome;
- revision 1's RA-114 criteria 1–7, its authorization probe, and its per-question grounding table.

**When to run it:**
- only after `fix/ask-document-routing-ra114` has been independently reviewed and merged, with the post-merge byte check repeated at the merge commit;
- with an explicit owner go-ahead, because it makes model calls and starts the worker.

## What changes from revision 1

1. **The ranking now differs, so the offline prediction is replaced** (below). The criteria themselves are unchanged. None is loosened to fit the new prediction, and none is tightened after the fact.
2. **One unrelated-question control, through the document form** (0 model calls): `{"q": "What is the weather in Paris?", "document_id": <run doc>}`, sent as the owner.
   - **Pass:** 200 and `no_relevant_evidence` true.
   - **Fail:** any evidence.
3. **A panel check of the document form** (0 model calls), in the established browser, as the owner. The steps:
   1. Open Library, then "Ask about this document" on the run's document. The button appears once the document is analyzed and has its memo.
   2. Check that the context bar names it.
   3. Ask Q1 in the panel.
4. **The panel's marketplace form is not sent live.** It would make a ninth model call. It is covered offline by this folder's walk (`output/panel_walk/walk.json`): with no document chosen, the panel sent `{q}`; after clearing the document context it sent `{q}` again; a stranger who forced a document context got 403.

## Call budget (unchanged ceiling)

| Step | Expected calls |
|---|---|
| Memo | 1 |
| Q1–Q7, marketplace form (API) | 7 (query extraction, once each) |
| Q1–Q7, document form (API) | **0** |
| Unrelated-question control, authorization probe, panel document check | **0** |
| Browser checks, replays, restarts | 0 |
| **Ceiling** | **8. No retries.** A 9th attempted call fails the run |

Revision 1's ledger checkpoints stay. One more is added: the ledger's line count and SHA-256 immediately before and after the panel document check. **Any new line there fails RA-114 and the run.**

## Panel check criteria (RA-114)

All must hold:
- **The request:** the panel's `/ask/` request body, from the browser's network log or the server request log, is exactly `{"q": <Q1>, "document_id": <run doc>}`.
- **The response:** it meets revision 1's criteria 1–6 for Q1.
- **What the panel shows:** the quoted passages with their pages, and no marketplace cards.
- **The context can be cleared:** after "Ask the marketplace instead", the context bar is gone. This is checked without sending a question.
- **0 model calls** (ledger unchanged).

## Excerpts are not a pass by themselves

Criteria 1–7 establish that the answer comes from the document, unmodified and uncomposed. **Grounding is graded separately, per question, against the frozen answer key** (revision 1's table; `docs/baselines/manychat/ANSWER_KEY.md`, "Fixed questions"). A question whose excerpts miss its required passage fails, however clean the response is. The grader records two things for each question:
- the evidence pages, in order;
- whether the required passage is among them.

## Offline prediction (memo 104's own chunks; not a live result)

`output/rank_replay_after_9ee8d3d.json` replays Q1–Q7 at `9ee8d3d` on memo 104's 12 recorded chunks:
- in a throwaway test database;
- with production-shaped vectors;
- with a second document that says "users", "raised" and "Traction" outright.

`output/rank_replay_before_e4d17d7.json` is the same replay at `e4d17d7`. If the live deck chunks the same way:

| Q | Pages at `e4d17d7` | Pages at `9ee8d3d` | Grounding criterion (revision 1) | Predicted |
|---|---|---|---|---|
| Q1 | 2, 1, 3, 4, 5 | **2** | includes page 2 ($23.1M) | pass |
| Q2 | 1, 2, 3, 4, 5 | **10** | includes page 10 (140,000+ bots); no user count stated | **pass** (was fail) |
| Q3 | 10, 12, 1, 2, 3 | **10, 12** | includes pages 10 and 12 | pass |
| Q4 | 2, 1, 3, 4, 5 | **none** (`no_relevant_evidence` true) | nothing about SEC outside an excerpt | pass |
| Q5 | 2, 1, 3, 4, 5 | **2** | no revenue figure outside an excerpt | pass. Page 2 is reached on "current" and states no revenue (recorded for the grader) |
| Q6 | 1, 2, 3, 4, 5 | **2, 1** | includes page 2 (2015 Series A); no year outside an excerpt | pass |
| Q7 | 1, 2, 3, 4, 5 | **none** (`no_relevant_evidence` true) | no advice | pass |

**Limits of this prediction:**
- It holds only if the live run's chunks match memo 104's. A different chunking or extraction changes it, and the live result decides.
- Q2 reaches page 10 because of the topic rule. The deck puts "Traction" on page 10, and the pre-existing traction vocabulary lists "users". This is general pitch-deck vocabulary, not a rule about this deck. A deck with no "Traction" heading and no "users" would still return nothing for Q2, and `no_relevant_evidence` would say so.
- Excerpts are the deck's own words. Page 10 says bots, not users. The grader checks that no user count appears outside the excerpt.

**Outcome for RA-114:** unchanged from revision 1. A run meeting every criterion is proposed to the grader as RA-114 live evidence. It does not close RA-114 by itself, and it does not close RA-108, RA-109, Q-2–Q-4 or overall acceptance.
