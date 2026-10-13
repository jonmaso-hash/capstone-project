# Correction to this folder's M7 claim (added at 5c5502f)

This file is additive. The README and `output/mutations_output.txt` in this folder are left exactly as committed at 7dd9195.

**What 304dede's evidence said:** M7 is an equivalent mutant: "no input can tell it apart". M7 drops the month-vs-fiscal-year kind check in `same_period`. The README said "no input can tell it apart", and the header of `mutations_output.txt` said "they can never be equal or within 6".

**Why that was wrong:** the claim holds only for ISO dates with years 0834 and later.
- **What `_AS_OF` accepts:** any four-digit year, and a month index is `year*12 + month`.
- **The counterexample:** an `as_of` of `0168-08-31` gives month index 2024, which is equal to `FY2024`. Without the kind check, `same_period(('month', 2024), ('fy', 2024))` returns True.
- **So M7 is not equivalent.** At 304dede it simply had no test that could kill it.

**What changed at 5c5502f:** `test_a_month_end_never_matches_a_bare_fiscal_year` tests `same_period`'s contract directly, with those exact values. M7 is now **red**: see `../funding-fidelity-5c5502f/output/mutations_output.txt`.

The 304dede result should therefore read **84 red, 1 survived (M7, a test gap)** rather than "84 red, 1 equivalent".
