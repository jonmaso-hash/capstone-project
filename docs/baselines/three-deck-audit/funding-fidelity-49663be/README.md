# Funding-source fidelity: FF-302 / FF-303 / FF-305 at `49663be`

**Separate, additive evidence.** It edits none of the earlier funding-fidelity folders, the memo-95 run
(`docs/baselines/manychat/funding-fidelity-2948998/` on branch `docs/manychat-funding-fidelity-2948998`, including its
OWNER_GRADING.md at 9688474), memo 95, memo 94, memos 90/91 or documents 3132/3133/3136/3137.

**Status:** RA-106 and Zelda hardening stay pending. Memo 95 is not regenerated; the fix applies to memos generated
after it. Not deployed.

## Owner findings on memo 95 (partial pass), and the change

| Ledger | Memo 95 (verbatim, as stored) | With this change |
|---|---|---|
| FF-302 (P3) | "• reported by Pitch Deck Hunt funding raised: $23.1M [S3]" | "• Funding raised (reported by Pitch Deck Hunt): $23.1M [S3]" |
| FF-303 (P2) | "This alone would allow the traction figures [S1, S2] … and would anchor assessment of the $23.1M funding figure (per Pitch Deck Hunt) [S3] against remaining runway." | "This would allow … against runway (which needs a dated cash balance and burn rate; neither is in the evidence)." |
| FF-305 (P2) | "Taking the self-reported figures at face value [S1, S2, S3], ManyChat had meaningful bot-platform traction by April 2016 and had raised a material amount of capital." | "Taking the self-reported figures at face value [S1, S2], ManyChat had meaningful bot-platform traction by April 2016 and had raised a material amount of capital (per Pitch Deck Hunt, undated) [S3]." |

**How each change works:**
- **FF-302.** "self-reported" describing a narrated figure is reworded by form:
  - a label becomes "X (reported by …):";
  - a parenthetical or predicate becomes "reported by …";
  - an adjective is dropped, with "(per …)" after the figure.
- **FF-305.** The narrated item is found **by citation**, with no amount needed:
  - The company's refs stay in the self-reported group.
  - The narrated ref moves to the end of the first stretch about funding after that group, marked "undated" when its as-of is "not stated".
  - If nothing later is about funding, it becomes a parenthetical beside the group.
  - A sole cited paraphrase is attributed too: "Funding (per Pitch Deck Hunt) [S3]".
- **FF-303.** Applies to a statement about the funding figure, found by amount or citation. "remaining / existing / available runway or cash" and "runway / cash remaining / left" are qualified, and "X alone would" loses "alone". Left unchanged:
  - questions;
  - "if" / "unless" / "assuming" / "whether" scenarios;
  - runs whose evidence has the company's own cash or runway figure (a third party's does not count).

**Prompt rule 10** now says the same.

**Unchanged:** structured periods, Truth Delta comparison and scoring, tier permissions (the Lite API is still `tier: lite`, `locked: true`), the raw-source memo boundary, and the memo payload.

## Results

[output/memo95_probe.txt](output/memo95_probe.txt): memo 95's raw model reply through the new guards, in memory.
- **Exactly three sections differ** from stored memo 95: the three rows above.
- These stay as they were:
  - the conditional upside scenario;
  - "how much remains available" (stated as unknown);
  - both cash and runway questions;
  - "Runway: not calculated";
  - all company traction marked "self-reported".
- The guard is idempotent.

[output/memo94_probe.txt](output/memo94_probe.txt): memo 94's probe output is **identical** to the 3481d8f probe.

**Regressions** (`zelda_api/tests_funding_fidelity.py`):
- **Memo-95 sentences verbatim:** the label, the mixed `[S1, S2, S3]`, the runway premise, and the three traction lines that must stay self-reported.
- **Other wording forms:** parenthetical, predicate, adjective, adjective opening the sentence.
- **Cited paraphrases without an amount:** sole, claim ref in the group, no separate funding clause; a dated narrated item is not called "undated".
- **Kept unchanged:** questions (one using "remaining runway"), "if" scenarios, "how much remains available", "Runway: not calculated", and a runway sentence unrelated to funding.
- **Cash evidence:** a real company cash balance keeps the wording; a third party's does not count.
- **Idempotence.**
- **Writer test:** memo 95's sentences through `_generate_memo`, then the stored memo, the staff full IC memo, the staff Markdown, and the Lite memo API (tier unchanged). It also checks prompt rule 10 and the raw-source boundary.

[output/mutations_output.txt](output/mutations_output.txt): **48 mutations, all red.**
- **16 new:** J1–J16.
- **32 earlier** (F/G/H), retargeted to the new rule list.
- **J10** (questions not exempt) survived twice before its test was fixed:
  - no preserved question used the premise wording;
  - the added question ended "…, if any?", which the "if" rule also keeps.

  The question now relies on the question check alone. File hashes were verified after every group.

[output/validation_output.txt](output/validation_output.txt), on the committed code with isolated test databases, one batch at a time:
- `check` clean; `makemigrations --check` reports no changes.
- 225 (funding, dates, grounded context, memo and presentation modules, CI manifest) + 428 (`zelda_api.tests`) + 87 (authorization, panel, library, notifications, paywall, company overview) = **740 tests, all OK**.

## Still open

- **RA-106:** until a newly generated memo is graded.
- **Tense:** labels and notes only, no sentence restructuring.
- Also open: RA-109/I1, RA-103, RA-108, PF-206 / FF-311.
