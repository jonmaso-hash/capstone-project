# FF-405 review corrections: equated figures and joint narrators, at `589917a`

**Separate, additive evidence.** It edits no earlier evidence folder. These are all unchanged:
- `narrator-provenance-4d53428/` (1f9786e);
- memo 96's run folder `docs/baselines/manychat/funding-fidelity-9b6d215/` (branch `docs/manychat-funding-fidelity-9b6d215`, 5f08c05), including the grading and the accepted staff addendum;
- every earlier memo and document.

No report was regenerated.

**Status:** branch `fix/narrator-provenance`, pushed and unmerged, with no PR. RA-106 and Zelda hardening stay pending. Nothing is deployed, and paid-source Pass B was not run.

| Commit | What |
|---|---|
| `afe0cab` | FF-405 rule, first version (reviewed) |
| `4d53428` | FF-411 Markdown charset (not changed here) |
| `1f9786e` | Evidence for the first version |
| `589917a` | **These corrections:** `zelda_api/funding_fidelity.py`, `zelda_api/tests_funding_fidelity.py`, new fixture `zelda_api/data/funding_fidelity/memo96_payload.json` |

## Finding 1: the replay still equated the company's traction with Pitch Deck Hunt's funding

The first fix replayed memo 96 to "...the company's own deck statements [S1, S2] and **the same figures as reported by** the third-party aggregator Pitch Deck Hunt [C1] ...". The test expectation preserved this wording. [S1, S2] are the company's 140 000+ bots and 500M messages. [C1] is Pitch Deck Hunt's $23.1M raised. They are not the same figures.

**Correction.** `FundingFacts.ref_figures` now holds every item's (ref, statement). The rule covers wordings of the form "the same / identical <figures|numbers|amounts|metrics|claims|statements|data> as / reported by / per / as <narrators> [refs]".
- **When it holds:** only if the narrators' own cited refs state every figure of the citation group it is equated with.
- **Otherwise:** the equation is dropped and the narrators' figures are named by their kind, as in "the funding figure reported by".
- **With none of the narrators' own refs cited:** it reads "the figures reported by".
- **Left as written:** a ref outside the context, a sentence with nothing cited before the phrase, and questions.

Memo 96 `zelda_advantage`, replayed from its recorded raw reply with its own grounded payload:

> The verification pass distinguished between the company's own deck statements [S1, S2] and **the funding figure reported by** the third-party aggregator Pitch Deck Hunt **[C1] ([C2, C3] are the company's own traction statements)**, correctly flagging that Pitch Deck Hunt is the narrator of the **funding claims** rather than an independent validator — ...

`MEMO96_ADVANTAGE_FIXED` (the test expectation) now requires this wording. So does the writer test, which covers the stored memo, the staff IC memo and the Markdown. Both reject "the same figures as reported by".

## Finding 2: joint narrator names bypassed citation validation

The first version skipped any narrator named together with another, as in "Pitch Deck Hunt and Crunchbase list ... [S3, S4, S1]". A company ref in a joint group was therefore never checked.

**Correction.**
- **One run:** narrators named together ("A and B", "A, B and C", "A & B", "A or B") are read as one run.
- **Citations:** their citation group keeps every ref that one of them narrates. Each other ref is named under its own source, as in "[S3, S4] ([S1] is the company's own traction statement)". When none of the refs is theirs, the note reads "(not Pitch Deck Hunt's or Crunchbase's: ...)".
- **Kinds of figure:** "<A> and <B> are the sources of the X, Y and Z figures" keeps the kinds that either one narrates.
- **Unchanged:**
  - legitimate joint attribution ("Pitch Deck Hunt and Crunchbase list ... [S3, S4]");
  - the company named together with a narrator ("The company and Pitch Deck Hunt list [S3, S1]");
  - questions.

## Memo 96 replay with its actual grounded payload ([output/memo96_replay.txt](output/memo96_replay.txt))

`probe96.py` reads the payload **actually sent to the model** from the run's recorded call (09b). It checks that this payload equals the rebuilt payload (09a) and the new test fixture; all three are equal. It then replays the recorded raw reply through the pipeline's guard steps: the time guard, then the funding guard.

- 15 of 16 text sections equal stored memo 96. Only `zelda_advantage` differs, as quoted above; `evidence_level` is not a text section.
- Reversing the item order gives the same memo.
- A second pass changes nothing in any section.

The regression test does the same from the fixture `memo96_payload.json`, which is a copy of 09a's payload with its sha256 recorded in it. It runs in both item orders, with an idempotence check per section. `GroundedItem.time_wording_allowed` is not part of the payload, so it is empty in the replay. Stored memo 96 is not regenerated or edited.

## Earlier memos

- [memo95_probe.txt](output/memo95_probe.txt) is identical to the memo-95 probe committed at 1f9786e (compared with line endings normalized).
- [memo94_probe.txt](output/memo94_probe.txt) is identical to the memo-94 probe committed at 1f9786e (compared with line endings normalized). Its header line prints a frozenset, whose order can vary between runs; this run matched.

## Regressions (`zelda_api/tests_funding_fidelity.py`)

- **`NarratorProvenanceTests`:**
  - memo 96's sentence;
  - memo 96's whole raw reply with its own payload, in both item orders, idempotent;
  - the fixture payload gives the same refs, narrators and kinds as the test context;
  - the changes recorded, and that no ref is added or lost;
  - **(new, N5)** a citation after another subject ("... and ManyChat reports 500M messages [S2]", "... noting the company's 140,000+ bots [S1]", "... notes that the company reports ... [S1, S2]") is left as written. As a control, the same shape with no other subject is checked and split.
- **`JointNarratorAndEquatedFigureTests` (new):**
  - Joint narrators, rewritten: joint groups containing a company ref, names in either order, only company refs, a citation before the names, and joint kinds.
  - Joint narrators, unchanged: legitimate joint attribution, the company named with a narrator, and questions.
  - Equated figures, rewritten: paraphrases ("per", "as <narrator>", "identical"), partly the same, joint narrators, and none of the narrator's own refs.
  - Equated figures, unchanged: supported equations, nothing cited before, an unknown ref, and questions.
  - Joint kinds where the company has its own revenue.
- **`MemoWriterTests.test_memo_96_zelda_advantage_through_the_writer_and_its_full_readers`:** the corrected clause appears in the stored memo, the staff IC memo and the Markdown.

## Mutations ([output/mutations_output.txt](output/mutations_output.txt), harness [mutate_np2.py.txt](output/mutate_np2.py.txt))

**31 mutations, each with a completed run, all RED.** The set:
- N1–N16 (no N4), re-pointed at the revised rule;
- J1–J6, joint narrators; J1 restores the reviewed bypass;
- E1–E8, equated figures; E1 restores the reviewed behaviour;
- M1–M2, the FF-411 charset.

- **Run 1** ran in the background in four sequential groups. N5 survived it: no test had a narrator followed by another subject before the citation. The N5 regression was added and N5 then went RED in run 2, so the mutation is not equivalent.
- **Run 1 was stopped** by Claude Code while E4 was running, under system low memory. That E4 line shows "RED" only because the subprocess was killed; it has no test result and is marked **not counted**.
- **Run 2** ran in the foreground, one mutation at a time, with free RAM checked before each: N5, then E4, then E5–E8, M1 and M2.
- **File restoration:** both code files matched their fingerprints after every group and every run 2 mutation, and no mutation subprocess remained after the interruption. The fingerprints are `funding_fidelity.py` d291828a17633fa3 and `views.py` 1061e439239f3b98.

## Validation ([output/validation_output.txt](output/validation_output.txt))

**773 tests OK** (256 + 430 + 87) in three sequential batches, with the memory watchdog running. `check` is clean, and `makemigrations --check` reports no changes. The watchdog logged no process over 1,500 MB.

## Process notes

- **Low memory:** during mutation run 1 the system ran low on memory, and Claude Code stopped the watchdog and the mutation run. No Python process had exceeded the watchdog threshold. Work resumed on the owner's instruction, with one foreground run at a time.
- **Deleted worktrees:** several worktree folders, including the memo-95 and memo-96 run worktrees (`KCV-mc-ff`, `KCV-mc-ff3`), were found deleted from disk partway through this work. They were not deleted here and were not recreated or pruned. Their branches are intact locally and on origin (5f08c05, 9688474). The memo-95 and memo-96 probes therefore read the evidence files extracted with `git show <commit>:<path>`. The extracted 09a's sha256 equals the one recorded in the fixture. The edit is in [make_r3.py.txt](output/make_r3.py.txt). The memo-94 probe already read its evidence this way.
- **One tracked file restored:** a probe rewrote the tracked file `zelda_api/__pycache__/__init__.cpython-314.pyc`. It was restored with `git checkout` and is not in any commit.

## Still open
- FF-406 ("as of April 2016"), FF-407 ("listed as Series A"), FF-413 (the Truth Delta page renders as an unstyled fragment).
- RA-106 (until a newly generated memo is graded), RA-109/I1, RA-103, RA-108, PF-206/FF-311.
- Detection is lexical. Not checked:
  - a narrator credited across clauses or by a pronoun;
  - an equation worded differently from "the same / identical <noun> as / reported by / per <narrator>".
