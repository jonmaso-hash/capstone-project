# Funding-source fidelity: possessive "Today's" opening, at `7c71995`

**Separate, additive evidence.** It edits no earlier evidence folder. It also leaves these untouched:
- the memo-95 run and its OWNER_GRADING.md (`docs/manychat-funding-fidelity-2948998`, 9688474);
- memos 94, 95, 90 and 91;
- documents 3132, 3133, 3136 and 3137.

**Status:**
- The branch stays unmerged.
- RA-106 and Zelda hardening stay pending.
- Not deployed.

## The change
**Source:** the owner's `funding-fidelity-possessive-opening-fix.patch`, copied verbatim in `output/`. It was checked with `git apply --check` first, then applied cleanly on 5c5502f (branch tip 2e64686). The committed change to `zelda_api/funding_fidelity.py` matches the patch's hunks line for line ([output/patch_apply.txt](output/patch_apply.txt)).

**What the patch does:**
- `_LEAD_NOW` accepts "Today's" with a straight (') or typographic (’) apostrophe.
- After the premise rewrite, the opening is found again. The rewrite can consume "Today's remaining runway" itself (as a "current" adjective), so cutting at the original opening's length was wrong. The list marker is kept, and the rest is recapitalized.

**Before (5c5502f), through both guards with a 2016-04-30 cash/burn pair:**
- "Today's $23.1M funding figure … supports remaining runway." gave "'s $23.1M funding figure … supports runway as of 2016-04-30 (…)."
- "Today's remaining runway is anchored by …" gave "Y as of 2016-04-30 (…) is anchored by …"
- The same happened under "- ", "• " and "1. ".

**After (7c71995):**
- "$23.1M funding figure (per Pitch Deck Hunt) [S3] supports runway as of 2016-04-30 (…)."
- "Runway as of 2016-04-30 (…) is anchored by …"
- "Cash as of 2016-04-30 (…) is not …"

Each keeps its list marker. The rewritten "Runway" / "Cash" keeps its noun and capital.

**Without a dated pair:** the premise is qualified and the possessive opening stays, e.g. "Today's runway (which needs a dated cash balance and burn rate; neither is in the evidence) …" (and the same with ’).

## Results
[output/possessive_probe.txt](output/possessive_probe.txt) runs the 5c5502f and 7c71995 code, in the pipeline's order, for both apostrophes, plain, bullet and numbered forms, in both item orders, guarding each output a second time.

[output/memo95_probe.txt](output/memo95_probe.txt) (time guard, then funding guard) and [output/memo94_probe.txt](output/memo94_probe.txt): **identical** to every earlier probe.

**New regression:** `test_possessive_opening_through_both_guards`. It runs through `both_guards`, the pipeline's time-guard-then-funding-guard order, and covers:
- the three sentences ("Today's $23.1M funding figure …", "Today's remaining runway …", "Today's available cash …");
- both apostrophes;
- markers "", "- ", "• ", "1. " and "2) ";
- both item orders and idempotence;
- the unsupported control for each form.

Earlier regressions pass unchanged.

[output/mutations_output.txt](output/mutations_output.txt): **21 mutations run, all red.**
- **P1–P6 (the patch):**
  - possessive not accepted;
  - typographic apostrophe not accepted;
  - the pre-patch slice;
  - opening not re-found;
  - marker dropped when the opening is consumed;
  - marker not kept.
- **15 inherited, covering the opening and current-wording code:** O1–O4 (O3 retargeted to the patched line), O9–O11, M1–M5, M8–M10.
- **Not re-run:** the other 82 inherited mutations, whose code is untouched. Their targets were verified.

**Line endings:** `git apply` rewrote `funding_fidelity.py` with CRLF (`core.autocrlf=true`). The fingerprints in the header are the working copies. The committed LF blob (`6653e34e…`) has identical content ignoring CR. `claim_context.py` is unchanged since 5c5502f and has the same CRLF/LF situation.

[output/validation_output.txt](output/validation_output.txt): on the committed code, isolated test databases, one batch at a time.
- `check` clean.
- `makemigrations --check`: no changes.
- 241 + 428 + 87 = **756 tests OK**.

**Unchanged:**
- structured periods;
- fiscal-year distinctions;
- locality and citations;
- questions and conditional scenarios;
- scoring and tiers;
- the raw-source memo boundary.

## Still open
- **"Today's $23.1M funding figure …" now opens with the bare figure**, with no article. That is grammatical but terse; the patch does not insert one.
- **Opening detection is lexical.**
- **RA-106:** until a newly generated memo is graded.
- Also open: RA-109/I1, RA-103, RA-108, PF-206 / FF-311.
