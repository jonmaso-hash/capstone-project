# Funding-source fidelity at `2befa42`

**Separate evidence.** Nothing earlier is edited: the live run's ledger, its artifacts and
[OWNER_GRADING.md](https://github.com/jonmaso-hash/capstone-project/blob/docs/manychat-postfix-a975af3/docs/baselines/manychat/postfix-a975af3/pass-a/OWNER_GRADING.md)
on branch `docs/manychat-postfix-a975af3`, memo 94, frozen memos 90/91 and documents 3132/3133.

**Status:** RA-106 stays open. The owner graded the live run a partial pass, and this branch is the
scoped follow-up. Memo 94 is not regenerated: the fix applies to memos generated after it. Not
deployed; Zelda hardening is not complete.

## What memo 94 got wrong (owner: partial pass)

| Section (memo 94, verbatim) | Problem |
|---|---|
| `information_readiness` (Lite): "Funding raised figure (**self-reported**, unverified): $23.1M [S3]" | Pitch Deck Hunt's listing called the company's own report |
| `base_scenario`: "…and **stated funding of $23.1M** [S3]" | No narrator |
| `risk_assessment`, `open_concerns` (Lite), `zelda_advantage`: "The $23.1M raised figure [S3] was checked…" | No narrator in a standalone section |
| `what_would_change_the_picture` (Lite), questions (uncited): "…the $23.1M funding raised…", "Who are the investors behind the $23.1M raised…" | No narrator |
| `downside_scenario`: "…the **$23.1M raise** [S3] cannot be confirmed…" | Reported funding presented as a financing event |
| questions: "what runway does **the stated raise** provide", "use of proceeds from **this raise**"; `open_concerns`: "operate on **its stated raise**" | A current raise assumed; the evidence has none (profile `raising_amount=0`, not public) |
| `base_scenario`: "ManyChat **was a Series A** software company [P1, P2] with … traction **as of April 2016**" | Undated profile stage attached to a slide date |

## Fix

**`zelda_api/funding_fidelity.py`** (new) is applied after generation, per sentence, in every
section. It runs after the RA-106 time-wording guard.

- **Attribution.** A sentence that states a narrated figure names its narrator:
  - "self-reported" becomes "reported by Pitch Deck Hunt";
  - "the company states", when only the narrated figure is cited, becomes "Pitch Deck Hunt reports";
  - in a sentence mixing the company's figures with the narrated one, it becomes "the deck states", followed by "(per Pitch Deck Hunt)";
  - otherwise "(per Pitch Deck Hunt)" goes right after the figure's phrase.

  Sentences that already name the narrator, or cite the claim without stating the amount, are unchanged. So is the company's own "self-reported" traction.
- **Not an event.** "the $23.1M raise" becomes "the reported $23.1M".
- **No premise.** With no current raise in the evidence, "this raise", "the stated raise" and "its current round" become "any current or planned raise", and the question is kept. A current raise counts as evidence when:
  - there is a public "Raising (profile)" item above 0; or
  - a statement says "seeking", "raising", "use of proceeds" or "the ask".
- **Profile undated.** A sentence citing a profile item beside a date marks it "(current profile, undated)".

**Prompt rule 10** says the same.

**Unchanged:**
- structured periods;
- Truth Delta comparison and scoring;
- tier permissions (the Lite API still returns `tier: lite`, `locked: true` and the same five sections);
- the raw-source memo boundary (no source sentence in the model input);
- the memo payload.

## Results

[output/memo94_probe.txt](output/memo94_probe.txt): the guard applied in memory to memo 94's stored
text, with memo 94's real memo-input items and no DB access.
- 9 sections change, covering every row in the table above.
- The executive summary and financial analysis, which already named Pitch Deck Hunt, are unchanged.

`zelda_api/tests_funding_fidelity.py` (in the blocking CI list):
- **Unit tests:** memo 94's sentences verbatim, plus negative controls:
  - sentences already attributed;
  - the claim cited without the amount;
  - the company's self-reported traction;
  - other amounts ($2.31M, $23.15M);
  - an un-narrated figure;
  - legitimate questions ("What is the current monthly burn rate?", "Who led the 2019 Series A round?", "round-by-round");
  - a raise present in the evidence (public profile raise, "Seeking $5M"), and a zero raise that does not count;
  - undated profile lines and dated slide lines;
  - idempotence and layout.
- **Writer tests:** real ManyChat extraction, then GroundedContext, then `_generate_memo` (mocked reply with memo 94's sentences), then every consumer:
  - staff full IC memo;
  - staff Markdown download;
  - owner Lite IC memo;
  - investor Lite memo API (tier and locked unchanged);
  - investor company overview.

  They also check the stored memo, prompt rule 10, the raw-source boundary and that claim periods stay empty.

[output/validation_output.txt](output/validation_output.txt), on the committed code with isolated test databases:
- `check` clean; `makemigrations --check` reports no changes.
- Report consumers: 207 + 76 + 428 (`zelda_api.tests`) + 103 + 426 (`matchmaking.tests`) + 147 (accounts/pages) = **1,387 tests, all OK**.
- The first pass failed 5 writer tests in `tests_claim_context_dates`:
  - Two were real wording problems, fixed and regression-tested: a mixed-source sentence that kept "The company states … (per Pitch Deck Hunt)", and "$23.1M (per …) listed" splitting the figure's phrase.
  - Three expected the old, unattributed wording and were updated.
  - Everything was then re-run.

[output/mutations_output.txt](output/mutations_output.txt): **14 mutations, all red**:
- F1 attribution off;
- F2 / F3 "self-reported" kept, or reassigned when it covers other figures;
- F4 "the $X raise" kept;
- F5 / F6 premises kept, or rewritten despite a real raise;
- F7 / F8 profile label off, or added without a date;
- F9 pipeline not applying the guard;
- F10 / F14 figure phrase split;
- F11 a zero raise counted;
- F12 narrator added twice;
- F13 mixed-source "the company states".

## Still open

- **RA-106:** until a new memo is generated and graded. Memo 94 is unchanged by design.
- **Upside scenario:** "the $23.1M raised … was fully deployed into growth" is a hypothetical framed as a requirement. It now carries attribution, but its premise is left to prompt rule 10.
- **Rewrites, not rewording:** the guard does not restructure sentences. "ManyChat was a Series A … [P1, P2] (current profile, undated)" keeps the model's past tense.
- **Also open:** RA-109 / I1, RA-103, RA-108, PF-206 (Section Coverage by tier).
