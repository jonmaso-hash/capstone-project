# Memo-99 corrections: basis label (OF-704) and source location (OF-705) at `979bf49` / `620cefa`

**Separate, additive evidence.** It edits nothing in the memo-99 run evidence (`docs/manychat-output-fidelity-64f9db5`, `d821cca` + grade `2e3b624`), the earlier output-fidelity review folders, any run ledger, grading, memo, answer key, protocol or frozen fixture. Memo 99 is not edited or regenerated; the two new fixtures (`zelda_api/data/funding_fidelity/memo99*.json`) are additive copies of the committed evidence. No live model run was made.

**Status:** branch `fix/basis-label-source-context` from `64f9db5`, pushed and **unmerged**, with no PR. Main is still `64f9db5`.
- RA-109 live output acceptance stays open until review and a later live sample.
- RA-106's scoped acceptance is unchanged.
- RA-108, overview coverage, styling, the P3 notes and overall hardening are out of scope and still open.

| Commit | What |
|---|---|
| `979bf49` | **The correction:** `zelda_api/basis_fidelity.py` (rules `label`, `total`, `location`); regressions in `zelda_api/tests_output_fidelity.py`; additive fixtures `memo99.json` and `memo99_payload.json` (built by [scripts/make_memo99_fixtures.py](output/scripts/make_memo99_fixtures.py.txt) from `d821cca`, sent payload checked equal to the committed rebuild, leak-checked) |
| `620cefa` | Two controls the first mutation run showed missing. Tests only; the application code is byte-identical to `979bf49` ([output/pre_mutation_hashes.txt](output/pre_mutation_hashes.txt)) |

## The two graded P2s and the correction

All three rules run inside the existing basis guard. They use only the normalised items' refs, statements, statuses, pages and source contexts, plus the notes' refs. No raw chunk, key text or grading hint is involved.

### OF-704: an ambiguity labelled a contradiction

**Rule `label`:** in a sentence already tied to exactly one basis pair, by the accepted resolution rules (citations, noun or bridged antecedent):

| Becomes | From |
|---|---|
| "ambiguity" | "contradiction" |
| "ambiguities" | "contradictions" |
| "ambiguous" | "contradictory" |

It also fixes the article ("a contradiction" → "an ambiguity"). The facts and refs stay.

**Kept as written:**
- a negated form ("no contradiction", "not contradictory", "rather than a contradiction");
- a question;
- a pair where Truth Delta found a member **CONTRADICTED**;
- any sentence not tied to a pair: another metric, unrelated refs, or a non-pair group.

**"Inconsistency" is deliberately unchanged**, since the grade treats it as P3. That keeps `zelda_advantage` exactly as stored.

| Memo 99 `open_concerns` 1 | |
|---|---|
| Stored | "- Measurement-basis **contradiction** in the headline usage metric: the deck states '500M messages' without an interval on page 10 and '500M messages/month' on page 12 [C2, C3]." |
| Replay at `979bf49` | "- Measurement-basis **ambiguity** in the headline usage metric: the deck states '500M messages' without an interval on page 10 and '500M messages/month' on page 12 [C2, C3]." |

The model's next sentence ("These are not necessarily the same figure; until management clarifies …") and the other bullets are unchanged. That includes the funding bullet's "establish or contradict it", which is a verb about external evidence and not this label.

### OF-705: different source pages presented as one dated slide

**Rule `location`** (any sentence):
- **Trigger:** a shared-place phrase, "on/in the same (traction) slide/page [refs]" or "on/in a/the slide headed 'X' [refs]".
- **When it acts:** only if the citation group mixes pages or contexts, or names a context some ref lacks, **and** cites a member of a basis pair.
- **Repair:** each ref is placed under its own page and context from the admitted items' sources, in citation order.
- **Never:** no ref is dropped, and nothing is invented; a ref without a page leaves the sentence as written. Questions are kept.

**Rule `total`:** in a sentence tied to the pair, the pair's unspecified-interval figure followed by "total" ("500M total") becomes "500M with no stated interval". It is kept when the pair states a cumulative fact, and in questions.

| Section | Stored (memo 99) | Replay at `979bf49` |
|---|---|---|
| `supported_points` 2 | "… a messages figure of either **500M total** or 500M/month (measurement basis unresolved; see open concerns) **on the same traction slide [S2, S3]**, suggesting …" | "… a messages figure of either **500M with no stated interval** or 500M/month (measurement basis unresolved; see open concerns) **on page 10 (slide headed 'Traction by Apr-16') [S2] and page 12 [S3]**, suggesting …" |
| `business_model_analysis` | "… 140,000+ bots and 500M messages (measurement basis questioned; see open concerns) **on a slide headed 'Traction by Apr-16' [S1, S2, S3]** — which confirm …" | "… 140,000+ bots and 500M messages (measurement basis questioned; see open concerns) **on page 10 (slide headed 'Traction by Apr-16') [S1, S2] and page 12 [S3]** — which confirm …" |

**Placement matches the payload exactly:**
- S1 and S2 are on page 10 under 'Traction by Apr-16';
- S3 is on page 12 with no context.

The test `test_every_placed_citation_supports_its_page_and_context` checks all five placed refs against the payload's sources.

**Correct shared contexts are left alone:**
- `executive_summary` "appearing in a slide headed 'Traction by Apr-16' [S1, S2]";
- `base_scenario`;
- `information_readiness` "(slide headed 'Traction by Apr-16') [S1, S2]";
- `risk_assessment`'s "page 10 (slide headed 'Traction by Apr-16') [C3, S2] and '500M messages/month' on page 12 [C2, S3]".

## Replay of the actual memo replies ([output/replay_memos_96_97_98_99_620cefa.json](output/replay_memos_96_97_98_99_620cefa.json))

**Method:** each committed raw reply is replayed through the merged pipeline order (list normalisation → time guard → funding guard → basis guard) and compared with what that run stored. The output is identical at `979bf49` and `620cefa`.

| Memo | Sections differing from stored | Rule changes |
|---|---|---|
| 96 | `zelda_advantage` only (the accepted FF-405 wording) | as before |
| 97 | none | as before |
| 98 | the four accepted corrections, **identical** to the `aaa6e0a` replay | as before |
| **99** | **`open_concerns`, `supported_points`, `business_model_analysis` only** | `basis_contradiction_label`; `basis_unspecified_total` + `basis_source_location`; `basis_source_location`. Plus memo 99's five accepted live funding-guard edits (`cash_premise`, `funding_not_runway`, three attributions), unchanged |

**Memo-99 checks in the test module:**
- every other field is exactly as stored;
- citations stay in the same order;
- reversed item order gives the same output;
- a second pass changes nothing.

## Evidence

- **Red** ([output/red_run_on_64f9db5.txt](output/red_run_on_64f9db5.txt)): the regressions run against the code at `64f9db5`, before any implementation, gave **80 tests, 13 failures**. They covered the memo-99 replay (OF-704, OF-705 and placement support), the stored sections, the memo writer, and the helper-level label, location and total rules. The negative controls and every earlier memo-98 and containment test passed.
- **Green** ([output/first_green_979bf49.txt](output/first_green_979bf49.txt)): 80 OK at `979bf49`; the focused related modules ran 293 OK. No test expectation was changed to fit the code.

### Regressions (`zelda_api/tests_output_fidelity.py`, 82 tests)

| Class | Covers |
|---|---|
| `Memo99ReplayTests` | The actual memo-99 reply and payload: fixture identity; OF-704 repaired with its qualification kept; OF-705 per-page placement and no "500M total"; each placed citation supports its page/context; every other field exactly as stored; citations in order; correct shared contexts, the management question, "(total vs. per month)" and "internal inconsistency" kept; second pass; reversed items; only the expected rules fired |
| `Memo99StoredSectionsTests` | Memo 99's stored text through the basis guard: the same three sections change and no others |
| `BasisLabelTests` | Article and plural/adjective forms. Negations, questions and "inconsistency" kept. Unrelated metric, non-pair group, mixed revenue/pair refs and an external CONTRADICTED pair item kept |
| `BasisSourceLocationTests` | Cross-page groups placed (three phrase forms, citation order). Correctly shared context, separately placed figures, a single ref, a question and a non-pair group kept. No note means no placement |
| `BasisUnspecifiedTotalTests` | "500M total" repaired. Conditional "cumulative total", "(total vs. per month)" and another metric's total kept |
| `Of705MutationControlTests` (`620cefa`) | A pair with a stated cumulative side keeps "3M total"; a shared-place question is kept |
| `PipelineMemo99Tests` | The memo writer (`_generate_memo`) stores the three repairs and leaves `executive_summary`, `risk_assessment`, `what_would_change_the_picture`, `zelda_advantage`, `questions_for_management` and `downside_scenario` as memo 99 stored them |
| Carried | All earlier classes, including the memo-98 replay and writer tests, unchanged and passing |

### Mutations ([output/mutations_output_620cefa.txt](output/mutations_output_620cefa.txt))

**41 of 41 caught on the final head `620cefa`.**
- **How they ran:** one at a time, with the watchdog running.
- **Hashes:** the SHA-256 of `basis_fidelity.py`, `funding_fidelity.py` and `intelligence_pipeline.py` was verified after every restore and at the end.
- **Labels:** `tests_output_fidelity`, `tests_funding_fidelity` and `tests_usage_basis` (226 tests).
- **Carried, unchanged:** the 29 from the bridge review (O1–O6, O8, F1–F7, F9, C1–C9, A1–A3, B1, B2).

| ID | Mutation | Result |
|---|---|---|
| L1 | Label rule off (**unsupported contradiction label restored**) | caught |
| L2 | A negated contradiction is rewritten | caught |
| L3 | An external CONTRADICTED state no longer keeps the word | caught |
| L4 | A question is relabelled | caught |
| L5 | Global word replacement in every sentence | caught |
| T1 | Unspecified-total rule off | caught |
| T2 | A pair's stated cumulative fact no longer keeps its total | caught |
| P1 | Location rule off (**cross-page/context conflation restored**) | caught |
| P2 | Only the first page group kept (refs dropped) | caught |
| P3 | Location rule not bounded to a basis pair | caught |
| P4 | Every page gets the claimed heading (conflation moved into the repair) | caught |
| P5 | A question is rewritten | caught |

**First run** ([output/mutations_first_run_979bf49.txt](output/mutations_first_run_979bf49.txt)): 38 of 41 caught.

| Survivor | Why it survived | Fix |
|---|---|---|
| **T2** | The cumulative control used a weekly/cumulative pair, which has no unspecified side, so the rule never ran | Control added in `620cefa` |
| **P5** | The question control never matched the shared-place pattern | Control added in `620cefa` |
| **L5** | The mutant itself was ineffective. It replaced the word without recording a change, and the guard returns the original text when nothing is recorded | Redefined to record its change, as a faithful global-replacement mutant |

All three are caught in the final run. The application code did not change between the runs.

### Validation at `620cefa`

**1,372 tests OK** in the four established sequential batches. Free RAM was 1.49–1.64 GB before each batch, and the watchdog logged nothing over 1,500 MB.

| Batch | Result |
|---|---|
| A | 341 OK |
| B | 415 OK |
| C | 430 OK |
| D | 186 OK |

`manage.py check`: no issues. `makemigrations --check --dry-run`: no changes.

## Isolation and limits

- **Isolation:** test databases only. No network, provider or model call; no memo regenerated; no frozen artifact edited.
- **Lexical and bounded:**
  - the label rule covers only "contradiction(s)" and "contradictory", not verbs ("contradicts") or "inconsistency";
  - the location rule covers only the "same slide/page" and "slide headed 'X'" phrases immediately followed by their citation group, and only where a basis-pair member is cited.
  Other phrasings are left as written: a missed correction rather than a wrong one.
- **Not proven live:** live behaviour still needs a post-merge sample after review.
