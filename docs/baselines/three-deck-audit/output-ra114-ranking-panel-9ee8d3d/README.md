# RA-114, round 2: review of e4d17d7, passage retrieval for Q2, and the panel's Ask tab (offline, at 9ee8d3d)

This folder adds evidence for branch `fix/ask-document-routing-ra114`.
- **Earlier evidence is unchanged:**
  - memo 104's run (`f73bef5`);
  - the post-merge verification (`1aab9e3`);
  - round 1 (`6917e84`, `output-ra114-ask-document-e4d17d7/`).
- **Nothing else was touched:**
  - no model was called;
  - no application database or MFA was changed. Tests and replays used the throwaway test database; the panel walk used a throwaway SQLite file in the scratchpad, deleted afterwards;
  - the worker was not started, and nothing was merged or deployed.
- **Status:** all results here are my own and pending independent review. **RA-114 stays open.** It needs a live run graded against the answer key. RA-108, RA-109, Q-2–Q-4 and overall acceptance also remain open.

| Item | Value |
|---|---|
| Validation head | **`9ee8d3dbf156cdee15167e87702d6a7802780551`** |
| Commits since round 1 | `64c5020` (retrieval, panel, tests), `9ee8d3d` (one test pair; a redundant tie-break removed) |
| Base | `b27836439ca0e6aa9acc1ca6feaeae1be80b6415` (`origin/main`, unchanged) |
| Changed since `e4d17d7` | `zelda_api/retrieval.py`, `templates/includes/zelda_ai_assistant_enhanced.html`, `zelda_api/tests_ask_document.py` (+1 test, more ids), `zelda_api/tests_assistant_panel_escaping.py` (inventory +2 renderers), new `zelda_api/tests_document_retrieval_ranking.py`, new `zelda_api/data/document_retrieval/memo104_chunks.json` ([output/commit_and_hashes.txt](output/commit_and_hashes.txt)) |
| Unchanged | `zelda_api/views.py` (same blob as `e4d17d7`), every output guard (`basis_fidelity.py` and `funding_fidelity.py` are the same blobs as at `b278364`) |

## 1. Review of the API fix at `e4d17d7`

I verified the reported results against the committed files. The round 1 README's figures match its outputs: 14 tests, 607 OK, 10/11 mutants, and replay pages identical to `/search/`.

| Concern | Finding |
|---|---|
| **Document isolation** | Retrieval goes through `VectorRetriever._candidates`: the principal's permitted documents, narrowed to the one asked about, before anything is scored. Covered by the owner test (`test_only_that_documents_chunks_are_used`), the staff test (`test_staff_who_may_read_every_document_get_only_the_one_asked_about`) and mutant I1. This round adds cross-document controls on the recorded deck: a second document of the same owner says "users", "raised" and "Traction" outright and is never returned (`CrossDocumentTests`; replay field `other_document_text_returned` false for all ten questions) |
| **Authorization parity with `/documents/<id>/search/`** | Same rule (`authorize(principal).text_permitted(doc)`), same principal construction, same order (check, then retrieve). It also has the same existence signal: 404 for a missing document, 403 for one the principal may not read. That signal is inherited from `/search/`, not new |
| **Input validation** | `document_id` must be a JSON integer, not a bool or a string, else 400. Missing, 0, negative or out-of-range ids (2⁶³, 10³⁰) are 404, not 500: new subtests, checked on SQLite under Django 6.0.4, which returns no row for out-of-range integer lookups. `q` must be a non-blank string, else 400. **Not changed, pre-existing:** a JSON body that is not an object (an array) makes `request.data.get` fail on both the marketplace and document paths |
| **Response compatibility** | Success keeps the marketplace shape the panel already reads (`status`, `response`, `results: []`) and adds `document_id`, `evidence` and `no_relevant_evidence`. Errors keep `{status: 'error', message}`, which the panel shows. `/search/` uses `{error}`; `/ask/` stays consistent with itself |
| **`RetrievalRefused` path** | Reachable only if retrieval's own check disagrees with the view's: access revoked between the two calls, or the two checks drifting apart in future. Round 1's mutant **A2** (refusal answered 200 with no evidence) survived because no test reached it. **It was not equivalent**: a 200 there would say "nothing in this document bears on it" to someone who was refused. A new test, `test_a_refusal_from_retrieval_itself_is_a_403`, forces the refusal and requires 403 with no text. A2 is now caught |

## 2. Q2's retrieval failure: diagnosis on memo 104's recorded chunks

The chunks are frozen in `zelda_api/data/document_retrieval/memo104_chunks.json`: a field-for-field copy of `f73bef5`'s `02_chunks.json`, with its source SHA-256 recorded. The before/after replay is in [output/rank_replay_before_e4d17d7.json](output/rank_replay_before_e4d17d7.json) and [output/rank_replay_after_9ee8d3d.json](output/rank_replay_after_9ee8d3d.json).

1. **The vector half of the score is inert.**
   - The pipeline stores `json.dumps(vector)` in a JSONField, so `embedding_vector` is a **string** (`stored_vector_type: str`).
   - `cosine_similarity(list, str)` returns 0 on the length mismatch, so every similarity is 0 (`similarity_as_stored`).
   - Ranking is therefore `0.3 × keyword overlap`. The recorded relevances (0.2, 0.1, 0.06 …) are exactly that.
   - Decoding the vectors would not help. The semantic-hash similarity between a question and unrelated chunks is noise: Q5 against pages 1 and 8 gives −1.0, against page 11 0.999, and page 7 gives NaN (`similarity_if_decoded_by_page`).
   - **Left unchanged and recorded:** see "Remaining" below.
2. **Ties came from the overlap itself:**
   - "ManyChat" is in every chunk (`angel.co/manychat` on every slide), so a question naming it scores every chunk alike. Q2, Q7 and the subject-only control C2 tie on all five results; the others tie below their first one or two.
   - Question words count: "with" is the only reason page 2 led for Q4 (0.2 against 0.1).
   - "raise" does not match "raised", so Q6 tied pages 1 and 2 at 0.15.
3. **Q2 cannot reach page 10 lexically.**
   - The deck never says "users".
   - Page 10 reports adoption as "Total Bots Created … Traction by Apr-16 … 140 000+ bots".
   - No word of the question appears there.

## 3. The correction (`zelda_api/retrieval.py`), general by construction

| Rule | Evidence | Mutants that fail without it |
|---|---|---|
| Inside one document, its own subject name (`source_entity`) is set aside; across documents it still counts | (2) footer name in every chunk | S1 (7 failures), S2 |
| Question words do not count (`QUESTION_WORDS`) | (2) "with", Q4 | W1 |
| A light word form: plural and `-ed`. `-ing` is left alone, because "messaging apps" (page 4, the platforms' user counts) is not a count of messages | (2) "raise"/"raised", Q6 | ST1, ST2, ST3 |
| A question in a pitch-deck topic's words also reaches a passage headed with that topic's name, at half weight. A word the question already uses counts once | (3) Q2 | T1, T2, T3 |

**Where the topic words come from:** the existing category vocabulary, `retrieve_for_category`'s queries, hoisted unchanged to `CATEGORY_QUERIES`. Its Traction entry, "customers users adoption growth metrics", dates from `d02d480a` (June 2026).

**Nothing in the code names ManyChat, page 10, a question or an answer.** The same rules are tested on synthetic decks with other names and words (`SyntheticDeckTests`):
- a footer name on every page selects nothing;
- a stated "users" outranks a "Traction" heading;
- word forms match;
- a one-chunk document still answers.

**Scope:** the change reaches only `/documents/<id>/search/`, `/documents/<id>/rag/` and the `/ask/` document form. The memo pipeline imports only `RetrievalRefused` from this module, and `ContextAssembler` has no caller outside the module and its tests.

**One addition was removed again.** `64c5020` added an explicit tie-break on (document, chunk index). Mutation D1 showed it is **equivalent**: `DocumentChunk.Meta.ordering = ['document', 'chunk_index']` already orders every candidate query, and the sort is stable. `9ee8d3d` removes it. A test stores chunks out of order and pins that equal scores come back in the document's order.

### Before / after on memo 104's chunks

Production-shaped vectors; `/ask/` with the document; extraction patched and **0 calls**; `ask_equals_search` true for every row:

| Q | Before (`e4d17d7`): pages (relevance) | After (`9ee8d3d`): pages (relevance) | `no_relevant_evidence` after |
|---|---|---|---|
| Q1 raised | 2 (0.2), 1, 3, 4, 5 (0.1) | **2** (0.3) | false |
| Q2 users | 1, 2, 3, 4, 5 (all 0.06) | **10** (0.15) | false |
| Q3 messages | 10, 12 (0.12), 1, 2, 3 (0.06) | **10, 12** (0.15) | false |
| Q4 SEC | 2 (0.2), 1, 3, 4, 5 (0.1) | none | **true** |
| Q5 revenue | 2 (0.15), 1, 3, 4, 5 (0.075) | 2 (0.15), on "current"; page 2 states no revenue | false |
| Q6 Series A | 1, 2 (0.15), 3, 4, 5 (0.075) | **2** (0.3), 1 (0.15) | false |
| Q7 invest? | 1, 2, 3, 4, 5 (all 0.1) | none | **true** |
| C1 "What is the weather in Paris?" | none | none | true |
| C2 "Who is ManyChat's CEO?" | 1, 2, 3, 4, 5 (all 0.3) | none | **true** |
| C3 the other document's words | 2, 1, 10 | 2, 1, 10; the other document is never returned | false |

**These rows show which passages are reached. They do not show that a question passed its grounding criterion.** That is graded live against the answer key (plan below). Offline, against revision 1's per-question table, the reached pages are consistent with:
- Q1 (page 2), Q2 (page 10), Q3 (pages 10 and 12) and Q6 (page 2) including their required passage;
- Q4, Q5 and Q7 composing nothing.

## 4. The panel (`templates/includes/zelda_ai_assistant_enhanced.html`)

The Ask tab had no document context. Global search, the Library and briefs open documents, but the Ask form always sent `{q}`.

**Ownership:** the memo response does not tell the panel who owns a document. Setting a document context implicitly, for example on opening a brief, would have sent an investor's next marketplace question to a document they may not read (403). So the context is explicit:
- **Library**, "your company" section (the viewer's own uploads, `uploaded_by=user`): documents that can open a brief (analyzed, with a memo) get **Ask about this document**.
- The button sets a **visible, clearable** context bar: "Asking about *name*. Answers are passages quoted from it, not marketplace results. · *Ask the marketplace instead*". It also switches to the Ask tab.
- With the context set, Ask sends `{q, document_id}` and shows the passages with their pages, escaped.
- With no context, Ask sends `{q}` exactly as before, and the existing submit path is unchanged.

**Headless-Chrome walk at `9ee8d3d`** ([output/panel_walk/walk.json](output/panel_walk/walk.json), with the server's own request log in [ask_requests.jsonl](output/panel_walk/ask_requests.jsonl) and six screenshots):
- Chrome used a throwaway profile, against a local server on a throwaway SQLite file.
- Outbound connections were blocked, and extraction was replaced by a recorder.
- Signing in used seeded throwaway session cookies, so no password was entered anywhere.

| Step | Request body the server received | Result |
|---|---|---|
| Positive control: signed in, panel open, no context at load | — | page loaded, `askForm` present, context hidden |
| Marketplace question, no document chosen | `{q}` | 200, marketplace fallback (the recorded extraction result) |
| Library → Ask about this document | — | context bar names the document; placeholder changes |
| Q1, Q2, Q3 | `{q, document_id}` | 200; pages [2], [10], [10, 12] rendered as excerpts |
| Q7 | `{q, document_id}` | 200, "No relevant evidence was found in this document for that question."; no cards |
| Ask the marketplace instead → marketplace question | `{q}` | context gone; 200, marketplace fallback |
| Stranger: Library | — | no Ask button (no own documents) |
| Stranger forcing the owner's document from the console | `{q, document_id}` | **403** "Not authorized."; nothing rendered |
| Stranger marketplace question | `{q}` | 200, marketplace fallback |

**Walk totals:** 0 console errors. Extraction recorder calls: 3, exactly the three marketplace questions.

**Limits of the panel check:**
- There is no automated JavaScript test of the Ask handler; this walk is the check.
- The escaping inventory (`tests_assistant_panel_escaping`) now covers both new renderers. Mutants P1 (excerpt unescaped) and P2 (button name unescaped) fail it.
- The live run checks the panel's document form only (plan below).

**Process note:** a first walk, run before `64c5020` was committed, launched Python without `-B`. It rewrote tracked `.pyc` files in the worktree. These were restored to their committed bytes and the new ones removed before committing, and the final walk used `-B`. The walk recorded here is the one at `9ee8d3d`.

## Tests

Run serially at `9ee8d3d` with the CI placeholder settings. Free RAM was 1.62–1.94 GB before each run, above the 0.9 GB floor ([output/suite_ram.txt](output/suite_ram.txt)).

| Run | Result | Note |
|---|---|---|
| `tests_ask_document` | **15 OK** | 14 from round 1, plus the `RetrievalRefused` test; out-of-range ids are added to an existing test |
| `tests_document_retrieval_ranking` | **20 OK** | new |
| Endpoint and boundary group (round 1's 141), plus `tests_page_provenance` (15) | **156 OK** | existing tests, unchanged |
| Panel: `tests_assistant_panel_escaping`, `pages.tests_zelda_panel_markup`, `tests_library` | **45 OK** | existing; the inventory is extended by two entries |
| The four fidelity modules | 283 + 77 + 67 + 25 = **452 OK** | the previous baseline, unchanged |

**Total: 688 OK.** That is the 452-test fidelity baseline, plus 201 existing endpoint, boundary, provenance and panel tests, plus **35 RA-114 tests** (15 + 20). Round 1 reported 607: 452 + 141 + 14. The full repository suite was not run, because of the machine's memory limits.

**RED:** the ranking tests on `e4d17d7`'s `retrieval.py` (swapped in, then restored and compared byte for byte) give **9 of 18 tests failing**, 10 failures counting subtests ([output/red_ranking_on_e4d17d7.txt](output/red_ranking_on_e4d17d7.txt)). Nine tests pass there too, as they should, because they are controls of behavior that `e4d17d7` already had: the recorded-deck check, Q1's first page, Q3's pages, cross-document isolation (three tests), `/ask/` = `/search/`, relevance order and the one-chunk document. The two tests added in `9ee8d3d` came after that run.

## Targeted mutations

The harness is [output/scripts/mutate_ra114b.py.txt](output/scripts/mutate_ra114b.py.txt). It applies one mutant at a time on disk, restores the original bytes and checks their SHA-256. A mutant counts as caught only by assertion failures.

| Run | Result |
|---|---|
| At `64c5020`, 24 mutants ([output/mutations_64c5020.txt](output/mutations_64c5020.txt)) | 22 caught. **A2, round 1's survivor, is caught.** Two survived: **T3** (a heading the question already names counts twice), **not equivalent**, because it reorders a question that names a topic; and **D1** (ties in database order) |
| Targeted rerun after adding two tests ([output/mutations_rerun_T3_D1.txt](output/mutations_rerun_T3_D1.txt)) | T3 caught. D1 still survived, and was then shown **equivalent** (see section 3) and its code removed |
| At `9ee8d3d`, the 23 that still apply ([output/mutations_9ee8d3d.txt](output/mutations_9ee8d3d.txt)) | **23 of 23 caught**: views 11, retrieval 10, template 2 |

**What this covers, and what it doesn't:** 23/23 is coverage of these **targeted** mutants, not complete mutation coverage. They were chosen by me, around the changed lines. **Not mutated:**
- the `QUESTION_WORDS` list entry by entry;
- the stemmer's `-ies` and `-es` branches;
- `without_subject`'s word-boundary regex;
- the panel's JavaScript, beyond the two escaping mutants (it has no automated test).

## Remaining (not changed here)

- **The hash vectors.** Stored as strings, they never contribute. Decoded, they would add noise (section 2). Real embeddings, or removing the vector half of the score, is a separate decision.
- **A company whose name is an ordinary word** (for example "Revenue Labs") has that word set aside inside its own document. `source_entity` can also be a founder's name.
- **The topic rule covers only the existing category vocabulary.** A deck with neither "users" nor a "Traction" heading still returns nothing for Q2, and says so (`no_relevant_evidence`).
- **Q5 reaches page 2 on "current"** ("current site", "current products"). Page 2 states no revenue, so nothing is composed, but `no_relevant_evidence` is false. This is recorded for the grader.
- **A non-object JSON body** to `/ask/` still fails, as before.

## For the live run

[NEXT_LIVE_VALIDATION_REV2_RA114.md](NEXT_LIVE_VALIDATION_REV2_RA114.md) revises `1aab9e3`'s plan and round 1's revision additively:
- the **8-call ceiling** and no retries are kept, and F-2's **"not exercised"** outcome is kept;
- it adds an unrelated-question control and a panel document-form check, both at 0 calls;
- it replaces the offline prediction: on memo 104's chunks, every per-question grounding criterion is now predicted to pass, where revision 1 predicted Q2 to fail;
- it keeps revision 1's criteria unchanged.

## Reproduce

Scripts are committed under [output/scripts/](output/scripts/) with a `.txt` suffix, because repo tests walk `.py` files:

| Script | Purpose |
|---|---|
| `t.sh.txt` | test runner: CI placeholder settings, no credentials, labels required |
| `mutate_ra114b.py.txt` | mutation harness |
| `tests_tmp_ra114_rank_replay.py.txt` | before/after replay. Copy it into a worktree as `zelda_api/tests_tmp_ra114_rank_replay.py`, run it with `RA114_CHUNKS=<memo104_chunks.json>` and `RA114_REPLAY_OUT=<json>`, then delete it |
| `verify_panel_server.py.txt` and `panel_walk.mjs.txt` | the panel walk. Run the server with `python -B <script> <worktree> <out_dir> <port>`; it uses a throwaway SQLite file, blocks the network and records extraction. Then run `node panel_walk.mjs <out_dir> <port> <chrome.exe>`. The server's `seed.json` (throwaway session keys) and its SQLite file are not committed |
