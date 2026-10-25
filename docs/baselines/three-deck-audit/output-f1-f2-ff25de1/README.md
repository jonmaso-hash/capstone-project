# F-1 / F-2 correction (ManyChat memo 104, post-merge run at 5120190)

Additive correction evidence for branch `fix/funding-word-heading-scope-f1-f2`. The completed run stays immutable: memo 104, document 3146, the eight-call ledger and the run evidence (`f73bef5` on `docs/manychat-output-fidelity-5120190`) were not touched. No memo was regenerated, no model was called, no database was opened or repaired, no MFA was changed, the worker stayed stopped, and nothing was merged or deployed. All validation below is my own, run locally; none of it is independent review. **RA-108, RA-109, RA-114, Q-2–Q-4 and overall acceptance stay open.** The completed browser checks show access, not report-content acceptance.

## Commits

| Commit | Content |
|---|---|
| `ff25de158f72e2debc7937c824fdb6a77a34d1b1` | app, tests and memo-104 fixtures; **validation head** (parent `5120190`) |
| this commit | evidence only (this folder) |

Diff `5120190..ff25de1` ([output/diff_stat_5120190_ff25de1.txt](output/diff_stat_5120190_ff25de1.txt)): 5 files, +678 / −2.

| File | Change |
|---|---|
| `zelda_api/funding_fidelity.py` | `_FIGURE_TAIL`: `\b` after the alternatives (+2 comment lines) |
| `zelda_api/basis_fidelity.py` | new rule `_heading_scope` (`basis_heading_scope`), its two patterns, a docstring entry, one line in `guard_basis_wording` |
| `zelda_api/tests_output_fidelity.py` | 5 new classes, 22 tests |
| `zelda_api/data/funding_fidelity/memo104.json`, `memo104_payload.json` | memo 104's raw reply, stored memo and sent payload, copied from `f73bef5` |

## F-1: "reportedly" split by the funding attribution

**Cause.** `_FIGURE_TAIL = (?:\s+(?:in\s+)?(?:funding|raised|figure|total|listed|reported))*` had no word boundary, so after "$23.1M" it matched " reported" inside "reportedly", and `_attribute` inserted " (per Pitch Deck Hunt)" there.

**Audit of the pattern.** All six alternatives had the same prefix problem: "funding"/"fundings", "raised"/"raisedness", "figure"/"figures", "total"/"totalling", "listed"/"listedness", "reported"/"reportedly"/"reporters". The other alternations in `funding_fidelity.py` already end on `\b`, on required whitespace, or are used with `fullmatch` (`_JOINER`: "with" cannot fullmatch "without").

**Fix.** `(?:\s+(?:in\s+)?(?:funding|raised|figure|total|listed|reported)\b)*`. A complete-word tail is still part of the figure's phrase; a longer word is not, so the attribution follows the figure and the word stays whole.

| | Text |
|---|---|
| Raw reply | `- What is the composition of the $23.1M reportedly raised [S4] — how many rounds, at what valuations, and from which investors?` |
| at 5120190 (stored) | `… the $23.1M reported (per Pitch Deck Hunt)ly raised [S4] — …` |
| at ff25de1 | `… the $23.1M (per Pitch Deck Hunt) reportedly raised [S4] — …` |

The word, question, amount, citation and Pitch Deck Hunt attribution are kept; a second pass changes nothing. Complete-word tails are unchanged ("$23.1M raised (per Pitch Deck Hunt) [S4]", "in funding", "funding figure", "total", "listed", "reported", "reported raised").

## F-2: page 10's heading spread to page 12's figure

**Cause.** Memo 104's sentence names the heading in a form no rule read ("— contextualised under a slide heading 'X'", after the list's closing dash), so nothing scoped it. Removing S3 from its group alone would not do: "500M messages/month" would then be cited to page 10's S2.

**Fix: new rule `heading`.** When a heading phrase closes a figure list (a participle such as "contextualised", "presented", "shown" straight after the list's closing dash, or after the comma ending "the company states <list>"), the list cites both sides of one basis pair, and only some of its refs carry the named heading, the list is restated fact by fact from the admitted items, like the existing location rule: each figure keeps its own ref, the heading follows only the refs whose items carry it, page 10's side says "with no explicit interval", page 12's keeps "/month", and nothing is made cumulative or dated. A "(see consistency note below)" pointer is kept word for word; without one the pair's clarification follows. The trailing clause keeps its place (the list's closing dash is restored before it).

| | Text |
|---|---|
| at 5120190 (stored) | `The only indicators of commercial activity are the company's self-reported traction figures — 140,000+ bots [S1] and 500M messages or 500M messages/month (see consistency note below) [S2, S3] — contextualised under a slide heading 'Traction by Apr-16', but these figures are undated as counts and have not been independently verified [C2, C3, C4].` |
| at ff25de1 | `The only indicators of commercial activity are the company's self-reported traction figures — 140 000+ bots [S1] and 500M messages with no explicit interval [S2] on page 10, under 'Traction by Apr-16', and separately 500M messages/month [S3] on page 12 (see consistency note below) — but these figures are undated as counts and have not been independently verified [C2, C3, C4].` |

Kept: "self-reported", "have not been independently verified [C2, C3, C4]", every ref (S2 and S3 now each cite alone). One wording change to note: the restated figures use the admitted statements' own form ("140 000+ bots"), as the location rule does, instead of the memo's "140,000+".

**Left unchanged (controls, each a test case):** a correctly scoped list ("— 140,000+ bots [S1] and 500M messages [S2] — contextualised under …, but page 12 states 500M messages/month [S3]"); a heading mention that assigns no context to the other figure; denials ("— not all contextualised …", "and not 500M messages/month", "does not state"); conditions (also with the company's own subject), a hedge ("possibly", "may be"), a question; another fact, figure, interval, ref or aside in the list ("revenue of $10M", "250M messages/month", "500M messages/day", "[S2, S3, S4]", "(unaudited)", another pair's "40 staff [S9]"); a mid-clause phrase ("… 'X' that dates them"); a narrator's figures, another speaker, and no source named ("The figures — …"); a heading neither figure carries. Known limit: "The figures — …" (no own source named) keeps the defect, the same conservative choice the context rules make.

## Validation

**Red on 5120190** ([output/red_on_5120190.txt](output/red_on_5120190.txt)): the two guard modules put back to 5120190 with the new tests: 22 tests, **30 failures** across the F-1 and F-2 regressions; the files were restored and their SHA-256 checked ([output/guard_hashes_ff25de1.txt](output/guard_hashes_ff25de1.txt)).

**Tests at ff25de1** (serial, one module per process, memory watchdog at 1500 MB, free RAM 1.54–1.74 GB before each, [output/suite_ram.txt](output/suite_ram.txt)):

| Module | Result |
|---|---|
| `zelda_api.tests_output_fidelity` | 281 OK (259 + 22 new) |
| `zelda_api.tests_usage_basis` | 77 OK |
| `zelda_api.tests_funding_fidelity` | 67 OK |
| `zelda_api.tests_claim_context_dates` (also imports the funding guard) | 25 OK |

**450 OK.** `manage.py check` and `makemigrations --check --dry-run` exit 0 ([output/check.txt](output/check.txt)).

**Frozen memos 96–104 through the full guard order** (list normalisation → time → funding → basis; guards at 5120190 loaded from git vs ff25de1; [output/replay_memos_96_to_104_ff25de1.json](output/replay_memos_96_to_104_ff25de1.json)):

| Memo | Sections differing from the 5120190 replay |
|---|---|
| 96–103 | none |
| 104 | `business_model_analysis` (`basis_heading_scope`), `questions_for_management` (same `attribution:Pitch Deck Hunt` rule, whole-word output) |

The 5120190 replay reproduces stored memo 104 exactly. Every memo: reversed item order gives the same output and rules, a second pass changes nothing, every citation names a supplied ref. No additional section changed.

**Established preservation controls.** The 75 carried probes of the earlier rounds are identical to their 9fd0f35 output ([output/carried_probes_compare.txt](output/carried_probes_compare.txt)). The ten replay cases recorded with the run (memo 103's OF-1102/OF-1103 sentences, memo 104's sentences, five controls: denial, unrelated consequence, unknown trailing clause, date as hypothesis, qualifier and attribution without a heading) plus the F-1 and F-2 cases, 56 in all, with exact outputs at both commits: [output/exact_before_after_ff25de1.json](output/exact_before_after_ff25de1.json). Only memo 104's two sentences, the six longer-word tails and the nine F-2 corrections differ; memo 103's graded sentences and the five controls are byte-identical to 5120190. All idempotent and order-free.

**Targeted mutations** ([output/mutations.txt](output/mutations.txt), [output/mutations_h4_h8_rerun.txt](output/mutations_h4_h8_rerun.txt)): one mutant at a time, `tests_output_fidelity` + `tests_funding_fidelity` (348 tests), bytes restored and hashed after each. Caught means assertion failures.

| ID | Mutant | Result |
|---|---|---|
| F1 | tail alternatives unbounded (the 5120190 pattern) | caught, 16 failures |
| F2 | only "reported" bounded | caught, 10 |
| H1 | heading rule not applied | caught, 15 |
| H2 | any subject (narrator, analyst, no source) | caught, 3 |
| H3 | hedged or denied subject | caught, 1 |
| H4 | heading inside a condition | **survived first run**; caught, 1, after adding a condition control with the company's own subject |
| H5 | mid-clause phrase | caught, 1 |
| H6 | other facts, figures, asides in the list | caught, 6 |
| H7 | a list none of whose refs carries the heading | caught, 1 |
| H8 | refs outside the pair may move | **survived first run** (the only such control was narrated); caught, 1, after adding another pair's "40 staff [S9]" control |
| H9 | the note pointer replaced by the clarification | caught, 4 |
| H10 | the closing dash not restored | caught, 6 |
| H11 | page 12's ref placed under the heading | caught, 14 |

13 of 13 caught after the two controls were added (both are in `ff25de1`; the first full run predates them).

## Reproduce

Scripts in [output/scripts/](output/scripts/): `t.sh` (CI env test runner, labels required), `py.sh` (Django script runner, refuses below 0.9 GB free), `m104.py`, `replay.py`, `carried_probe.py` + `cmp_probes.py`, `exact.py`, `cases.py`, `mutate_f12.py`, `probe_words.py`.
