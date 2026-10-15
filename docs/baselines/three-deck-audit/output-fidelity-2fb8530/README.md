# Memo-98 output fidelity: UB-604, NP-603, NP-604 at `2fb8530`

**Separate, additive evidence.** It edits no earlier evidence folder, run ledger, grading, memo, answer key, protocol or frozen fixture. Memo 98 is not edited or regenerated: these checks replay its **recorded** reply. No live model run was made.

**Status:** branch `fix/usage-basis-output-fidelity` (from `d276918`; main is still `d276918`), pushed and **unmerged**, with no PR.
- RA-109 live **output** acceptance stays open until this correction is reviewed and a later live run is graded.
- RA-106's scoped acceptance is unchanged.
- Still open: RA-108 (UB-605), overview coverage (UB-606), the P3 wording notes, and overall hardening. They are out of scope here.

| Commit | What |
|---|---|
| `0dd8e91`, `feeb0c7` (`docs/manychat-usage-basis-d276918`) | Memo-98 run evidence and its grade (partial pass) |
| `2fb8530` | **This correction**:<br>• new `zelda_api/basis_fidelity.py`;<br>• `zelda_api/funding_fidelity.py`: three rules;<br>• `zelda_api/intelligence_pipeline.py`: applies the basis guard after the funding guard;<br>• `zelda_api/tests_output_fidelity.py`;<br>• fixtures `data/funding_fidelity/memo98*.json`;<br>• CI entry |

## What changed

| Finding | Rule | Memo 98, recorded reply → output at `2fb8530` |
|---|---|---|
| **UB-604** | `basis_fidelity`, active **only** when the grounded context carries a measurement-basis note:<br>• **judgment:** a statement about the noted bases (it names cumulative, monthly, interval or run rate, or cites a noted ref) that calls a figure overstated, inflated, exaggerated, misleading, misrepresented, incorrect, erroneous or wrong is replaced by the neutral clarification, worded from the pair's admitted bases, with its citations kept;<br>• **referent:** a definite "the cumulative figure/total/count/…" becomes "the figure stated without an explicit interval", unless an admitted fact of the pair is itself cumulative.<br>Questions are kept. | "If the cumulative figure is being presented as a monthly figure, the key traction claim is materially overstated." → "How the figure stated without an explicit interval relates to the monthly figure needs clarification before either is relied on." |
| **NP-603** narrative | `_narrative_owner`: a sentence citing only one narrator's funding refs, in the clause that names the funding narrative and no traction figure, gives "the company (has) put forward/states/…" back to the narrator | "…the fundraising narrative **the company** has put forward…" → "…**Pitch Deck Hunt** has put forward…" |
| **NP-603** total | `_unsupported_total`: "total" before "(amount) raised/funding/capital" is dropped where the clause states the narrated figure and the admitted statement has no total or to-date wording. Questions are kept | "$23.1M as the **total** amount raised [S4]" → "$23.1M as the amount raised [S4]" |
| **NP-604** | `_funding_not_runway`, in statements **and questions**: "runway/operate/operating/survive/sustain … against/on/from/with/out of <phrase naming funding>" keeps the denominator and names it: "— from the dated cash and burn alone, since <phrase> is historical funding, not cash on hand". It runs after the attribution rule, and never inserts a narrator | "how long the company can operate on the capital narrated as raised [S4]" and "runway against the $23.1M (per Pitch Deck Hunt) narrated as raised [S4]?" → "… — from the dated cash and burn alone, since … is historical funding, not cash on hand [S4]" |

**Kept as written:**
- questions, including "Is the 500M messages figure a cumulative total or a monthly run rate …?" and "Is a new fundraising round …?";
- indefinite conditional scenarios ("… rather than a cumulative total");
- `information_readiness` "cumulative vs. monthly" (a P3, not in scope);
- `open_concerns` "inconsistency" (a P3);
- other metrics' "overstated";
- company-owned funding narratives and the company's own bot/message statements;
- explicit stated totals;
- dated-cash questions and "did the funding occur" questions.

The word "cumulative" is never replaced on its own, no citation is dropped, and nothing reads source text: only the note's refs, the admitted items' statements and the narrator metadata.

**No schema change.** `makemigrations --check` reports no changes.

## Evidence

### Red on `d276918` ([output/red_run_on_d276918.txt](output/red_run_on_d276918.txt))

Application code was identical to `d276918`. Result: **24 tests, 3 failures and 22 errors.** The failures are the three funding rules; the errors are the missing `basis_fidelity` module, including the memo-98 replay that imports it. The funding controls passed on the old code.

**Test corrections after red** (recorded, not hidden):
1. **Explicit cumulative case:** with an admitted cumulative fact, the clarification now reads "How the cumulative figure relates to the monthly figure …". It is worded from the actual bases, not "without an explicit interval".
2. **Funding-question case:** the existing attribution rule correctly adds "(per Pitch Deck Hunt)" to the uncredited amount first, and the expected string now includes it ([first_green_attempt.txt](output/first_green_attempt.txt)).
3. **Two over-reaches caught by the existing `tests_funding_fidelity` suite** ([existing_tests_caught_overreach.txt](output/existing_tests_caught_overreach.txt)), both fixed in the code before commit:
   - the narrative rule rewrote "and **the company** reports 140,000+ bots"; it is now clause-scoped and skips traction clauses;
   - the total rule stripped "total" from a question; it now keeps questions and acts only in the clause stating the narrated figure.
4. **Added after red:** a memo-writer test (`PipelineAppliesTheRulesTests`) and a dated-cash/funding control.

### Regressions ([`zelda_api/tests_output_fidelity.py`](../../../../zelda_api/tests_output_fidelity.py), 25 tests)

| Class | Covers |
|---|---|
| `Memo98ReplayTests` | Memo 98's recorded reply through the time, funding and basis guards:<br>• the four corrected clauses are exact;<br>• every other field is **byte-equal to the stored memo**;<br>• valid questions and scenarios are kept;<br>• citations are preserved in order in every field;<br>• a second pass changes nothing;<br>• reversed item order gives the same output;<br>• only the expected rule families fire |
| `PipelineAppliesTheRulesTests` | The memo writer (`_generate_memo`), with the recorded reply as the model's answer, stores the corrected sections; the upside scenario and `zelda_advantage` are stored unchanged |
| `BasisGuardTests` | Referent replaced / kept with an admitted cumulative fact; judgment replaced with refs kept; an explicit cumulative fact does not license an overstatement; five kept controls; inactive with no note; idempotent; list markers and numbering kept |
| `FundingSourceAndRunwayTests` | Narrative to narrator; company-owned and mixed refs kept; unsupported total dropped and a stated total kept; funding never a runway denominator even with a dated cash balance; four valid cash/funding questions kept; idempotent |

### Replay of memos 96, 97 and 98 at `2fb8530` ([output/replay_memos_96_97_98.json](output/replay_memos_96_97_98.json))

Each run's recorded reply, from committed evidence, was put through the current guards and compared with what that run stored. This is a supplementary deterministic check, not live evidence.

| Memo | Sections differing from stored | New rules that fired |
|---|---|---|
| 98 | exactly `risk_assessment`, `supported_points`, `what_would_change_the_picture`, `questions_for_management` | `basis_overstatement`, `unsupported_total`, `narrator_narrative`, `funding_not_runway` ×2 |
| 97 | none | none |
| 96 | `zelda_advantage` only: the previously **accepted** FF-405 provenance correction (merged in #281 after memo 96 was generated) | none |

### Mutations ([output/mutations_output.txt](output/mutations_output.txt))

**16 of 16 caught on the committed code.**
- **How they ran:** one at a time, in the foreground, with the watchdog running. Each file's SHA-256 was verified after restore.
- **Labels:** `tests_output_fidelity`, `tests_funding_fidelity` and `tests_usage_basis` (169 tests).
- **The mutations:**
  - **O1–O8 (basis guard):** judgment off; judgment in questions; judgment unrelated to the bases; citations dropped; admitted cumulative ignored; referent off; active without a note; memo writer skips the guard.
  - **F1–F7, F9 (funding rules):** narrative off; clause scoping removed; ownership check removed; total off; total in questions; stated total stripped; runway rule off; runway rule removed from the rule list.

**First run** ([output/mutations_first_run.txt](output/mutations_first_run.txt)): 16 of 17 caught. **F8** ("a cash balance treated as funding") **survived**, because the cash exclusion was unobservable: the denominator must already name funding. The check was removed from the code rather than kept, and the docstring says so. The final run was repeated on the committed code without F8.

### Validation at `2fb8530`

**1,315 tests OK** in the established four sequential batches. Batch A now includes the 25 new tests. Free RAM was 1.22–1.61 GB before each batch, and the watchdog logged nothing over 1,500 MB.

| Batch | Result |
|---|---|
| A (output fidelity, funding fidelity, grounded context, memo, presentation, CI manifest) | 284 OK |
| B (claim path including usage basis) | 415 OK |
| C (`zelda_api.tests`) | 430 OK |
| D (authorization, panels, library, notifications, valuation, retrieval, overview identity) | 186 OK |

`manage.py check`: no issues. `makemigrations --check --dry-run`: no changes. `tests_output_fidelity` was added to the blocking CI job, and `pages.tests_ci_manifest` passes.

## Isolation and limits

- **Isolation:**
  - Test databases only.
  - The memo-98 fixtures hold the payload as sent (normalised items and the note) plus the model reply and stored sections; the build script asserts no chunk text, contact details, key text or canary.
  - No network, provider or model call; no memo regenerated; no frozen artifact edited.
- **Detection is lexical:**
  - judgment words listed above, basis words or a noted ref in the same sentence;
  - a definite "the cumulative <figure word>";
  - "the company <verb>" in the narrative clause;
  - runway/operate verbs with a funding-naming denominator in the same clause.

  Paraphrases outside these shapes are not caught.
- **Clarification scope:** the clarification is worded from the first noted pair only.
- **Not proven live:** whether a newly generated memo avoids or is corrected for these shapes needs a separate post-merge live run, with new rows, after review.
