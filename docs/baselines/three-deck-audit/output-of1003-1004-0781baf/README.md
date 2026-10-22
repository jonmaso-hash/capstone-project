# OF-1003 and OF-1004 (memo 102) corrected at `75ca81f` (application) and `0781baf` (final test head)

Additive correction evidence; **not live acceptance**. No live model was called, memo 102 was not regenerated and its Q1–Q7 were not repeated. Its eight model calls remain the original failure record. Frozen fixtures, answer keys, grading, recorded memos and earlier evidence are unchanged.

| Item | Value |
|---|---|
| Live evidence (immutable) | Run `6d131f585cb5232a7535d896d6659583b5ecb053`; independent grade `f2a282f98951e91c7e638e8a805e8f5fc07685b0`, both on `docs/manychat-output-fidelity-d0bad8f` (`docs/baselines/manychat/output-fidelity-d0bad8f/`) |
| Base | `main` at `d0bad8fdaace39f2f64be9f576874da9b0bf5e7a` (PR #287), the code memo 102 ran on |
| Application commit | `75ca81f722503110fc378b50270d5bcc0a149eec` (`zelda_api/basis_fidelity.py`, tests and the memo-102 fixtures) |
| Test-only commits | `37f77e542e0fb19fdec41c6563a9f20898e1e64b`, `0781bafc55187a2fe09730befaae113625ac2380` (final head; application bytes identical to `75ca81f`) |

## The two blockers (independent grade `f2a282f`)

- **OF-1003 (P2):** `base_scenario` says "If the traction figures [S1, S2, S3] are taken at face value under the 'Traction by Apr-16' framing, ManyChat had reached meaningful platform scale at that point in time." S3 is page 12's monthly statement and has no supplied context. "Taken at face value" does not give it page 10's date.
- **OF-1004 (P2):** `open_concerns` and `business_model_analysis` cite page 12's monthly figure as `[C3, S3]`. C3 is page 10's claim. The mapping is C3 / S2: page 10, 500M messages, interval unstated; C2 / S3: page 12, 500M messages/month.
- **OF-1005:** not an additional blocker.

## Root cause

The model wrote both defects, and the guards passed them unchanged. At `d0bad8f` the replay of memo 102's raw reply reproduces the stored memo exactly, with one funding narrator edit and no basis edit ([output/replay_memos_96_to_102_0781baf.json](output/replay_memos_96_to_102_0781baf.json): `base_replay_equals_stored` true for memo 102).

- **OF-1003:** the merged context rule (`_context_aside`) moves page 12's refs out from under page 10's heading only for the company's affirmative statement. It kept every condition, so that explicit date hypotheses would be preserved ("If … [S3] reflects a monthly run-rate as of the 'X' slide context"). Two narrower gaps also applied: it did not read "framing" as a context noun, and it required the phrase to end its clause. A condition that only accepts the figures supposes nothing about their date, yet it still carried the heading onto S3.
- **OF-1004:** no rule checked a citation's identity. Pairs knew each side's members (C3/S2 and C2/S3), but nothing checked that a group attached to one figure cites that figure's side.

## The correction (`zelda_api/basis_fidelity.py`)

### Identity rule (OF-1004), first in each sentence

A citation group written straight after **one** figure of a pair, or one operand of "[…] vs […]" whose other operand cites one side alone, cites that figure's side.

**What names a side:**
- the figure's value, "+" and stated interval together ("500M messages/month");
- with no interval written, a quotation of one side's whole statement ("'500M messages'").

The same number alone names no side.

**The repair:**
- The other side's ref becomes the named side's ref of the same kind: its claim (`Pair.refs`), or its one repeating statement.
- With no such ref, the wrong ref is dropped if the group still cites the named side. Otherwise it is kept and logged as `basis_citation_identity_unresolved`, rather than being invented or silently deleted.

**Kept:**
- comparisons: a group citing both sides' claims ("[C2, C3]") or both sides' statements;
- a group after a list of both figures ("page 10 states '500M messages' … while page 12 states '500M messages/month' [C2, C3]");
- a group following no figure ("conflicting bases [C3, C2]");
- another interval ("500M messages/day"), another noun, or a "+" no statement gives;
- an unquoted figure with no interval ("500M messages [C2]");
- refs outside the pair;
- "[C3, S2 vs S3]", which the citation pattern does not parse.

`Pair` gains `statements` (each side's claim statement).

### Condition rule (OF-1003), after the affirmative context rule

**When it acts:** a condition ("if", "assuming", "supposing") whose antecedent holds nothing but:
- the figures' own subject (placing words, the pair's evidence categories, the cited statements' words);
- their citations;
- an acceptance frame ("are taken at face value", "are accepted as stated");
- a context phrase ending the antecedent.

**What it does:** the other side's refs leave the condition's citations and follow the sentence as the deck's own fact, with their own page and context and the pair's clarification ("…; the deck separately states 500M messages/month [S3] on page 12 (how … needs clarification before either is relied on)").

**Kept:**
- any other predicate: an explicit hypothesis about the date or basis ("reflects a monthly run rate under …", "all fall under …", "as of the 'X' slide context");
- "whether", a question, a denial, a hedge;
- a narrator, an attributed speaker, another metric;
- a narrated side;
- an antecedent that continues ("… framing and revenue follows");
- a condition citing only page 12, where nothing would stay under the heading.

"framing" is added to the context-phrase nouns, which the affirmative rule shares.

## Exact output changes for memo 102 (raw reply, full guard sequence; [output/memo_changes_0781baf.txt](output/memo_changes_0781baf.txt))

| Section | Before (stored = raw) | After | Why |
|---|---|---|---|
| `base_scenario` | If the traction figures [S1, S2, S3] are taken at face value under the 'Traction by Apr-16' framing, ManyChat had reached meaningful platform scale at that point in time. | If the traction figures [S1, S2] are taken at face value under the 'Traction by Apr-16' framing, ManyChat had reached meaningful platform scale at that point in time; the deck separately states 500M messages/month [S3] on page 12 (how the figure stated without an explicit interval relates to the monthly figure needs clarification before either is relied on). | Page 10's heading now covers only page 10's S1 and S2. S3 keeps its citation, its page and no date |
| `open_concerns` 1 | … while a separate page states '500M messages/month' [C3, S3]. | … while a separate page states '500M messages/month' [C2, S3]. | The quoted monthly figure is page 12's: its claim is C2. The earlier "[C3, S2]" for page 10 is unchanged |
| `business_model_analysis` | … see consistency note on [C3, S2] vs [C3, S3]) … | … see consistency note on [C3, S2] vs [C2, S3]) … | The second operand stands for the monthly side against page 10's [C3, S2]. The sentence's own placing ("in a slide headed 'Traction by Apr-16' [S1, S2], and 500M messages/month elsewhere [S3]", OF-1005) is unchanged |

The 14 other fields are exactly as stored. The citation order is unchanged except for the two C3 → C2 replacements. The memo writer, tested with a mocked model (`PipelineMemo102Tests`), stores exactly these outputs.

## Validation

| Check | Result |
|---|---|
| Red | Final tests (`0781baf`) against `d0bad8f`'s guard: **20 assertion failures, 0 errors** across all of `tests_output_fidelity` (224 tests), including the memo writer ([output/red_run_final_tests_on_d0bad8f.txt](output/red_run_final_tests_on_d0bad8f.txt)). The first tests (before the later controls) gave 18 failures, 0 errors, out of 221 ([output/red_run_first_tests_on_d0bad8f.txt](output/red_run_first_tests_on_d0bad8f.txt)). The preservation controls pass on both codes, as controls should |
| Green at `0781baf` | Modules one at a time: **224 + 77 + 67 = 368 OK** ([output/modules_0781baf.txt](output/modules_0781baf.txt)). The tree was clean |
| Django | `check` and `makemigrations --check --dry-run` exit 0, with `PYTHONDONTWRITEBYTECODE=1` ([output/check_and_migrations_0781baf.txt](output/check_and_migrations_0781baf.txt)) |
| Replay of memos 96–102 | Raw replies from their committed evidence, full guard sequence, base `d0bad8f` vs `0781baf` ([output/replay_memos_96_to_102_0781baf.json](output/replay_memos_96_to_102_0781baf.json)).<br>• **Memos 96–101:** 0 fields differ.<br>• **Memo 102:** exactly the three fields above differ.<br>• **Every memo:** reversed item order gives the same output and changes; a second pass changes nothing; every output citation names a supplied ref; other fields' citations are unchanged.<br>• The base replay equals memo 102 as stored; memos 100 and 101 were stored before later merged repairs. The recorded memos are not touched |
| Carried probes | **75 probes, identical apart from `head`** to the committed `064e4ea` output (in `44af018`) ([output/compare_probes.txt](output/compare_probes.txt)) |
| Exact outputs | **110/110** at `0781baf`, the same table as at `c7d4607` (0 diff lines; [output/exact_diff_c7d4607_vs_0781baf.txt](output/exact_diff_c7d4607_vs_0781baf.txt)) |
| Mutations | **31 of 31 caught at `0781baf`**, each by assertion failures in a run of all 368 tests, with no errors; every restore SHA-256 checked ([output/mutations_all31_0781baf.txt](output/mutations_all31_0781baf.txt); the [pre](output/pre_mutation_hashes_0781baf.txt) and [post](output/post_mutation_hashes_0781baf.txt) hashes are identical). See the next section |

### Mutations

Each mutation either removes a correction, so the memo-102 defect returns, or removes a protection, causing harmful overcorrection.

- **Identity (I1–I18; I7 unused):**
  - the rule off;
  - comparisons not recognised;
  - the list guard off;
  - interval, quotation, "+" and noun not read, or an unquoted figure naming a side;
  - wrong-kind or other-side replacement;
  - the drop and unresolved paths;
  - refs outside the pair dropped;
  - the "vs" rule off, or applied when both operands mix or one compares;
  - `Pair.statements` empty.
- **Condition (C1–C14):**
  - the rule off;
  - "framing";
  - "whether", "assuming" and "as stated";
  - any predicate accepted;
  - antecedent end not required;
  - topics, subject allowlist, narrator and attribution, and narrated refs not read;
  - a page-12-only condition emptied;
  - questions rewritten;
  - the clarification not added.
- **First pass at `37f77e5`** ([output/mutations_first_pass_37f77e5.txt](output/mutations_first_pass_37f77e5.txt)): **C6 and C9 survived**, both masked by other checks. Its controls used "usage", which is already a placing word, and "the monthly figure", which the subject allowlist already refuses. Test-only `0781baf` added controls only those checks decide, and the whole pass was rerun at that head.
- **Earlier masking found before any run** (test-only `37f77e5`): the "whether", "+", noun, comparison-operand and narrated-side controls.
- **Not rerun:** the 127 carried mutations from earlier rounds. The carried probes, the exact table and all earlier tests are unchanged and green.

## Running conditions

- Free RAM before each chunk: 1.10–1.65 GB ([output/free_ram_before_mutation_chunks.txt](output/free_ram_before_mutation_chunks.txt)). The 0.9 GB floor refused nothing, and every chunk ran in the foreground.
- **My slips, none affecting a result:**
  - `replay_diff.py` first wrote its JSON to `sys.argv[1]`, which under `manage.py shell -c` is the word "shell". This created an untracked file named `shell` in the worktree. I removed it before any commit and changed the script to use `OUT`.
  - A first draft of the identity rule's list guard read "500M" without lowercasing. The memo 99–101 replays exposed it (their correct "[C2, C3]" lost C3), and it was fixed before any commit.
  - A test expectation contradicted the design ("[S7, S8]" is a comparison). The test was corrected, not the rule.

## Limitations

- **Identity:**
  - Only a group written straight after one figure, or a "vs" operand.
  - A figure with no interval names a side only when quoted whole; "500M messages per month" (spelled out) and figures far from their citation are not read.
  - Scoped to measurement-basis pairs: a same-number miscitation without a consistency note is not checked.
- **Condition:**
  - Only the allowlisted acceptance frames. Others ("are reliable", "hold") are kept as written.
  - The restated fact follows the whole sentence, after the consequence.
  - A condition citing only page 12 under page 10's heading ("If the figure [S3] is taken at face value under the 'X' framing") is kept.
  - A question with the same shape is kept.
- **Carried:** the limitations of earlier rounds (fixed vocabularies, "slide N" as page N, the condition path's basis words, and others). See the earlier READMEs.
- **P3 items keep their classes:** OF-1008 (OF-909 class), OF-1009 (OF-910 class, including RA-108). Their wording is unchanged.
- **Not live:** RA-109 live acceptance needs a fresh sample at the reviewed, merged code, independently graded, with the browser walks completed (they were blocked for memo 102, D-9).

**Status:** branch `fix/basis-context-identity-of1003-1004`, unmerged and not deployed, pending independent review. RA-109 live acceptance, RA-108, RA-114 and overall hardening remain open.
