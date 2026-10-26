# RA-114: document questions sent to Ask Zelda got the marketplace fallback (offline fix at e4d17d7)

This folder adds evidence for branch `fix/ask-document-routing-ra114`.
- **Earlier evidence is unchanged:** memo 104's run (`f73bef5`), the F-1/F-2 folders and the post-merge verification (`1aab9e3`).
- **Nothing else was touched:**
  - no model was called;
  - no application database or MFA was changed; tests and the replay used the throwaway test database only;
  - the worker was not started, and nothing was merged or deployed.
- **Status:** all validation is my own, pending independent review. This offline fix **does not close RA-114**, which needs a live run and grading. RA-108, RA-109, Q-2–Q-4 and overall acceptance also remain open.

| Item | Value |
|---|---|
| Execution SHA | `e4d17d768f488a03468ae9e35ce825667e85c800` (fix and tests). **Validation head** |
| Base | `b27836439ca0e6aa9acc1ca6feaeae1be80b6415` (`origin/main`, the PR #290 merge). Main has not moved |
| Changed files | `zelda_api/views.py` +59 (`ZeldaAskAPIView`); `zelda_api/tests_ask_document.py` +171 (new) ([output/commit_and_hashes.txt](output/commit_and_hashes.txt)) |
| Untouched | every output guard. `basis_fidelity.py`, `funding_fidelity.py` and the fidelity tests are the same blobs as at `b278364` |

## The finding

- **First recorded:** RA-114 was first recorded at `5655d331` (ManyChat rerun ledger) as "`/ask/` is marketplace search (B&J L-010/L-011 family)".
- **Ben & Jerry's L-011:** "No document Q&A surface. `/ask/` is marketplace search", which answers all seven fixed questions with the fallback.
- **Memo 104's run** (`f73bef5`, `pass-a/10_retrieval_ask_q1_q7.json`): the probe sent `POST /api/v1/zelda/ask/ {"q": <question>}` as the owner for Q1–Q7.
  - All seven got `200 {"status": "success", "response": "I couldn't find specific search criteria in that — try mentioning industry, size, price, or financials for founders.", "results": []}`.
  - The document's own `/search/` and `/rag/` returned 200 with evidence for the same questions.

## Root cause (code and recorded evidence)

At `b278364`, `ZeldaAskAPIView.post` (`zelda_api/views.py`) reads only two things:
- the question `q`;
- the requester's role (buyer → seller search; everyone else → founder search).

There is no document input. Whatever the question is about, it goes to `_call_claude_for_query_extraction` (one model call), which looks for marketplace constraints such as sector, stage or price. "How much has ManyChat raised?" has none, so `constraints` is empty and the view returns the fixed "couldn't find specific search criteria" text.

So nothing failed in the routing, context or fallback selection. The document **could not be named**:
- the probe sent no document because the endpoint accepts none;
- the panel's Ask tab sends `{q}` only (`templates/includes/zelda_ai_assistant_enhanced.html`);
- a `document_id` added to the body was ignored. The replay below shows this: before the fix, a stranger sending another owner's `document_id` got the same 200 fallback.

## The fix

When the body carries a `document_id`, `ZeldaAskAPIView` hands the question to `_document_question`. Nothing else changes.

| Concern | Behaviour |
|---|---|
| Input | `document_id` must be an integer (not a bool or a string) → else 400. `q` must be a non-blank string → else 400. An unknown document → 404 (as `/documents/<id>/search/`) |
| Authorization | `authorize(Principal.from_request(...)).text_permitted(doc)`, **before** retrieval: the rule `/documents/<id>/search/` uses. The owner and staff are allowed. An investor (connected or not), a roleless user, another owner, a staff member viewing as an investor, and anonymous are refused (403/401) with no text |
| Document isolation | `VectorRetriever().retrieve(principal, question, doc)`: the principal-scoped retrieval, narrowed to that one document. A refusal from it is a 403 |
| The answer | That document's own chunks, as `evidence` (`chunk_id`, `page`, `section`, `text`, `relevance`), equal to `/search/`'s results. The response sentence is fixed and states only how many passages were found and on which pages, with "the document's own words … not a verified answer". **No figure is composed, nothing is generated, and no answer is hard-coded** |
| Insufficient evidence | `no_relevant_evidence` is said outright (true exactly when there is no evidence), with "No relevant evidence was found in this document for that question." |
| Model calls | **None.** No query extraction; the query embedding is local hashing |
| Marketplace | No `document_id` (or `null`) → the marketplace search, byte for byte as before, including its rate limit, extraction and fallback |

**Not changed:** the panel UI, the output guards, retrieval ranking, and the marketplace path.

## Reproduction and before/after

**Regression tests** in `zelda_api/tests_ask_document.py`, built on `AuthorizationFixture`. That fixture includes the private document, the hidden document and the connected investor:
- **At `b278364`** (the final test file placed there temporarily, then removed): 14 tests, **17 failures and 6 errors** ([output/red_final_tests_on_b278364.txt](output/red_final_tests_on_b278364.txt)). The reproduction fails with the fallback text: `"I couldn't find specific search criteria" unexpectedly found in …`. The first 13-test run is kept in [output/red_first13_on_b278364.txt](output/red_first13_on_b278364.txt).
- **The two marketplace controls pass on both commits:** a question with no `document_id` still gets extraction and the fallback, and a real marketplace question still finds founders.
- **At `e4d17d7`:** 14 OK.

**Offline before/after on memo 104's own deck chunks** ([output/replay_summary.txt](output/replay_summary.txt), with detail in [before](output/replay_before_b278364.json) and [after](output/replay_after_e4d17d7.json)).
- **Setup:**
  - document 3146's 12 recorded chunks (`f73bef5` `02_chunks.json`), loaded into the throwaway test database and embedded with the run's scheme;
  - memo 104's Q1–Q7 sent both as the run sent them (`{q}`) and with the document;
  - extraction mocked to the run's recorded result, so no model was called.
- **Faithful to the live run:** for all seven questions, `/search/` ranks equal the ones memo 104's run recorded, and the `{q}` response equals the recorded body byte for byte.

| | At `b278364` (before) | At `e4d17d7` (after) |
|---|---|---|
| `{q}` (as the run sent it) | the marketplace fallback (7/7) | the same fallback (7/7, unchanged) |
| `{q, document_id}` as the owner | **the marketplace fallback (7/7)**; `document_id` ignored | 200: 5 cited excerpts each, **equal to `/search/`** (7/7); `results` empty |
| `{q, document_id}` as a stranger | 200 fallback | **403**, no text |
| Extraction calls (mocked) | 14 | 7 (the `{q}` form only) |

Evidence pages after the fix:

| Q | Pages |
|---|---|
| Q1 | 2, 1, 3, 4, 5 (page 2 is "$23.1M raised") |
| Q2 | 1, 2, 3, 4, 5 |
| Q3 | 10, 12, 1, 2, 3 |
| Q4 | 2, 1, 3, 4, 5 |
| Q5 | 2, 1, 3, 4, 5 |
| Q6 | 1, 2, 3, 4, 5 |
| Q7 | 1, 2, 3, 4, 5 |

`no_relevant_evidence` is false for all seven, because "ManyChat" matches every chunk. **This is the known retrieval gap (L-002/L-013), unchanged by this fix.** Q2 ("users") never reaches page 10's bots/messages chunk; see the plan revision.

## Tests

Run serially with the CI placeholder settings, with free RAM of 1.38–1.73 GB before each run, above the 0.9 GB floor ([output/suite_ram.txt](output/suite_ram.txt)):

| Run | Result |
|---|---|
| **New:** `zelda_api.tests_ask_document` | **14 OK** |
| **Endpoint and boundary:** `tests_retrieval`, `tests_boundary_closeout`, `tests_chunk_boundary`, `tests_authorization`, `tests_principal`, `tests_no_investment_advice`, `tests_source_naming`, and from `zelda_api.tests` the classes `AskZeldaAPIViewTests`, `AskZeldaBuyerSellerSearchTests`, `ZeldaSearchAccessTests`, `ZeldaGlobalSearchInvestorPrivacyTests` | **141 OK** (existing tests, unchanged) |
| **The four fidelity modules:** `tests_output_fidelity`, `tests_usage_basis`, `tests_funding_fidelity`, `tests_claim_context_dates` | 283 + 77 + 67 + 25 = **452 OK**, the same as the previous baseline (this fix touches none of them) |

Total: **607 OK** = the 452-test fidelity baseline + 141 existing endpoint and boundary tests + **14 new**. The full repository suite was not run, because of the machine's memory limits.

## Targeted mutations

Source: [output/mutations_ra114.txt](output/mutations_ra114.txt), with the rerun in [output/mutations_ra114_rerun.txt](output/mutations_ra114_rerun.txt). One mutant at a time was applied on disk to `views.py`, tested with `tests_ask_document`, then the original bytes were restored and SHA-checked. A mutant counts as caught only through assertion failures.

| ID | Mutant | Result |
|---|---|---|
| R1 | `document_id` ignored (the bug) | caught, 17 |
| R2 | routes on a `null` `document_id` too | caught |
| A1 | no authorization check before retrieval | caught (retrieval reached for a stranger) |
| I1 | retrieval over every document the principal may read | caught, by the staff test added for it. It survived the first run, because an owner can read only their own document |
| E1, E2 | `no_relevant_evidence` never true; empty evidence worded as found | caught |
| V1, V2 | a bool accepted as an id; a blank question accepted | caught |
| X1 | model extraction still called on the document path | caught |
| X2 | marketplace cards added to a document answer | caught |
| A2 | a retrieval refusal returned as 200 with no evidence | **survived; not proven equivalent.** It cannot be reached: the same `text_permitted` check refuses first. It is kept as defence in depth |

**10 of 11 caught.**

## For the live run

[NEXT_LIVE_VALIDATION_REV_RA114.md](NEXT_LIVE_VALIDATION_REV_RA114.md) revises `1aab9e3`'s plan additively, for after this fix is reviewed and merged:
- Q1–Q7 are asked with and without the run's `document_id`;
- explicit RA-114 pass/fail criteria for the document-grounded answers;
- the **8-call ceiling** and no retries, as before;
- F-2's **"not exercised"** outcome, as before.

**Offline prediction:** on current retrieval, RA-114 would **fail live on Q2's grounding**. Page 10 is not reached, which is the retrieval gap, not routing. The criterion is not weakened to fit the prediction.

## Reproduce

Scripts are committed under [output/scripts/](output/scripts/) **with a `.txt` suffix**, because repo tests walk `.py` files:
- `t.sh.txt` (test runner; CI placeholder settings, no credentials);
- `mutate_ra114.py.txt` (mutation harness);
- `tests_tmp_ra114_replay.py.txt` (the before/after replay). It is copied into a worktree as `zelda_api/tests_tmp_ra114_replay.py`, run with `RA114_REPLAY_OUT=<json>`, then deleted. Its users carry a throwaway test password only.
