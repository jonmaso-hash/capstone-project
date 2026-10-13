# Funding-source fidelity: review blockers on `49663be`, fixed at `1d63239`

**Separate, additive evidence.** It edits none of these:
- the 49663be folder (`../funding-fidelity-49663be/`);
- the earlier funding-fidelity folders;
- the memo-95 run and its OWNER_GRADING.md (`docs/manychat-funding-fidelity-2948998`, 9688474);
- memos 94, 95, 90 and 91;
- documents 3132, 3133, 3136 and 3137.

**Status:**
- RA-106 and Zelda hardening stay pending.
- Memo 95 is not regenerated.
- Not deployed.

## Blocker 1: runway needs a dated cash balance and a compatible burn basis

**Before (49663be):** any company item with a digit and the word "cash" or "runway" turned the runway guard off for the whole memo. That included an undated "$2.1M cash in the bank", and a dated cash balance with no burn rate.

**Now:** each company item is classified by `cash_basis()` as a cash balance or a burn, in one of three states.

| State | When | Examples |
|---|---|---|
| **NONE** | Not company evidence at all | a narrator's figure; a profile field; no dollar amount; negated ("does not hold $2.1M in cash"); unknown ("undisclosed", "not disclosed"); a question; a cash *flow* |
| **PRESENT** | A figure, but not a basis | no structured as-of date (`as_of` is `not stated` or empty); historical ("previously had"); tentative ("expects"); conditional ("if hiring closes"); a burn without a rate ("Total burn of $1.8M") |
| **DATED** | A basis | an affirmative company figure with a structured as-of date (ISO period end, or `FYyyyy`) and, for a burn, a rate (per month, monthly, annual …) |

Only the structured `as_of` counts as a date, never a date in the wording. This is the same rule RA-102/106 applies.

**When the premise stands:**
- **Runway:** a DATED cash balance and a DATED burn rate dated within **6 months** of each other.
- **Cash** ("available cash"): a DATED balance.
- **Otherwise:** the premise is qualified, and the note says what the evidence actually holds.

| Evidence | Note after "runway (which needs a dated cash balance and burn rate; …)" |
|---|---|
| nothing (memo 95) | "neither is in the evidence" (unchanged) |
| dated cash only | "no burn rate is in the evidence" |
| dated burn only | "no cash balance is in the evidence" (no longer "neither") |
| undated cash | "the evidence's cash figure is not a dated balance and no burn rate is in the evidence" |
| undated or rateless burn | "the evidence's burn figure is not a dated rate" |
| both dated, periods apart | "the evidence's cash balance and burn rate are not from the same period" |

The 49663be positive test, where undated cash left the premise alone, is **revised**. Undated cash now keeps the guard.

Prompt rule 10 adds: undated, past or estimated cash or burn figures, and a burn rate from another period, are not a basis.

## Blocker 2: every narrated reference in a mixed group, in one pass

**Before (49663be):** only the first narrated entry in item order left the group. In "[S1, S3, S4]" (company traction, Pitch Deck Hunt, Crunchbase), one third-party ref stayed labelled self-reported. Which one depended on item order, and a second pass changed the text again.

**Now:**
- All narrated refs in the group move at once, in **citation order**, so item order does not matter.
- Each narrator gets its own attribution and keeps its own citation.
- The company's refs stay self-reported.

> Taking the self-reported figures at face value [S1], ManyChat had meaningful bot-platform traction by April 2016 and had raised a material amount of capital (per Pitch Deck Hunt, undated) [S3] and (per Crunchbase, undated) [S4].

**Other cases:**
- **One narrator, several refs:** "[C1, S3]" gets a single note.
- **Group of narrated refs only, beside company refs** ("traction [S1] with funding [S3, S4]"): the notes replace the group in place.
- **Sole group with two narrators:** "Funding (per Pitch Deck Hunt and Crunchbase) [S3, S4]".
- **Narrator already named in the clause:** left alone. This keeps the guard idempotent.

## Results

[output/blockers_probe.txt](output/blockers_probe.txt): each reviewer scenario, before and after, in memory, with every output guarded a second time.
- **At 49663be:**
  - undated cash bypassed the guard;
  - historical, negated and period-mismatched cash bypassed it too;
  - dated cash alone bypassed it;
  - burn-only said "neither";
  - the three-source group kept one third-party ref and was **not idempotent** in either item order.
- **At 1d63239:** every case is correct and idempotent.

[output/memo95_probe.txt](output/memo95_probe.txt): memo 95's raw model reply through the guards.
- Sections and text are **identical to the 49663be probe**: the three corrected passages.
- These stay as they were:
  - the conditional scenario;
  - both cash/runway questions;
  - "how much remains available";
  - "Runway: not calculated";
  - the self-reported traction lines.

[output/memo94_probe.txt](output/memo94_probe.txt): **identical** to the 49663be probe, and so to the 3481d8f probe.

**New regressions** (`zelda_api/tests_funding_fidelity.py`):
- **Cash and burn:**
  - the undated-cash test, revised;
  - dated cash with a compatible burn in three forms, including FY dates, in both item orders;
  - 14 insufficient-basis cases, each asserting its own note, never "neither" when a company burn figure exists, and the same result in reversed item order;
  - the cash premise with undated cash;
  - a supported runway keeping "alone".
- **Mixed groups:**
  - S1 + S3 (Pitch Deck Hunt) + S4 (Crunchbase), checked in both item orders and for idempotence;
  - citation order;
  - no funding clause;
  - an all-narrated group beside company refs;
  - a sole group with two narrators;
  - one narrator cited twice;
  - a narrator named in another clause;
  - a dated second narrator.

Earlier controls are all kept and pass: questions, "if" scenarios, unrelated runway, memo-95 verbatim sentences, and the writer → staff IC memo → Markdown → Lite API test.

[output/mutations_output.txt](output/mutations_output.txt): **70 mutations, all red**.
- **Inherited:** 32 F/G/H and 16 J. Eight J mutations were retargeted to the rewritten code with the same intent.
- **K1–K16:** blocker 1.
- **L1–L6:** blocker 2.
- **K7 survived its first run:** the "unknown" control had no dollar amount. The control was fixed and K7 is now red. K1–K6 were re-run on the final test file.
- **Fingerprints:** file sha256s were verified after every group, and they match the committed files.

[output/validation_output.txt](output/validation_output.txt): on the committed code, isolated test databases, one batch at a time.
- `check` clean.
- `makemigrations --check`: no changes.
- 232 + 428 + 87 = **747 tests OK**.

**Unchanged:**
- structured periods;
- Truth Delta comparison and scoring;
- tier permissions;
- the raw-source memo boundary (only item statements and structured `as_of` are read);
- the memo payload.

## Still open
- **RA-106:** until a newly generated memo is graded.
- **The 6-month compatibility window** is a stated threshold (`COMPATIBLE_MONTHS`), not derived from data.
- Also open: RA-109/I1, RA-103, RA-108, PF-206 / FF-311.
