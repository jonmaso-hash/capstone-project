# FF-405 second review corrections: every equation, shared company credit, at `d246e36`

**Separate, additive evidence.** It edits no earlier evidence folder. These are all unchanged:
- `narrator-provenance-4d53428/` (1f9786e) and `narrator-provenance-review-589917a/` (8bc97dc);
- memo 96's run folder (5f08c05 on `docs/manychat-funding-fidelity-9b6d215`), including the grading and the accepted staff addendum;
- every earlier memo and document.

No report was regenerated.

**Status:** branch `fix/narrator-provenance`, pushed and unmerged, with no PR. RA-106, RA-108 and Zelda hardening stay pending. Nothing is deployed, and paid-source Pass B was not run. The accepted staff navigation check does not establish a pass for a newly generated memo.

| Commit | What |
|---|---|
| `afe0cab`, `4d53428`, `1f9786e` | FF-405 first version, FF-411 (accepted), their evidence |
| `589917a`, `8bc97dc` | First review corrections (equated figures, joint narrators), their evidence |
| `d246e36` | **These corrections:** `zelda_api/funding_fidelity.py` (`_same_figures`, new `_is_note`), `zelda_api/tests_funding_fidelity.py` |

## Finding 1: only the first equality in a sentence was checked (P2)

`_same_figures` searched once and returned. A supported first equation therefore shielded a false second one. When there were two false equations, the second needed another pass, so the rule was not idempotent.

**Correction.** Every equation in the sentence is checked in one invocation, and the rule continues past supported, uncheckable and rewritten matches alike.
- **Compared group:** each equation is compared with the nearest group cited before it and after the previous equation's credited group.
- **Notes:** the guard's own notes, such as "([C2, C3] are …)", are never taken as the compared group.

Exact outputs ([output/review_cases.txt](output/review_cases.txt)); each case gives the same result in both item orders and is idempotent:

| Input | Output |
|---|---|
| The funding [S3] and the same figures per Pitch Deck Hunt [C1], alongside the bots [S1] and the same figures per Pitch Deck Hunt [S3], are unverified. | …[C1], alongside the bots [S1] and **the funding figure per** Pitch Deck Hunt [S3], are unverified. (The first equation is supported and kept.) |
| The bots [S1] and the same figures per Pitch Deck Hunt [C1], plus the messages [S2] and the same figures per Pitch Deck Hunt [S3], are unverified. | The bots [S1] and **the funding figure per** Pitch Deck Hunt [C1], plus the messages [S2] and **the funding figure per** Pitch Deck Hunt [S3], are unverified. (Both are fixed in one pass.) |

## Finding 2: shared company/narrator credit was narrowed to a funding-only claim (P2)

In "reported by the company and Pitch Deck Hunt [S1, S3]", the phrase matcher took "the company and" as descriptive words. It then counted only Pitch Deck Hunt's refs.

**Correction.** The rule now detects the company named together with the narrators: "the company", "the deck" or the company's name, joined before or after them.
- **Shared credit:** the company's own refs count as stated, alongside the narrators' refs.
- **Supported:** a supported combined comparison is unchanged.
- **Unsupported:** an unsupported one keeps every kind in the group, as in "the traction and funding figures reported by the company and Pitch Deck Hunt".

| Input | Output |
|---|---|
| The combined bot and funding statements [S1, S3] are the same figures as reported by the company and Pitch Deck Hunt [S1, S3]. | unchanged (supported) |
| The combined statements [S1, S3] are the same figures as reported by Pitch Deck Hunt and the company [S1, S3]. | unchanged (supported) |
| The messages [S2] are the same figures as reported by the company and Pitch Deck Hunt [S1, S3]. | The messages [S2] are **the traction and funding figures reported by** the company and Pitch Deck Hunt [S1, S3]. (genuinely unsupported) |
| The company and Pitch Deck Hunt list the totals [S1, S3]. | unchanged (ordinary shared-credit control) |

## Memo 96 replay with its actual grounded payload ([output/memo96_replay.txt](output/memo96_replay.txt))

The payload sent to the model (09b), the rebuilt payload (09a) and the test fixture are equal. They are read from 5f08c05 with `git show`, because the run worktree is gone.

- Of 16 text sections, 15 equal stored memo 96. Only `zelda_advantage` differs, and it keeps the **accepted** wording:
  > …[S1, S2] and the funding figure reported by the third-party aggregator Pitch Deck Hunt [C1] ([C2, C3] are the company's own traction statements), correctly flagging that Pitch Deck Hunt is the narrator of the funding claims…
- Reversing the item order gives the same memo.
- Every ref is kept, in order, in every section.
- A second pass changes nothing.

## Earlier memos

[memo95_probe.txt](output/memo95_probe.txt) and [memo94_probe.txt](output/memo94_probe.txt) are identical to the probes committed at 1f9786e, compared with line endings normalized.

## Regressions (`JointNarratorAndEquatedFigureTests`, new methods)

- `test_every_equation_in_a_sentence_is_checked`: the two Finding 1 cases. Each checks the exact output, both item orders, idempotence and unchanged refs.
- `test_an_equation_after_a_note_is_not_compared_with_the_note`: an equation after a guard note keeps the note intact and does not compare against it.
- `test_shared_company_and_narrator_credit`: these cases are unchanged in both item orders:
  - the supported combined comparison, with the company before the narrator and with it after;
  - the company's name ("ManyChat and Pitch Deck Hunt");
  - the ordinary shared-credit control.

  Two unsupported shared-credit cases are checked with their exact output, unchanged refs and idempotence.

## Mutations ([output/mutations_output.txt](output/mutations_output.txt))

All **12 of 12 completed runs were caught**. They ran one at a time in the foreground with the watchdog running, and both file hashes matched after every run. None was interrupted.
- **Set:** N1 (rule off) and E1–E11 (the equality rule).
- **New mutations:**
  - **E9:** stops after the first equation in a sentence.
  - **E10:** restores the shared-company misclassification (`shared = False`).
  - **E11:** lets the guard's own note be taken as the compared group.
- **E7** produced errors as well as failures.
- **Not rerun:** N2–N16, J1–J6 and M1–M2 target code this commit leaves unchanged. Their completed results at 589917a are in `../narrator-provenance-review-589917a/output/mutations_output.txt`.

## Validation ([output/validation_output.txt](output/validation_output.txt))

**776 tests OK** (259 + 430 + 87) in three sequential batches, with free RAM checked before each and the watchdog running. `check` is clean, and `makemigrations --check` reports no changes. The watchdog logged no process over 1,500 MB.

## Still open
- FF-406, FF-407, FF-413; RA-106, RA-108, RA-109/I1, RA-103, PF-206/FF-311.
- Detection is lexical. Not checked:
  - credit given across clauses or by a pronoun;
  - equations worded differently from "the same / identical <noun> as / reported by / per <narrator>".
- An equation is compared only with the nearest group cited before it.
