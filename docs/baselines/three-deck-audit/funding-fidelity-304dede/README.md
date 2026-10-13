# Funding-source fidelity: review gaps at `1d63239`, fixed at `304dede`

**Separate, additive evidence.** It edits none of these:
- the 1d63239 and 49663be folders, or any earlier funding-fidelity folder;
- the memo-95 run and its OWNER_GRADING.md (`docs/manychat-funding-fidelity-2948998`, still at 9688474);
- memos 94, 95, 90 and 91;
- documents 3132, 3133, 3136 and 3137.

**Status:**
- The branch stays unmerged.
- RA-106 and Zelda hardening stay pending.
- Memo 95 is not regenerated.
- Not deployed.

## Gap 1: matching dates do not establish current cash or runway

**Before (1d63239):** a dated cash balance and burn rate with matching dates left "current remaining runway" untouched, whether the pair was dated 2016-04-30 or 2030-06-30. FY2026 was also read as December 2026, so an "FY2026" annual burn was taken as compatible with a 2026-06-30 cash balance.

**Now:**
- **A supported pair supports runway only as of its own date.** Current wording takes that date instead:
  - the forms covered are a "current" / "present" / "today's" adjective, or "today" / "now" / "currently" / "at present" in the premise's clause;
  - "against current remaining runway" becomes "against runway as of 2016-04-30 (from the dated cash balance and burn rate; the evidence gives no current figure)";
  - "... leaves remaining runway today" becomes "... leaves runway as of 2016-04-30 (...)", and the contradictory "today" is removed from that clause;
  - "the current available cash" becomes "the cash as of 2016-04-30 (the latest dated cash balance; the evidence gives no current figure)".
- **Without support**, "current" stays and the premise is qualified as before: "current runway (which needs a dated cash balance and burn rate; …)".
- **Kept as written:**
  - the dated positive controls with no current wording ("against remaining runway" with a matching dated pair);
  - historical analysis ("implied remaining runway at that date");
  - questions and "if" scenarios that use "current".
- **No December is inferred from FY2026.** A bare fiscal year has no month. It matches only the same fiscal-year label (FY2026 cash with an FY2026 burn), never a month end. FY2026 burn against 2026-06-30 cash now reads "not shown to be from the same period" (the earlier "not from the same period" wording was also softened to this).
- **Prompt rule 10 adds:** "Dated cash and burn give runway as of their date, never current runway."

## Gap 2: every relevant citation group in one call, with locality

**Before (1d63239):** the review repro (S1 company traction, S3 Pitch Deck Hunt funding, S4 Crunchbase funding) failed three ways:
- only the first "self-reported" was handled per call;
- S3's note moved into S4's clause ("self-reported funding [S4] is unverified (per Pitch Deck Hunt, undated) [S3]");
- S4 stayed "self-reported", so the output was not idempotent in either item order.

**Now:**
- **Every "self-reported" span is handled in one call**, each within its own clause. A handled span is a no-op the next time round, so the loop ends.
- **Locality:** a narrated note moves forward only through clauses without their own citations or "self-reported" wording. Otherwise it stays beside its group.

> The self-reported figures [S1] (funding: per Pitch Deck Hunt, undated [S3]) are noted, and funding (per Crunchbase) [S4] is unverified.

The result is the same in reversed item order and is idempotent. The memo-95 form (the note moving to a later uncited funding clause) is unchanged.

## Results

[output/gaps_probe.txt](output/gaps_probe.txt) runs each reviewer scenario through the 1d63239 and 304dede code, guarding every output a second time:
- **At 1d63239:**
  - the current premise was untouched for both the 2016 and 2030 pairs;
  - FY2026 counted as compatible with 2026-06-30;
  - the repro misplaced S3's note, left S4 self-reported, and was **not idempotent**.
- **At 304dede:** every case is correct and idempotent. The dated positive control is unchanged.

[output/memo95_probe.txt](output/memo95_probe.txt): memo 95's raw reply through the guards. Sections and text are **identical** to the 49663be and 1d63239 probes: the three corrected passages, with the conditional scenario, questions and "Runway: not calculated" kept.

[output/memo94_probe.txt](output/memo94_probe.txt): **identical** to the earlier probes.

**New regressions** (`zelda_api/tests_funding_fidelity.py`):
- **Current premises:**
  - three current forms × three pairs (2016-04-30, 2030-06-30, FY2026), checked in reversed item order and for idempotence;
  - kept controls: the plain premise, historical analysis, a question and an "if" scenario;
  - unsupported "current runway" and "current cash", with idempotence;
  - FY2026 against a period end (not shown to be from the same period);
  - FY2026 with FY2026 (supported);
  - the prompt-rule sentence.
- **Locality:**
  - the review repro;
  - a memo-95-style clause followed by an S4 clause;
  - S4 first;
  - an uncited later "self-reported" clause;

  each checked in both item orders and for idempotence.
- **Kept:** all earlier regressions. One test changed by intent: FY2026 annual burn is no longer "compatible" with 2026-06-30 cash.

[output/mutations_output.txt](output/mutations_output.txt): **85 mutations: 84 red, 1 equivalent, 0 survived.**
- **Inherited:** 70. Those targeting moved code were dedented or retargeted with the same intent.
- **New:** 11 M (gap 1) and 4 N (gap 2).
- **M7 is an equivalent mutant:** it drops the month-vs-fiscal-year kind check. A month index (at least 12001) can never equal or be within 6 of a fiscal year (at most 9999), so no input can tell it apart. The header explains this.
- **Fingerprints:** file sha256s were verified after every group and equal the committed files.
- **Harness chain:** `mutate_fidelity6.py` chains to `mutate_fidelity5.py` (`../funding-fidelity-1d63239/output/`), then `mutate_fidelity4.py` (`../funding-fidelity-49663be/output/`), then `mutate_fidelity3.py`.

[output/validation_output.txt](output/validation_output.txt): on the committed code, isolated test databases, one batch at a time.
- `check` clean.
- `makemigrations --check`: no changes.
- 236 + 428 + 87 = **751 tests OK**.
- Consumers covered: memo persistence and list rendering, IC memo/Markdown/Lite via the writer test, presentation, authorization, panel, library, notifications, paywall and company overview.

**Unchanged:**
- structured periods;
- Truth Delta comparison and scoring;
- tier permissions;
- the raw-source memo boundary;
- the memo payload.

## Still open
- **RA-106:** until a newly generated memo is graded.
- **Current-wording detection is lexical:** the forms listed above.
- **`COMPATIBLE_MONTHS = 6`** is a stated threshold.
- Also open: RA-109/I1, RA-103, RA-108, PF-206 / FF-311.
