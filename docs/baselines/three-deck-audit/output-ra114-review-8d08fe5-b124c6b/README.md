# RA-114, round 3: the three findings of the review of 8d08fe5 (offline, at b124c6b)

This folder adds evidence for branch `fix/ask-document-routing-ra114`.
- **Earlier evidence is unchanged:**
  - round 1 (`6917e84`, `output-ra114-ask-document-e4d17d7/`);
  - round 2 (`8d08fe5`, `output-ra114-ranking-panel-9ee8d3d/`);
  - everything before them.
- **Nothing else was touched:**
  - no model was called;
  - no application database or MFA was changed. Tests and replays used the throwaway test database; the browser walks used throwaway SQLite files in the scratchpad;
  - the worker was not started, and nothing was merged or deployed.
- **Status:** my own results, pending independent review. **RA-114 live acceptance stays open.** The seven predicted grounding passes are still predictions from recorded chunks. RA-108, RA-109, Q-2–Q-4 and overall acceptance also remain open.

| Item | Value |
|---|---|
| Reviewed | `8d08fe5` (code `9ee8d3d`) |
| Validation head | **`b124c6b67ae44eb8f305e729b56663a9f03f8c28`** (one commit on `8d08fe5`) |
| Base | `b27836439ca0e6aa9acc1ca6feaeae1be80b6415` (`origin/main`, unchanged) |
| Changed | `zelda_api/retrieval.py`, `templates/includes/zelda_ai_assistant_enhanced.html`; tests: `tests_document_retrieval_ranking.py` (+7), new `tests_assistant_panel_ask.py` (7) and `js_tests/assistant_panel_ask.js`, `js_tests/panel_source.js` (the escaping harness's extraction helpers, moved so both harnesses share them), the `tests_assistant_panel_escaping.py` inventory, and one re-anchored control in `tests_retrieval.py` ([output/commit_and_hashes.txt](output/commit_and_hashes.txt)) |
| Unchanged | `zelda_api/views.py` (same blob as `e4d17d7`), every output guard |

## Finding 1 (P2): a company name could erase the question's subject

**Cause:** `without_subject` removed **each word** of `source_entity` from the question. For "Revenue Labs", "What is the revenue?" lost `revenue` and reached nothing.

**Fix:** the subject is the document's **full name as a phrase** (`subject_pattern`):
- its words in order;
- any punctuation or spacing between them (so "Ben & Jerry's" matches "Ben & Jerry’s");
- a trailing legal suffix optional (`Inc`, `LLC`, `Ltd`, …).

It is set aside in the question **and in each passage**, so a "Revenue Labs" footer does not make every page a revenue match. A topic word used apart from the full name still counts. Across documents nothing is set aside, as before.

| Revenue Labs deck (2 chunks) | `9ee8d3d` | `b124c6b` |
|---|---|---|
| "What is the revenue?" | none | **page 2** |
| "What is Revenue Labs' revenue?" | none | **page 2** |
| "Who founded Revenue Labs?" | none | none |

Source: [before](output/rank_replay_before_9ee8d3d.json) and [after](output/rank_replay_after_b124c6b.json), `revenue_labs_pages`. Tests in `SubjectNameTests` cover:
- the reviewer's case;
- the full name alone selecting nothing;
- a legal suffix with punctuation (`Ben & Jerry’s, Inc.`).

## Finding 2 (P2): fallback retrieval skipped the corrected ranking

**Cause:** when the question could not be embedded, or no chunk had a stored vector, `retrieve` used the old `_keyword_fallback_search`. That was a substring match (`icontains`) on raw words at a fixed relevance of 0.5. "many" in "How many users…" matched "manychat" in every footer.

A chunk with no vector was also dropped from the main path whenever other chunks had one.

**Fix:** one `_rank` path for every case.
- Every authorized candidate gets the same lexical score (subject phrase set aside, question words, word forms, topic headings).
- Vector similarity is added only where both the question and the chunk have a vector.
- The old fallback is removed. The scope rule is unchanged, because candidates still come only from `_candidates`.
- `tests_retrieval`'s positive control for the chunk-read scan was anchored on the old fallback's line. It is re-anchored to `_rank`'s read, with the same assertion that a direct `DocumentChunk` read fails the scan.

Memo 104's recorded chunks:

| Q | Normal path (both) | Question not embedded, `9ee8d3d` → `b124c6b` | No stored vectors, `9ee8d3d` → `b124c6b` |
|---|---|---|---|
| Q1 | 2 | 1, 2, 3, 4, 5 → **2** | 2 → 2 |
| Q2 | 10 | 1, 2, 3, 4, 5 → **10** | 1, 2, 3, 4, 5 → **10** |
| Q3 | 10, 12 | 1, 2, 3, 4, 5 → **10, 12** | 1, 2, 3, 4, 5 → **10, 12** |
| Q4 | none | 1, 2, 3, 4, 5 → **none** | 2 → **none** |
| Q5 | 2 | 1, 2, 3, 4, 5 → **2** | 2 → 2 |
| Q6 | 2, 1 | 1, 2, 3, 4, 5 → **2, 1** | 1, 2 → **2, 1** |
| Q7 | none | 1, 2, 3, 4, 5 → **none** | none → none |

At `b124c6b` all three columns are identical. The normal path is unchanged from round 2, and `/ask/` equals `/search/` for all ten replay questions. Tests in `FallbackPathTests` require the exact same ids and relevances with no vectors and with an unembeddable question, plus:
- a single chunk without a vector is still ranked;
- the fallback stays inside the document.

## Finding 3 (P2): a delayed answer could render under another document

**Cause:** the Ask submit handler rendered whatever came back, whenever it came back. Nothing tied a response to the request or the context it was made in.

**Fix:**
- Each Ask takes the next request number (`zeldaAskRequest`), and choosing or clearing a document moves the number on.
- A response renders, or reports an error, only if its number is still current.
- Otherwise the panel logs one line, "An earlier question was answered after you moved on; its answer is not shown.", and leaves the screen as it is.
- This applies to marketplace answers too: an older search no longer replaces a newer one.
- The submit body is now a named function, `submitZeldaAsk`, so it can be run outside the browser.

**Reproduction and before/after, in a real browser.** Headless Chrome, throwaway profile and database, network blocked, extraction recorded. The server delays questions containing "raised" by 2.5 s; the driver is `race_walk.mjs`. RED ran on a temporary detached worktree at exactly `9ee8d3d`, removed afterwards:

| Scenario | `9ee8d3d` ([red](output/race_walk_red_9ee8d3d/race_walk.json)) | `b124c6b` ([green](output/race_walk_green_b124c6b/race_walk.json)) |
|---|---|---|
| Ask about ManyChat (delayed), choose Northwind before it answers | context "Northwind", **ManyChat's page 2 excerpt rendered** | context "Northwind", nothing rendered, stale notice logged |
| On Northwind: delayed question, then a fast one | the newer answer (page 2) was **replaced by the older** (page 3) | the newer answer (page 2) stays |
| Delayed document question, then "Ask the marketplace instead" | context cleared, **Northwind excerpt rendered** | nothing rendered |

Screenshots for each scenario are in both folders. Both walks had 0 console errors.

**Automated regression:**
- `zelda_api/tests_assistant_panel_ask.py` runs the template's own Ask functions and state declarations in Node (`js_tests/assistant_panel_ask.js`), with a stub DOM and a `fetch` whose answers each scenario releases in its own order. Seven tests:
  - the current answer renders (positive control);
  - the reviewer's switch;
  - an older question answered last;
  - clearing to the marketplace;
  - a stale refusal and a stale network failure say nothing;
  - the marketplace still sends `{q}` alone and shows its cards;
  - an older marketplace answer never replaces a newer one.
- These tests cannot run at `9ee8d3d`, where `submitZeldaAsk` does not exist. **The behavioral RED for this finding is the browser walk above**, not this test.

**Regression of round 2's panel walk at `b124c6b`** ([output/panel_walk_b124c6b/walk.json](output/panel_walk_b124c6b/walk.json)): request bodies, statuses and evidence pages are identical to round 2. Marketplace `{q}`; Q1, Q2, Q3 and Q7 get [2], [10], [10, 12] and none; the stranger gets 403. 0 console errors; 3 recorded extraction calls (the three marketplace questions).

## Tests

Run serially at `b124c6b` with the CI placeholder settings. Free RAM was 1.16–1.35 GB before each run, above the 0.9 GB floor ([output/suite_ram.txt](output/suite_ram.txt)).

| Run | Result | Change from round 2 |
|---|---|---|
| `tests_ask_document` | 15 OK | — |
| `tests_document_retrieval_ranking` | **27 OK** | +7 (`SubjectNameTests` 3, `FallbackPathTests` 4) |
| Endpoint, boundary and provenance group | 156 OK | one control re-anchored |
| Panel: `tests_assistant_panel_ask`, `tests_assistant_panel_escaping`, `pages.tests_zelda_panel_markup`, `tests_library` | **52 OK**, no skips (Node ran) | +7 (`tests_assistant_panel_ask`) |
| The four fidelity modules | 283 + 77 + 67 + 25 = **452 OK** | unchanged baseline |

**Total: 702 OK** (round 2: 688; +14 new tests). The full repository suite was not run, because of the machine's memory limits.

**RED:** the 27 ranking tests on `9ee8d3d`'s `retrieval.py` give **4 failures** ([output/red_ranking_on_9ee8d3d.txt](output/red_ranking_on_9ee8d3d.txt)):
- the Revenue Labs topic-word test;
- the three fallback-ranking tests.

The other three new tests pass there too, as they should, because they are controls: the full name alone, the legal suffix, and fallback isolation.

## Targeted mutations

At `b124c6b`, one mutant at a time, original bytes restored and SHA-checked. A mutant counts as caught only by assertion failures ([output/mutations_b124c6b.txt](output/mutations_b124c6b.txt)). The harness is built from round 2's by [build_harness.py.txt](output/scripts/build_harness.py.txt), which re-anchors S1 and S2 to the new code and checks that every anchor occurs exactly once.

**32 of 32 caught:**
- views 11 (unchanged);
- retrieval 15, including new N1 (each name word set aside on its own: the bug), N2 (name set aside in the question only), N3 (legal suffix not optional), F1 (chunks without a vector skipped) and F2 (an unembeddable question gets nothing);
- template 6, including new G1 (stale answers shown), G2 (choosing a document leaves pending answers current), G3 (a new question leaves the older one current) and G4 (stale failures reported).

**What this covers, and what it doesn't:** this is coverage of these targeted mutants only, not complete mutation coverage. **Not mutated:**
- `LEGAL_SUFFIXES` entry by entry;
- the phrase pattern's punctuation class;
- the stale-notice wording;
- everything listed as unmutated in round 2.

## Remaining (not changed here)

- **A partial name is not the subject.** "Brightline" alone, in a question about "Brightline Robotics", still counts and still ties footer chunks that carry "brightline.io". Only the full name is set aside. That is the reviewer's requirement, and its cost.
- **The hash vectors stay inert** (round 2, section 2).
- **A non-object JSON body** to `/ask/` still fails, as before.
- **A pending Ask's text box:** a superseded request no longer clears it, but the current request still clears it when its answer arrives (as before).

## For the live run

Revision 2 of the live plan ([../output-ra114-ranking-panel-9ee8d3d/NEXT_LIVE_VALIDATION_REV2_RA114.md](../output-ra114-ranking-panel-9ee8d3d/NEXT_LIVE_VALIDATION_REV2_RA114.md)) stands, unedited:
- the **8-call ceiling** and no retries;
- F-2's **"not exercised"** outcome;
- its criteria and its panel document-form check.

**Its offline prediction is unchanged at `b124c6b`:** the normal-path pages are identical (replay above). It applies after this branch is reviewed and merged, with the post-merge byte check at the merge commit. The live run uses stored vectors and an embeddable question, so it exercises the normal path; finding 2's paths are covered offline only. The race in finding 3 is not part of the live run either: it needs a delayed response, which a live run cannot arrange within the plan, so its evidence is the offline walk and the Node tests.

## Reproduce

Scripts are under [output/scripts/](output/scripts/) with a `.txt` suffix, because repo tests walk `.py` files:
- **`verify_panel_server.py.txt`:** round 2's throwaway server, plus a second own document and optional `RA114_SLOW_QUESTION`/`RA114_SLOW_SECONDS` delays. Run it with `python -B`.
- **`race_walk.mjs.txt`:** `node race_walk.mjs <out_dir> <port> <chrome.exe>`, against the server started with `RA114_SLOW_QUESTION=raised`.
- **`tests_tmp_ra114_rank_replay.py.txt`:** round 2's replay plus the unembedded, no-vector and Revenue Labs cases. Copy it in as `zelda_api/tests_tmp_ra114_rank_replay.py`, run it with `RA114_CHUNKS` and `RA114_REPLAY_OUT`, then delete it.
- **`mutate_ra114c.py.txt`, `build_harness.py.txt`, `t.sh.txt`.**

The throwaway servers' `seed.json` (session keys) and SQLite files are not committed.
