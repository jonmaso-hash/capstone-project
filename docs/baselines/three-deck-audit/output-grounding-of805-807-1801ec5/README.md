# OF-805, OF-806 and OF-807 corrected at `1801ec5` (memo 100, review of `d8b224c`)

**Separate, additive correction evidence.** It edits no earlier evidence, grade, memo, raw response, ledger, frozen key or fixture. Memo 100 is not regenerated or edited: these results replay its recorded reply. **This is correction evidence, not live acceptance.** No model was called.

| Item | Value |
|---|---|
| Base (reviewed execution commit) | `f34e3a399349a2d7401f66d9b60b10834047e57a`, merge of PR #285 |
| Branch | `fix/basis-grounding-of805-807`, **unmerged**, not deployed |
| Application commits | `54c4b06` (the three rules, memo-100 fixtures and regressions); `1801ec5` (an implied check dropped, two non-guessing controls) |
| Grade recorded | `f17db5c` on `docs/manychat-output-fidelity-f34e3a3` (`output-fidelity-f34e3a3/pass-a/OWNER_GRADING.md`) |
| Fixtures | `zelda_api/data/funding_fidelity/memo100.json` (raw reply and stored sections) and `memo100_payload.json` (payload as sent), from evidence `d8b224c` |

## The defects and the corrections

All three are new rules in `zelda_api/basis_fidelity.py` (`guard_basis_wording`, the last step of the memo writer's guard order: list normalisation, time, funding, basis).

| | Memo 100 stored (and replay at `f34e3a3`) | Replay at `1801ec5` | Rule |
|---|---|---|---|
| **OF-805** `business_model_analysis` | "… 140,000+ bots [S1] and 500M messages **[S2, S3]** as traction metrics (in a slide context headed 'Traction by Apr-16'), and that it operates in software [P2] (current profile, undated) at Series A stage [P1]." | "… 140,000+ bots [S1] and 500M messages **[S2]** as traction metrics (in a slide context headed 'Traction by Apr-16'), **and separately 500M messages/month [S3] on page 12 (how the figure stated without an explicit interval relates to the monthly figure needs clarification before either is relied on)**, and that it operates in software [P2] (current profile, undated) at Series A stage [P1]." | `basis_source_context` |
| **OF-806** `open_concerns` 1 | "These cannot be compared without clarification; **one or both figures may misrepresent the scale of actual activity.**" | "These cannot be compared without clarification; **how the figure stated without an explicit interval relates to the monthly figure needs clarification before either is relied on.**" | `basis_referent_judgment` |
| **OF-807** `upside_scenario` | "**These conditions are stated by the company** [S1, S2, S3] but have not been independently verified [C2, C3, C4], **so the upside reading rests entirely on the company's own assertions.**" | "**The figures** are stated by the company [S1, S2, S3] but have not been independently verified [C2, C3, C4]; **the conditions placed on them (active, paying customers, recurring revenue) are hypotheses the evidence does not state, and would need evidence.**" | `basis_condition_attribution` |

- **OF-805:**
  - **When it acts:** a figure cites both sides of one basis pair before a trailing context aside, in any of three forms: "(in a slide context headed 'X')", "(slide context: 'X')" or "(slide headed 'X')".
  - **What it does:** only the refs that context belongs to stay in that citation group. The other side's fact follows the aside with its own ref, page and context, plus the pair's clarification.
  - **What is kept:** the bot count, the following clause, the funding guard's "(current profile, undated)" and the citation order.
  - **Conditions:** every ref in the clause must be a known place; the moved refs must be one side of one pair and not narrated, and must share their citation group with the other side's ref under that context. Questions and conditions are kept.
- **OF-806:**
  - **Resolution:** "one or both figures", "both figures", "either figure" and "neither figure" continue the pair the item's previous sentence resolved to, as "the figures" already did. The pair is reset at every new line, so it never carries into another bullet.
  - **Replacement:** an error judgment in that clause becomes the pair's clarification. The sentence's other clauses stay.
  - **Kept as written:** a pair with a CONTRADICTED member, a denied judgment, a question, or a sentence citing anything outside the pair.
- **OF-807:**
  - **When it acts:** "These conditions are stated by the company [refs]" (also "those/the" and "conditions/assumptions/premises", with "stated/reported/claimed/asserted/presented/given by the company/deck/management/founders"), directly after a sentence in the same item that sets conditions ("if …").
  - **What it does:** the subject becomes "The figures", and a "rests … on the company's own assertions" consequence is dropped. The conditions the cited statements don't state (from a fixed hypothesis vocabulary: active, paying/paid, customers, recurring revenue, revenue, retention, monetisation, profitability) are named as hypotheses that need evidence.
  - **Unchanged:** the conditional sentence itself, so active/paying status and recurring revenue remain explicit "if"s.
  - **Kept as written:** no condition before it in the same item, no citation to check, every condition already in the cited statements' own words, a denial, or "these figures".

## Red, then green

- **Red** ([output/red_run_on_f34e3a3.txt](output/red_run_on_f34e3a3.txt)): the 22 new tests, run with `f34e3a3`'s application code. **10 assertion failures, 0 errors.** Every OF-805/806/807 assertion failed, through the full guard sequence, the stored-section path and the memo writer (`PipelineMemo100Tests`). The 12 controls passed, including the reproduction of the live corrections.
- **Green** ([output/modules_after_restoration_1801ec5.txt](output/modules_after_restoration_1801ec5.txt)): `tests_output_fidelity` (130), `tests_usage_basis` and `tests_funding_fidelity`, **274 OK** at `1801ec5`. The memo-96/98/99 replay and stored-section controls are unchanged and pass.

**Controls added** (`Of805SourceContextTests`, `Of806ReferentJudgmentTests`, `Of807ConditionAttributionTests`):

| Rule | Kept unchanged |
|---|---|
| OF-805 | Correctly separated page-10/page-12 wording, including memo 100's own `open_concerns` 1. An aside every cited ref belongs to. Unrelated figures (downloads). A different context name. An unknown ref. A page-12 figure alone under the aside. A separate page-12 mention before the aside (recorded limitation). A question. A condition. No basis note. A narrated moved ref |
| OF-806 | A new bullet. A different metric before it. No antecedent. A citation outside the pair (independent evidence). A question. A denial ("Nothing shows that …"). No judgment. A CONTRADICTED pair |
| OF-807 | Conditions a cited statement states (supported). No condition before it. No citation. Another bullet. "These figures …". A denial. A non-conditional sentence before it. A conditional with nothing beyond the figure |

## Replay of the recorded replies

[output/replay_memos_96_to_100_1801ec5.json](output/replay_memos_96_to_100_1801ec5.json). Each memo's recorded raw reply goes through list normalisation, time, funding and basis: once with `f34e3a3`'s basis guard (loaded from git) and once with `1801ec5`'s. Every field is compared.

| Memo | Fields | Differ from the `f34e3a3` replay | Reversed items | Second pass | Citations in order |
|---|---|---|---|---|---|
| 96 | 17 | none | same | unchanged | same |
| 97 | 17 | none | same | unchanged | same |
| 98 | 17 | none | same | unchanged | same |
| 99 | 17 | none | same | unchanged | same |
| 100 | 15 | `business_model_analysis`, `open_concerns`, `upside_scenario` (the three rows above, one rule each) | same | unchanged | same |

- **Memo 100's base replay:** the `f34e3a3` replay reproduces memo 100's stored text in all 15 fields, so the three differences are this correction alone. The live edits (`profile_undated`, `basis_overstatement`, `basis_contradiction_label`, `attribution:Pitch Deck Hunt`) are reproduced unchanged.
- **Carried probes:** the 75 probes recorded for the whole-figure, arithmetic, parenthetical, funding and source-context protections (from `output-figure-form-9d24d97`) give identical output and changes at `1801ec5` ([output/carried_probes_75_1801ec5.json](output/carried_probes_75_1801ec5.json)).

## Mutations

[output/scripts/mutate_q.py.txt](output/scripts/mutate_q.py.txt) applies each mutant to `zelda_api/basis_fidelity.py`, one at a time. It runs the three affected modules (274 tests), restores the original bytes and SHA-256 checks them before the next mutant. A mutant counts as **caught only by assertion failures**: errors are listed separately, and errors alone would be CRASH-ONLY, not coverage.

| ID | Mutation | Result |
|---|---|---|
| Q1 | "one or both figures" does not continue the pair | caught, 5 failures, 0 errors |
| Q2 | the referent-judgment rule is not applied | caught, 5, 0 |
| Q3 | a CONTRADICTED pair is neutralised too | caught, 1, 0 (`test_a_contradicted_pair_keeps_the_judgment`) |
| Q4 | a denied judgment is replaced | caught, 1, 0 (sub-case "Nothing shows that one or both figures …") |
| Q5 | the whole sentence is replaced, not only the judgment clause | caught, 5, 0 |
| Q6 | the context-aside rule is not applied | caught, 6, 0 |
| Q7 | a condition does not keep the sentence | caught, 1, 0 (sub-case "If 500M messages [S2, S3] (…) is one figure …") |
| Q8 | a narrated moved ref is moved anyway | caught, 1, 0 (`test_a_narrated_figure_is_kept`) |
| Q9 | a page-12 ref with its own mention is moved too | caught, 1, 0 (sub-case "500M messages [S2] and 500M messages/month [S3] (…)") |
| Q10 | the pair clarification is not added after the moved fact | caught, 4, 0 |
| Q11 | the condition-attribution rule is not applied | caught, 5, 0 |
| Q12 | conditions the cited statements do state are rewritten too | caught, 1, 0 (the supported S7 control) |
| Q13 | any sentence before counts as setting conditions | caught, 1, 0 (sub-case "The bots [S1] reflect active, paying customers. …") |
| Q14 | the sentence before is carried across a new list item | caught, 1, 0 (the other-bullet sub-case) |
| Q15 | the "rests on the company's own assertions" consequence is kept | caught, 3, 0 |

**15 of 15 caught by assertion failures; 0 crash-only.**
- **Runs:** chunks [1](output/mutations_chunk1.txt), [1b](output/mutations_chunk1b.txt), [2](output/mutations_chunk2.txt) and [3](output/mutations_chunk3.txt), in the foreground, with 2.13–2.26 GB free before each ([output/free_ram_before_mutation_chunks.txt](output/free_ram_before_mutation_chunks.txt)).
- **Chunk 1:** reported Q2 and Q5 as NOT-APPLIED, because their multi-line anchors used LF and the working copy is CRLF. The runner was fixed to use the file's line ending, and both were run in chunk 1b.
- **Chunk 3:** reran Q4, Q7, Q9 and Q13 with the failing sub-case printed, to show each is caught by its intended control.
- **Restores:** every restore matched, and the three guard and pipeline files are identical before and after ([pre](output/pre_mutation_hashes_1801ec5.txt), [post](output/post_mutation_hashes_1801ec5.txt)).
- **Removed before mutation:** the context rule's "sides" check, removed in `1801ec5`. The merged-mention check implies it, since a side's refs share one page and context, so no mutant of it could have been caught.

## Checks

- **Tests:** the affected modules after restoration, 274 OK.
- **Django:** `manage.py check`, no issues; `makemigrations --check --dry-run`, no changes ([output/check_and_migrations.txt](output/check_and_migrations.txt)).
- **Memory:** the watchdog logged nothing over 1,500 MB ([output/memwatch.log.txt](output/memwatch.log.txt)).
- **Not run:** no broad suite and no rerun of the earlier 73 mutations. The existing basis, funding and usage modules were run in full.

## Remaining limitations and newly seen issues (not fixed here)

- **OF-805 scope:**
  - Only a figure cited for both sides of a pair before a context aside, in the three aside wordings above.
  - A separate page-12 mention placed before the aside ("500M messages [S2] and 500M messages/month [S3] (in a slide context headed …)") is **not moved**. That would need the mention's bounds, and a control pins it unchanged.
- **OF-806 scope:** only the listed referents, the existing judgment vocabulary, and clauses split at ";".
- **OF-807 scope:**
  - It is lexical: the claim wording, the fixed hypothesis vocabulary, and a condition in the immediately preceding sentence of the same item.
  - It doesn't depend on a basis note.
- **Newly seen, preserved, not fixed (pre-existing):** slash-style citation groups such as memo 100's "[C3/S2]" are not recognised as citations by `claim_context._REF`. Every guard treats such sentences as uncited, which is why memo 100's `open_concerns` 1 resolved by its noun rather than its refs.
- **Not live:** live behaviour needs a post-merge sample after review.

**Status:** RA-109 live acceptance, RA-108, RA-114 and overall hardening remain open. No live model run, no memo regeneration, no deployment, no paid-source Pass B, no other deck, no prompt change.
