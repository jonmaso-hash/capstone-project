# Funding-source fidelity: remaining cases at `304dede`, fixed at `5c5502f`

**Separate, additive evidence.** It edits no earlier evidence folder. The one exception is a new file added beside the 304dede evidence, [`../funding-fidelity-304dede/CORRECTION.md`](../funding-fidelity-304dede/CORRECTION.md), which corrects that folder's M7 claim; the committed files there are unchanged.

It also leaves these untouched:
- the memo-95 run and its OWNER_GRADING.md (`docs/manychat-funding-fidelity-2948998`, 9688474);
- memos 94, 95, 90 and 91;
- documents 3132, 3133, 3136 and 3137.

**Status:**
- The branch stays unmerged.
- RA-106 and Zelda hardening stay pending.
- Memo 95 is not regenerated.
- Not deployed.

## 1. Introductory time qualifiers

**Before (304dede):** with cash and monthly burn both dated 2016-04-30, "Today, the $23.1M funding figure (per Pitch Deck Hunt) [S3] supports remaining runway." passed **both** guards unchanged. The comma put "Today" outside the premise's clause.

**Now:**
- **What counts:** an introductory qualifier governs the whole sentence. The forms are "Today", "As of today", "Currently", "Presently", "At present" and "At this point", plus "Now," only with its comma ("Now that …" is not a qualifier).
- **With a supported dated pair:** the premise takes the evidence's date, and the qualifier is removed with the sentence recapitalized:
  > The $23.1M funding figure (per Pitch Deck Hunt) [S3] supports runway as of 2016-04-30 (from the dated cash balance and burn rate; the evidence gives no current figure).
- **Kept:** questions ("Today, how much remaining runway …?") and conditional scenarios ("Today, if …").
- **Without support:** the premise is qualified as before, and "Today," stays.

**Tested in the pipeline's real order** (`_generate_memo`: `guard_time_wording`, then `guard_funding_fidelity`, via `both_guards`), because the order changes the outcome:
- **"Today,"** passes the time guard, and the funding guard dates it.
- **"As of today," "At present," and "Currently"** are removed by the **time guard** first, because no source says them. The funding guard then sees no current wording, and the dated pair supports the plain premise (the dated positive control).
- **A defect this exposed:** the time guard left " the $23.1M …" (leading space, lowercase), and "- the …" in a bullet. `guard_time_wording` now restores the opening: the list marker is kept, the leading space dropped, and the original capital restored. This is the only change to `claim_context.py`.
- **When the time guard keeps the phrase**, because its source says it or the sentence cites no claim-backed item, the funding guard alone dates it. That case is tested separately.

## 2. Every narrated group governed by one self-reported span

**Before (304dede):**
- In "The self-reported figures [S1, S3] with [S4] plus [S5] are unverified.", S5 needed a second call, and the output was **not idempotent**.
- In "The self-reported funding [S3] plus [S4] is unverified.", Crunchbase was never named.

**Now:** citation groups in the span's clause that are joined only by "with", "plus", "&" or "as well as" (or nothing) form one run governed by that "self-reported". The run is merged into one group, so every narrated ref in it is handled in the same step:
> The self-reported figures [S1] (funding: per Pitch Deck Hunt, undated [S3]; per Crunchbase, undated [S4]; per Dealroom, undated [S5]) are unverified.
>
> The funding (per Pitch Deck Hunt and Crunchbase) [S3, S4] is unverified.

**Citations:** every ref is kept. A merged run is written as one group ("[S3] plus [S4]" becomes "[S3, S4]").

**Locality:**
- Runs in another clause are not this span's: "…, and [S4] plus [S5] is listed" stays as written.
- Company-only runs are left as written, including one before a narrated run in the same clause.
- A "self-reported" after its run ("[S3] plus [S4] are self-reported.") is handled.

All of these hold in both item orders, and a second run changes nothing.

## 3. Latest ISO date uses its day

**Before (304dede):** cash dated 2016-04-01 and 2016-04-30 gave "as of 2016-04-01" or "as of 2016-04-30" depending on item order. Dates in the same month tied, and the first one won.

**Now:** the full ISO date is compared, so 2016-04-30 wins in any item order, for both runway and cash. Fiscal-year labels are still never given a month.

## Results

[output/cases_probe.txt](output/cases_probe.txt) runs every case through the 304dede and 5c5502f code, in pipeline order, in both item orders, with idempotence checked:
- **At 304dede:**
  - "Today," survived unchanged;
  - "As of today," left " the …";
  - the [S4] plus [S5] case was not idempotent;
  - Crunchbase was never named;
  - the latest date flipped with item order.
- **At 5c5502f:** every case is correct and stable.

[output/memo95_probe.txt](output/memo95_probe.txt), time guard then funding guard: **identical** to the 49663be, 1d63239 and 304dede probes.

[output/memo94_probe.txt](output/memo94_probe.txt): **identical** to the earlier probes.

**New regressions:**
- `test_introductory_time_qualifier_through_both_guards`;
- `test_the_latest_date_uses_its_day_in_any_item_order`;
- `test_a_month_end_never_matches_a_bare_fiscal_year`;
- `test_every_group_governed_by_one_span_in_one_call`.

All earlier regressions and controls pass unchanged.

[output/mutations_output.txt](output/mutations_output.txt): **42 mutations run, all red.**
- **What was run:** the 12 new mutations (O1–O12), plus the 30 inherited ones targeting code this change touched or depends on: J5–J8, J13, J16, K8, K9, K14, L1–L6, M1–M11 and N1–N4.
- **O12 survived its first run** until a test with a company-only run before a narrated run was added.
- **M7 is now red.** 304dede wrongly called it equivalent; see `CORRECTION.md`.
- **Not re-run:** the other 55 inherited mutations, whose code is untouched. Their targets were verified, and their last runs are in the 304dede folder.
- **Fingerprints** are listed in the header. `claim_context.py` was mutated in its CRLF working copy, and its committed LF blob has identical content.

[output/validation_output.txt](output/validation_output.txt): on the committed code, isolated test databases, one batch at a time.
- `check` clean.
- `makemigrations --check`: no changes.
- 240 + 428 + 87 = **755 tests OK**.
- Consumers covered: claim-context dates, memo persistence and list rendering, IC memo/Markdown/Lite via the writer test, presentation, authorization, panel, library, notifications, paywall and company overview.

**Unchanged:**
- structured periods;
- fiscal-year distinctions;
- Truth Delta comparison and scoring;
- tier permissions;
- the raw-source memo boundary;
- the memo payload.

## Still open
- **RA-106:** until a newly generated memo is graded.
- **Qualifier and joiner detection is lexical:** the forms listed above.
- **The time guard's own vocabulary decides** which openings it removes; the funding guard only sees what remains.
- **`COMPATIBLE_MONTHS = 6`** is a stated threshold.
- Also open: RA-109/I1, RA-103, RA-108, PF-206 / FF-311.
