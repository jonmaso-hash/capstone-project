# OF-903 to OF-906 corrected at `b040c23` (memo 101, graded at `f7eb39d`)

**Separate, additive correction evidence.** It edits no earlier evidence, grade, memo, raw response, ledger, frozen key or fixture. Memo 101 is not regenerated or edited: these results replay its recorded reply. **Correction evidence only; RA-109 live acceptance requires a later reviewed live sample.** No model was called.

| Item | Value |
|---|---|
| Base | `origin/main` = `066456341935d5ace32760a00788f78ec61a047a` (merge of PR #286), which is also the memo-101 execution SHA. **No commits since** |
| Branch | `fix/basis-structural-of903-906`, **unmerged**, not deployed |
| Grade recorded | `f7eb39d` on `docs/manychat-output-fidelity-0664563` (`output-fidelity-0664563/pass-a/OWNER_GRADING.md`) |
| Fixtures | `zelda_api/data/funding_fidelity/memo101.json` (raw reply and stored sections) and `memo101_payload.json` (payload as sent), from evidence `82771ef` |

## Commits and what ran at each

| Commit | What | Checks at that commit |
|---|---|---|
| `0664563` (base) | — | **Red:** the 20 new tests run with the base's application code. **12 assertion failures, 0 errors** ([output/red_run_on_0664563.txt](output/red_run_on_0664563.txt)), through the full guard sequence, the stored-section path and the memo writer (`PipelineMemo101Tests`, `_generate_memo`). All controls passed, including memo 101's upside hypothesis |
| `96f6c1a` | **The correction**, fixtures and regressions | Modules run one after another: `tests_output_fidelity` 158, `tests_usage_basis` 77, `tests_funding_fidelity` 67, OK. Replay of memos 96–101 ([96f6c1a json](output/replay_memos_96_to_101_96f6c1a.json)); 75 probes identical |
| `091075b` | Test only: parenthesis control | 158 OK. **First mutation run** over 33 mutants ([output/mutations_first_run_091075b.txt](output/mutations_first_run_091075b.txt)): 31 caught; **T6 and R3 survived** |
| `7211450` | Test only: controls for T6 and R3 | R3 caught; **T6 still survived** ([output/mutations_T6_R3_7211450.txt](output/mutations_T6_R3_7211450.txt)). This exposed that the company-subject pattern never matched a list item |
| **`b040c23`** (final application head) | A list marker is allowed before the company's own subject; T6's control replaced | **Red** for the bulleted case with `7211450`'s guard: 1 assertion failure ([output/red_run_7211450_list_marker.txt](output/red_run_7211450_list_marker.txt)). T6 and R3 caught. **All 33 mutants: 33 caught** ([output/mutations_final_all33_b040c23.txt](output/mutations_final_all33_b040c23.txt)). Modules one after another after restoration: 158 + 77 + 67 = **302 OK**. `check` and `makemigrations --check` clean. Replay of memos 96–101 and the 75 probes |

## Before and after: memo 101's recorded reply (replay)

| | `0664563` (= stored memo 101) | `b040c23` | Rule |
|---|---|---|---|
| **OF-903** `business_model_analysis` | "… the company states 140,000+ bots [S1] and 500M messages (with an ambiguity in measurement basis between a cumulative total and a monthly rate **[S2, S3]**) in a slide context headed 'Traction by Apr-16'." | "… a monthly rate **[S2]**) in a slide context headed 'Traction by Apr-16', **and separately 500M messages/month [S3] on page 12 (how the figure stated without an explicit interval relates to the monthly figure needs clarification before either is relied on)**." | `basis_source_context` |
| **OF-904** `base_scenario` (asserted) | "Taking the self-reported traction metrics at face value **[S1, S2, S3]**, ManyChat had built … by the period referenced in the 'Traction by Apr-16' slide context." | "… at face value **[S1, S2]**, ManyChat had built … in the 'Traction by Apr-16' slide context**; the deck separately states 500M messages/month [S3] on page 12 (how … relied on)**." | `basis_source_context` |
| OF-904 `upside_scenario` (conditional) | "If the self-reported figure of 500M messages/month [S3] reflects a monthly run-rate as of the 'Traction by Apr-16' slide context, …" | **unchanged:** a hypothesis inside a condition, recorded separately per the grade | — |
| **OF-905** `risk_assessment` 1 | "These figures carry different measurement bases and cannot be directly compared without clarification — **raising the possibility of metric inflation or imprecise reporting.**" | "… without clarification — **how the figure stated without an explicit interval relates to the monthly figure needs clarification before either is relied on.**" | `basis_referent_judgment` |
| **OF-906** `downside_scenario` | "If the inconsistency between **the cumulative and monthly presentations** of the 500M messages figure [C2, C3] reflects imprecise metric reporting, and if the 140,000+ bots [S1] are predominantly unpaid or inactive, …" | "… between **the unspecified-interval and monthly presentations** … [C2, C3] …" (the rest of the condition unchanged) | `basis_cumulative_presupposed` |

**Replay of memos 96–101** ([output/replay_memos_96_to_101_b040c23.json](output/replay_memos_96_to_101_b040c23.json)): each recorded reply goes through the full guard order with `0664563`'s basis guard (from git) and with `b040c23`'s.
- **Memos 96–100:** no field differs.
- **Memo 101:** exactly the four rows above differ, each by its own rule. The `0664563` replay reproduces memo 101's stored text in all 17 fields, so these four changes are this correction alone.
- **Stability:** for every memo, reversed items give the same output and changes, a second pass changes nothing, and citations stay in the same order.
- **Against `96f6c1a`:** the `b040c23` replay is identical to it.
- **Explained difference:** memo 100's replay at `0664563` differs from its stored text in `business_model_analysis`, `open_concerns` and `upside_scenario`. Those are PR #286's accepted corrections, since memo 100 was generated before #286. This branch adds nothing further to memo 100.
- **Probes** ([output/carried_probes_75_b040c23.json](output/carried_probes_75_b040c23.json)): the 75 carried probes for the whole-figure, arithmetic, parenthetical, funding and source-context protections are **identical**.

## The correction (`zelda_api/basis_fidelity.py`)

- **Context shared across sources (OF-903, OF-904):**
  - **What it reads:** the existing context split, which covers both sides of one pair cited in one citation group before a context naming only one side's source, now also reads context phrases outside parentheses ("in a slide context headed 'X'", "in the 'X' slide context", "within a 'X' slide heading"). That includes citations inside an earlier parenthesis.
  - **What stays unchanged:** the citation identity checks (every ref a known place; moved refs one side of one pair; not narrated; sharing a group with the other side's ref under that context), the denial and hedge checks, and the question and condition checks.
  - **What changed:**
    - The other side's fact is placed only where the context phrase ends its clause. That is what made a sentence without a reporting verb unsafe ("… in the 'X' slide context is the headline figure" is kept).
    - A reporting verb before the moved refs must have the company as its subject; "self-reported" is an adjective, not a verb, and a list marker may precede the subject.
    - A recorded narrator's name in the clause keeps it.
    - Without a reporting verb, the fact is its own clause: "; the deck separately states …".
  - **Mutation note:** this replaces the earlier requirement of a company reporting verb, whose mutant (R4) is retired. The clause-end, narrator-name, hyphen and company-subject checks are each mutated (T2, T3, T4, R3).
- **"These figures" (OF-905):**
  - **Resolution:** "these figures" (and "those figures/numbers/metrics") continues the pair the item's previous sentence resolved to.
  - **Segments:** sentences are split at ";" and at dashes. A judgment after a dash continuing that referent is replaced by the clarification, and the clause before the dash stays. An independent ";" clause needs its own referent.
  - **Dispatch:** the judgment-rule dispatch uses the same segments, so a sentence mixing an ungoverned judgment stays with the judgment rule.
  - **Protections carried:** a CONTRADICTED pair, a denial, a question and a citation outside the pair keep the sentence.
- **Cumulative presupposition (OF-906):**
  - **What it changes:** "the cumulative and monthly …" (or "the monthly and cumulative …", also weekly, daily, yearly, annual) is tied to a pair through its own following citation group, or else through the pair the sentence resolved to. When that pair admits no cumulative fact, "cumulative" becomes "unspecified-interval", inside a condition too, because the phrase presupposes rather than supposes.
  - **What is kept:** "if the figure is cumulative", "a cumulative total or a monthly rate", questions, another metric's or another pair's figures, and a pair with an admitted cumulative side.

### Controls (all through the full sequence or the basis helper; see `Of903SharedContextTests`, `Of905TheseFiguresTests`, `Of906CumulativePresuppositionTests`)

| Rule | Kept as written |
|---|---|
| OF-903/904 | Memo 101's upside hypothesis. A condition over shared refs. A narrator's listing with no verb. A third party's verb ("An analyst lists"). Mid-clause context. A denial. A hedge. Correctly separated page-10/page-12 wording. Correctly attributed dates (refs after the context). A question. A context phrase inside a non-context parenthesis, with and without a full stop |
| OF-905 | A new bullet. A different metric before it. No antecedent. A citation outside the pair. A denial. A question. No judgment. A judgment in an independent ";" clause. A CONTRADICTED pair |
| OF-906 | A hypothesis ("if the 500M figure is cumulative"). An alternative ("a cumulative total or a monthly rate"). A question. Another metric's figures. A pair with an admitted cumulative side ("3M messages to date") |

Positive controls also cover: a bulleted company statement, a no-verb assertion, "self-reported" figures, and a governed whole-sentence judgment.

## Mutations

[output/scripts/mutate_t.py.txt](output/scripts/mutate_t.py.txt) applies one mutant at a time to `zelda_api/basis_fidelity.py`, runs the three affected modules (302 tests), and restores the original bytes with a SHA-256 check before the next. **A mutant counts as caught only by assertion failures.**

| Group | IDs | Final run at `b040c23` |
|---|---|---|
| New, memo 101 | T1 (unparenthesised context phrases not read), T2 (fact placed mid-clause), T3 (narrator name ignored), T4 ("self-reported" read as a verb), T5 (no clause of its own without a verb), T6 (phrase inside a non-context parenthesis read), T7 ("these figures" not a referent), T8 (dash not a segment boundary), T9 (";" clause inherits the referent), T10 (cumulative rule off), T11 (admitted cumulative neutralised), T12 (own citation group ignored), T13 (question neutralised) | **13 of 13 caught** |
| Carried, integration (review of `1801ec5`) | R1, R2, R3, R5, R6 (R2 and R3 re-anchored; R4 retired, see above) | **5 of 5 caught** |
| Carried, OF-805..807 | Q1–Q15 (Q4, Q5 and Q7 re-anchored to the moved code, same meaning) | **15 of 15 caught** |

- **Total: 33 of 33 caught, 0 crash-only, 0 survived.** No run had any errors.
- **Restores:** every restore matched; the [pre](output/pre_mutation_hashes_b040c23.txt) and [post](output/post_mutation_hashes_b040c23.txt) hashes are identical.
- **Memory:** free RAM was 1.40–2.04 GB before each chunk ([output/free_ram_before_mutation_chunks.txt](output/free_ram_before_mutation_chunks.txt)).
- **Survivors along the way:** at `091075b`, T6 and R3 survived because their controls were also kept by other checks. `7211450` and `b040c23` added independent controls. T6's investigation also found the list-marker gap, which was fixed in `b040c23` (red first).
- **Run note:** two chunks of the final run exceeded the 10-minute foreground limit and finished in the background. The next chunks refused to start until the pre-run hash matched, so no runs overlapped, and the restore was verified before continuing.

## Memory

`tools/memwatch.ps1` (1,500 MB threshold) was **restarted and verified** (its start line logged) before the first test, and ran throughout. Nothing crossed it ([output/memwatch.log.txt](output/memwatch.log.txt)). All steps ran serially.

## Remaining limitations (not fixed here)

- **Lexical extents:**
  - The context phrases recognised are a parenthesised aside, "in/on/within/under a/the slide/page (context) headed/titled/: 'X'" and "in/on/within/under a/the 'X' (slide) context/heading".
  - Also fixed lists: the reporting verbs, denial words, hedges, "one or both / either / neither / these / those figures|numbers|metrics", the judgment vocabulary, and "the cumulative and/or/vs monthly|weekly|daily|yearly|annual …".
  - Other phrasings keep their text (the conservative direction).
- **Not moved:** a page-12 figure with its own mention, a context phrase inside a non-context parenthesis, and a context phrase mid-clause. These are kept by design; controls pin them.
- **OF-904 upside:** the conditional hypothesis is kept, per the grade.
- **Wording:** "unspecified-interval" is this correction's wording for the no-interval side in a coordinated phrase.
- **Not in scope:** OF-907 (P3 merged "500M messages [S2, S3]" citations with no place claimed) is not addressed.
- **Pre-existing, unchanged:**
  - `_judgment()` has no denial check of its own when a judgment is not governed by a referent.
  - Slash citations ("[C3/S2]") are not recognised by `claim_context._REF`.
- **Not live:** live behaviour requires a later reviewed live sample.

**Status:** RA-109 live acceptance, RA-108, RA-114 and overall hardening remain open. No merge, deployment, model call, memo regeneration, other deck or paid-source Pass B.
