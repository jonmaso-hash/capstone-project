# OF-1102 / OF-1103: page 10's heading kept off page 12's figure (memo 103)

**This is correction evidence only, not live acceptance.**
- No model call was made. Memo 103 was not regenerated, and Q1–Q7 were not repeated.
- This folder is additive. It changes nothing in memo 103's run (`4ee3639`), its grade (`e967274`), any earlier evidence folder, frozen fixture, answer key, grade or recorded memo.
- All validation below is **Claude's own (the author's), not independent**. It awaits independent review.

**Where the change is:**
- **Branch:** `fix/basis-date-transfer-of1102-1103`, from `origin/main` at `c6c3d1b9b1fe8b5e32d856c64a5b535a986684a0` (PR #288's merge). `origin/main` had no later commits, so no application change after PR #288 bears on this fix.
- **Commits:**
  - `ad7d85aeb546639cb76fe904c7c360dd7e7cfff5`: application, tests and memo-103 fixtures;
  - `4440bdc8fdf2207929920ce8f2e65844ff138559`: tests only (controls added before the mutation pass);
  - `b16d3c1942ebd5b28af6296b7fd52928ad8582f3`: tests only (J6 control); the final head for validation.
- **Guard:** `zelda_api/basis_fidelity.py`, sha256 `22312953aec3922f66ad77ac257ecc413e6ce065003507d24db56cc889bd4727` (working copy, CRLF), unchanged since `ad7d85a`.
- **Fixtures (new):** `zelda_api/data/funding_fidelity/memo103.json` (raw reply and stored fields) and `memo103_payload.json` (payload as sent), written from `4ee3639`'s `09b`, `09_memo` and `09a` by [output/scripts/make_fixtures.py.txt](output/scripts/make_fixtures.py.txt).

## Reproduced first (at c6c3d1b)

The new tests, run against the **unchanged** guard at `c6c3d1b`, give **22 assertion failures and 0 errors** out of 20 tests ([output/red_run_new_tests_on_c6c3d1b.txt](output/red_run_new_tests_on_c6c3d1b.txt)).
- They include memo 103's raw reply through the full time → funding → basis sequence, the stored sections through the basis guard, and the memo writer (`_generate_memo` with a mocked model call).
- At `c6c3d1b`, the replay of memo 103's raw reply equals the stored memo in every field, so the guards never touched either sentence.

**Why the merged rules missed them:**
- **OF-1102:** the source-context rule refused the sentence for two independent reasons. Either alone was enough:
  - "without independent verification" put "without" (a denial word) and unknown words into the clause head;
  - the closing ", with Pitch Deck Hunt listing $23.1M in prior funding [C1, S4]" meant the context phrase did not end its clause.
- **OF-1103:** no rule read a heading named in a condition's **consequence** ("…, ManyChat would represent … at the time of the 'Traction by Apr-16' slide"). The condition rule reads only a heading inside the antecedent.

## Changed outputs ([output/memo103_changed_outputs.txt](output/memo103_changed_outputs.txt))

| Field | At `c6c3d1b` (= stored) | At `b16d3c1` |
|---|---|---|
| `base_scenario` (OF-1102) | Taking the self-reported traction at face value without independent verification [S1, S2, S3], the company had deployed a meaningful bot platform by the period referenced in the 'Traction by Apr-16' slide context, with Pitch Deck Hunt listing $23.1M in prior funding [C1, S4]. | Taking the self-reported traction at face value without independent verification [S1, S2], the company had deployed a meaningful bot platform by the period referenced in the 'Traction by Apr-16' slide context, with Pitch Deck Hunt listing $23.1M in prior funding [C1, S4]; the deck separately states 500M messages/month [S3] on page 12 (how the figure stated without an explicit interval relates to the monthly figure needs clarification before either is relied on). |
| `upside_scenario` (OF-1103) | If the company's self-reported 140,000+ bots [S1] and 500M messages/month [S3] are accurate and the per-month figure is the correct basis, ManyChat would represent a platform with significant throughput at the time of the 'Traction by Apr-16' slide — consistent with a network-effect-driven software business approaching scale. | … at the time of the 'Traction by Apr-16' slide ('Traction by Apr-16' heads page 10, which states 140 000+ bots [S1]; the deck states 500M messages/month [S3] on page 12, with no date context) — consistent with a network-effect-driven software business approaching scale. |

- **Rules:** `basis_source_context` (base) and the new `basis_consequence_context` (upside).
- **Preserved:**
  - in the base: the qualifier "without independent verification", the Pitch Deck Hunt funding clause with its narrator and citations, and the second sentence;
  - in the upside: the whole condition (accuracy and basis), the consequence, the dash clause and the second sentence.
- **Unchanged:** the other 15 fields are exactly as stored, including the four funding-guard edits.

## The fix (`ad7d85a`)

**OF-1102, in the source-context rule:**
- **Verification qualifier.** An allowlisted verification qualifier is removed before the denial, hedge and own-head checks, and stays in the output. The allowlist:
  - "without (any) independent / external / third-party verification / confirmation / corroboration";
  - "not (yet) (been) independently verified / confirmed";
  - "(as yet) unverified".

  Any other "without" or "not" still denies, and a hedge before the qualifier ("possibly without …") still hedges.
- **Closing clause.** A closing ", with …" or ", alongside …" clause no longer blocks the rule. The moved fact then follows the whole sentence as "; the deck separately states …", so the clause keeps its own subject.
  - It must be about something else: no ref of any pair, condition, page, slide, heading or quoted heading, and none of the pair's figures, noun or bases.
  - Anything else keeps the sentence.
- **Time phrases.** "as of / at the time of / by the time of the 'X' slide (context|heading)" now names the heading, as the existing in/on/under phrases do.

**OF-1103, a new consequence rule** (`_consequence_context`, run right after the condition rule):
- **Scope:** a condition that opens the sentence ("If", "Assuming", "Supposing"). Its antecedent runs to the first top-level comma; commas inside a citation group, inside a number ("140,000+") and before a further condition (", and if …") don't end it.
- **What the antecedent may say:** every word must be the company's own source, a placing word, a word or figure of the cited statements, the pair's category or bases, or an allowlisted accepting word: accurate, correct, reliable, valid, true, right, taken, accepted, read or treated at face value, as stated / reported / presented / given, basis, per. Any other word is a hypothesis of the condition's own, so the sentence is kept. That covers "dates from", "reflects a monthly run-rate as of …", "April 2016" and a heading.
- **When it acts:** the consequence names a heading, and the antecedent cites a page-12 pair side with no heading of its own (and may also cite refs under the heading). Then a parenthesis goes right after the phrase: "('X' heads page N, which states <those refs' statements>; the deck states <page-12 statements and refs> on page M, with no date context)". The condition and consequence are never removed or rewritten.
- **When it is kept:** a question; a denial or attribution in the consequence; a citation inside the consequence; a narrator named, or a narrated ref; a heading on more than one page; a condition later in the sentence.
- **Idempotent:** a second pass sees the parenthesis and adds nothing.

## Validation (Claude's own; not independent)

| Check | Result |
|---|---|
| Red | The final tests (`b16d3c1`) against `c6c3d1b`'s guard give **23 assertion failures, 0 errors** out of 259 tests ([output/red_run_final_tests_on_c6c3d1b.txt](output/red_run_final_tests_on_c6c3d1b.txt)). The guard file was then restored from a byte copy and its hash checked |
| Green at `b16d3c1` | **259 + 77 + 67 = 403 OK**: `tests_output_fidelity` 259, `tests_usage_basis` 77, `tests_funding_fidelity` 67, run one at a time, with free RAM 1.42–1.45 GB ([output/modules_b16d3c1.txt](output/modules_b16d3c1.txt)). `check` and `makemigrations --check --dry-run` exit 0 ([output/check_and_migrations_b16d3c1.txt](output/check_and_migrations_b16d3c1.txt)) |
| New tests | **`Memo103ReplayTests` (12):**<br>• fixture identity;<br>• each repair exactly, with the qualifier and funding clause kept;<br>• hypotheses and correct citations kept;<br>• every other field as stored;<br>• citations changed only where corrected;<br>• supplied refs only;<br>• idempotent and order-stable;<br>• only the expected rules fire;<br>• memos 96–102 get no consequence rule.<br>**`Memo103StoredSectionsTests` (1), `PipelineMemo103Tests` (1):** the memo writer.<br>**`Of1102Of1103DateTransferTests` (7):** 8 asserted variants and 6 consequence variants corrected; 27 controls kept (12 asserted, 15 conditional). The memo-101 OF-904, memo-102 OF-1003 and memo-102 OF-1004 repairs are re-checked under memo 103's context. Every case gets a second pass and a reversed-order pass. A second pair (C7/C8, S7/S8, pages 7/8, 'Growth by Q3-19', S9 "40 staff") is checked both ways, including the item order reversed, a side with its own heading and a narrated side |
| Earlier controls | All earlier modules' tests pass unchanged, including the memo-101/102 corrections and the citation-denial and clause-ownership controls of the three PR #288 review rounds |
| Replay of memos 96–103 | Raw replies from the committed evidence, the full sequence, with the guard at `c6c3d1b` and at `b16d3c1` ([output/replay_memos_96_to_103_b16d3c1.json](output/replay_memos_96_to_103_b16d3c1.json)).<br>• **Memos 96–102: no field differs.**<br>• **Memo 103: exactly `base_scenario` and `upside_scenario` differ**, as above.<br>• Every replay is idempotent and order-stable, and every citation names a supplied ref.<br>• Memo 103's `c6c3d1b` replay equals its stored memo. The recorded memos were not touched |
| Carried probes | 75/75 identical to `f7a5ad1`'s apart from `head` (`f7a5ad1` and `c6c3d1b` carry the same guard blob, `cd57401b`) ([output/carried_probes_75_b16d3c1.json](output/carried_probes_75_b16d3c1.json)) |
| Exact outputs | **110/110**, with 0 diff lines from `f7a5ad1` once the head label and column padding are normalised ([output/exact_and_boundaries_b16d3c1.txt](output/exact_and_boundaries_b16d3c1.txt)) |
| Targeted mutations at `b16d3c1` | **21 of 21 caught by assertion failures** ([output/mutations_all21_b16d3c1.txt](output/mutations_all21_b16d3c1.txt)).<br>• Every "errors in:" line is "-": **0 execution errors and 0 crash-only kills**.<br>• Each was restored with a SHA-256 check, and the hashes before and after match ([output/pre_hashes.txt](output/pre_hashes.txt)).<br>• Five foreground chunks, one per call, behind the 0.9 GB floor; free RAM was 1.39–1.53 GB ([output/mutation_ram.txt](output/mutation_ram.txt)) |
| First mutation pass, at `4440bdc` | 20 of 21 caught; **J6 survived** ([output/mutations_first_pass_4440bdc/](output/mutations_first_pass_4440bdc/)). Its only control (", with revenue to follow if the figures hold") was also refused by the pair-naming check. `b16d3c1` adds ", with growth to follow if monetised", which only the condition check decides, and the whole pass was rerun at `b16d3c1` |

**The mutants:**
- **J1–J9, the source-context changes:**
  - **J1:** the qualifier stays in the head.
  - **J2:** the qualifier counts as a denial.
  - **J3:** a closing clause blocks the rule.
  - **J4:** the moved fact goes before the closing clause.
  - **J5–J7:** a closing clause naming the pair, holding a condition, or naming a page or heading is moved past.
  - **J8:** any "without" is a qualifier.
  - **J9:** the time phrase is not read.
- **K1–K12, the consequence rule:**
  - **K1:** the rule is off.
  - **K2, K3:** a citation-group or thousands comma ends the antecedent.
  - **K4:** any antecedent accepts.
  - **K5:** a further condition's comma ends it.
  - **K6, K7, K12:** a denied, cited or attributed consequence gets the note.
  - **K8:** not idempotent.
  - **K9:** a later condition is read.
  - **K10:** a side with its own heading gets "no date context".
  - **K11:** a narrated side is restated.

## Limitations

- **An allowlist, so it under-corrects; it never removes a condition, denial, question, fact or narrator.**
  - **Qualifiers and clauses:** a verification qualifier outside the list, and a closing clause other than ", with/alongside …", still keep an OF-1102 sentence unchanged.
  - **Conditions:** a condition with any unlisted word, or one not opening the sentence ("X would be large if …"), keeps an OF-1103 sentence unchanged.
- **The condition rule (OF-1003) was not given the qualifier.** "If the figures … are taken at face value without independent verification under the 'X' framing, …" is still kept unchanged.
- **Where the fixes go:**
  - The OF-1102 fact follows the whole sentence, after the closing clause, as in the earlier condition rule.
  - The OF-1103 note restates the heading's own statements and page 12's, using the deck's spellings ("140 000+ bots").
- **Only one heading phrase is read per consequence.** Only an affirmative clause whose moved ref shares a citation group with a ref under the heading is split, as before. A page-12 figure cited in its own group is still kept.
- **Carried from earlier rounds:**
  - slash and "vs." citations ("[C3/S2]") are not read by `_REF`;
  - the limitations in the PR #288 evidence folders.

## Reproduction

The scripts are in [output/scripts/](output/scripts/) with a `.txt` suffix:
- **Fixtures:** `make_fixtures.py`.
- **Tests:** `t.sh`.
- **Replay and exact table:** `shell.sh` runs `replay.py`, `sum_replay.py`, `carried_probe.py`, `exact.py` and `cmp_probes.py`.
- **Mutations:** `chunk.sh` runs `mutate_j.py`; `anchors.py` confirms that all 21 anchors match once.

## Status

- Pending independent review; not merged and not deployed.
- No live model run has been started, and none will be until this is reviewed and merged.
- Still open: RA-109 live acceptance, RA-108, RA-114, overall hardening, and the separately tracked wording questions Q-2, Q-3 and Q-4.
