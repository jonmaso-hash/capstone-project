# Review of d30a022 addressed: fact-by-fact placement, denial and condition boundaries at `8dfe5f5` / `91a9071`

**Separate, additive evidence.** It edits nothing in `output-label-location-620cefa/`, `output-label-location-review-d30a022/`, the memo-99 run evidence or grade, any historical memo, frozen fixture, ledger or earlier accepted correction. No live model run was made.

**Status:** branch `fix/basis-label-source-context`, pushed and **unmerged**, with no PR. Main is still `64f9db5`.
- RA-109 live output acceptance stays open.
- RA-106's scoped acceptance is unchanged.
- RA-108, the P3 notes and overall hardening are out of scope and still open.

| Commit | What |
|---|---|
| `979bf49` / `620cefa` / `d30a022` | First OF-704/705 correction, its controls and evidence (reviewed: changes required) |
| `7266b3b` | The review, recorded additively (`output-label-location-review-d30a022/`) |
| `8dfe5f5` | **This correction:** `zelda_api/basis_fidelity.py`; regressions in `zelda_api/tests_output_fidelity.py` |
| `91a9071` | One label control for the "to establish" boundary (tests only; application code byte-identical to `8dfe5f5`, [output/pre_mutation_hashes.txt](output/pre_mutation_hashes.txt)) |

## The four findings and what changed

### 1. P2: each fact under its own metric, basis, page and context

A clause that places a mixed-page citation group "on the same (traction) slide" or "on a slide headed 'X'" is now restated fact by fact from the admitted items, and only when the group cites a basis-pair member.

| Part | Source and wording |
|---|---|
| Each fact | Its item's own statement. The pair's no-interval side, and statements repeating it on that page, add "with no explicit interval" |
| Placement | Under its own page and context: "on page 10, under 'Traction by Apr-16'" |
| Runs | Adjacent refs on one page share a run; runs are joined by ", and separately" |
| Clarification | When both sides of the pair are cited, the pair's existing clarification follows in parentheses, so the relation stays a clarification question |
| Subject and verb | The clause keeps them ("the company states"); a clause without one becomes "The deck states" |
| Never | A bot fact or the dated heading on page 12; a cumulative reading; a dropped ref |

**Memo-99 replay** ([output/replay_memos_96_97_98_99_91a9071.json](output/replay_memos_96_97_98_99_91a9071.json)):

> **`business_model_analysis`:** "The only operational data are traction metrics — the company states 140 000+ bots [S1] and 500M messages with no explicit interval [S2] on page 10, under 'Traction by Apr-16', and separately 500M messages/month [S3] on page 12 (how the figure stated without an explicit interval relates to the monthly figure needs clarification before either is relied on) — which confirm product usage activity but do not establish how or whether the company monetises that activity."
>
> **`supported_points`:** "- The company states 500M messages with no explicit interval [S2] on page 10, under 'Traction by Apr-16', and separately 500M messages/month [S3] on page 12 (how the figure stated without an explicit interval relates to the monthly figure needs clarification before either is relied on), suggesting material message volume on the platform at that time."

The figure text is the admitted statement ("140 000+ bots"), not the model's "140,000+". The "either 500M … or 500M/month" framing and "500M total" are gone, because the restated clause replaces them.

**Test check:** `test_every_placed_citation_supports_its_page_and_context` parses every emitted fact and checks **(fact, page, context)** for its ref against the payload. The expected fact is the item's statement, with "with no explicit interval" for the note's no-interval side. It also checks:
- ref order S2, S3 and S1, S2, S3;
- no bot fact and no heading under page 12;
- no "cumulative" in the restated clause.

### 2. P2: denials and evidence qualifications kept

The label acts only on an affirmative use. It is kept when, in the six words before "contradiction", there is:
- a denial or qualification word (no, not, cannot, unable, insufficient, lack, rather, nothing, …);
- an unasserted infinitive ("to establish/show/prove/demonstrate/confirm/determine").

| Input | Output |
|---|---|
| "The messages cannot establish a contradiction [C3, C2]." | unchanged |
| "The message figures provide insufficient evidence to establish a contradiction [C3, C2]." | unchanged |
| "Further evidence would be needed to establish a contradiction [C3, C2]." | unchanged (`91a9071` control) |
| Memo 99's "Measurement-basis contradiction … [C2, C3]." | "Measurement-basis ambiguity …" (unchanged from `979bf49`) |

### 3. P2: conditional scenarios kept by the new rules only

A condition covers the words after "if", "whether", "unless", "assuming" or "suppos(e|ing)" in the same sentence, for the **label, total and location** rules. The accepted memo-98 judgment rule is unchanged: "If the cumulative figure [C3] is presented as monthly [C2], the claim is materially overstated." is still corrected (test and probe).

| Input | Output |
|---|---|
| "If the message figures are contradictory [C3, C2], management should explain the difference." | unchanged |
| "If 500M total is the correct interpretation [S2, S3], management should explain the reporting window." | unchanged |
| "If the figures appear on the same slide [S2, S3], management should say which is current." | unchanged |

### 4. Citation order

Runs group only adjacent refs on one page and context, so the flattened order is kept.

| Input | Output |
|---|---|
| "The figures appear on the same slide [S1, S3, S2]." | "The deck states 140 000+ bots [S1] on page 10, under 'Traction by Apr-16', and separately 500M messages/month [S3] on page 12, and separately 500M messages with no explicit interval [S2] on page 10, under 'Traction by Apr-16' (how … relied on)." Refs stay S1, S3, S2; a second pass changes nothing |

All of the reviewer's probes, with the emitted text from the committed helper, are in [output/emitted_text_probes.json](output/emitted_text_probes.json).

## Replay of the actual memo replies

| Memo | Sections differing from stored | Rule changes |
|---|---|---|
| 96 | `zelda_advantage` only | as accepted |
| 97 | none | as accepted |
| 98 | the four accepted corrections, **identical** to the `aaa6e0a` replay | as accepted |
| **99** | **`open_concerns`, `supported_points`, `business_model_analysis` only** | `basis_contradiction_label`; `basis_source_location`; `basis_source_location`. Plus the five accepted funding-guard edits, unchanged |

**Memo-99 checks in the test module:**
- every other field is exactly as stored;
- citations stay in the same order;
- reversed item order gives the same output;
- a second pass changes nothing;
- the stored-text pass changes the same three sections;
- the memo writer (`PipelineMemo99Tests`) stores the repairs and leaves the other sections as memo 99 stored them.

## Evidence

### Red ([output/red_run_on_620cefa.txt](output/red_run_on_620cefa.txt))

Run against the application code at `979bf49` (= `620cefa`) before implementation: **87 tests, 17 failures**, all reproductions.
- **The reviewer's probes:** denial ×4, conditional ×3 and interleaved order.
- **Corrected expectations:** memo-99 fact/basis/page/context association, memo-99 exact text, the stored-section pass, the memo writer, rule list, and four helper location cases.

**Test corrections, recorded in `8dfe5f5`.** `POINT_AFTER`, `MODEL_AFTER`, the helper location expectations, the placement-support test and the expected rule list encoded the incomplete repair (per the review). They now encode fact-specific clauses.

### Green and focused

- **`8dfe5f5`:** 87 OK ([output/first_green_8dfe5f5.txt](output/first_green_8dfe5f5.txt)); focused related modules 300 OK.
- **`91a9071`:** 88 OK.

### Mutations ([output/mutations_output_91a9071.txt](output/mutations_output_91a9071.txt))

**49 of 49 caught on the final head `91a9071`, first run.**
- **How they ran:** one at a time, with the watchdog running.
- **Hashes:** the SHA-256 of the three guard/pipeline files was verified after every restore and at the end.
- **Labels:** `tests_output_fidelity`, `tests_funding_fidelity` and `tests_usage_basis` (232 tests).
- **Carried:** the 29 from the bridge review; C9 was re-anchored to the per-side alias line, with the same semantics.
- **Re-anchored to the revised code:** L1, L3, L4, L5, T1, T2, P1–P5.

**New mutations, each removing a new boundary or restoring the conflation:**

| ID | Mutation | Result |
|---|---|---|
| L2 | Denial/qualification boundary removed | caught |
| L6 | Label ignores conditions | caught |
| L7 | Unasserted infinitive relabelled | caught |
| T3 | Total ignores conditions | caught |
| P6 | Location ignores conditions | caught |
| P7 | Non-adjacent refs grouped (citation order changes) | caught |
| P8 | The model's shared predicate kept (semantic conflation) | caught |
| P9 | No-interval basis dropped from its fact | caught |
| P10 | Clarification omitted when both sides are cited | caught |

### Validation at `91a9071`

**1,378 tests OK** in the four established sequential batches. Free RAM was 1.27–1.80 GB before each batch, and the watchdog logged nothing over 1,500 MB.

| Batch | Result |
|---|---|
| A | 347 OK |
| B | 415 OK |
| C | 430 OK |
| D | 186 OK |

`manage.py check`: no issues. `makemigrations --check --dry-run`: no changes.

## Isolation and limits

- **Isolation:** test databases only. No network, provider or model call; no memo regenerated; no frozen artifact edited.
- **Lexical and bounded:**
  - **Denials and qualifications:** recognised by a word list in the six words before "contradiction" (plus "to establish"-type infinitives).
  - **Conditions:** recognised by an opener earlier in the same sentence, for the new rules only.
  - **Location:** the rule acts only on the "same slide/page" and "slide headed 'X'" phrases directly followed by their citation group, where a basis-pair member is cited. The model's own wording between the reporting verb and the group is replaced by the admitted facts and the pair's clarification.

  Other phrasings are left as written.
- **Not proven live:** live behaviour still needs a post-merge sample after review.
