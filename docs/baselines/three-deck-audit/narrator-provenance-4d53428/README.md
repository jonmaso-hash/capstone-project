# Narrator provenance (FF-405) and Markdown charset (FF-411), at `4d53428`

**Separate, additive evidence.** It edits no earlier evidence folder. Memo 96 and its run artifacts
(`docs/baselines/manychat/funding-fidelity-9b6d215/`, branch `docs/manychat-funding-fidelity-9b6d215`, 5f08c05) are unchanged;
so are memos 90/91/94/95 and documents 3132/3133/3136/3137/3138.

**Status:** branch `fix/narrator-provenance` from main `9b6d215`, pushed, no PR. RA-106 and Zelda hardening stay pending. Not
deployed; paid-source Pass B not run.

| Commit | What |
|---|---|
| `afe0cab` | FF-405: `zelda_api/funding_fidelity.py` rule `_narrator_provenance`, regressions, memo-96 fixture `zelda_api/data/funding_fidelity/memo96.json` |
| `4d53428` | FF-411: `zelda_api/views.py` Markdown `text/markdown; charset=utf-8`, regressions in `zelda_api/tests.py` |

## FF-405 (P2, PHASE1-GROUNDING; graded in `OWNER_GRADING.md` at 5f08c05)

Memo 96's `zelda_advantage` credited Pitch Deck Hunt with `[C1, C2, C3]` and called it "the narrator of the funding and
traction claims". The grounded metadata gives Pitch Deck Hunt only C1/S3; C2/C3 are the company's checked traction
statements (S1/S2).

**The rule** (funding guard, after attribution; pipeline order unchanged: time guard, then funding guard):
- `FundingFacts.ref_sources` holds every item's (ref, narrator, kind of figure), read from the GroundedContext items.
- A citation group credited to a narrator (the next group after its name, in its clause, with no other subject between;
  or the group just before "reported by / per <narrator>") keeps only that narrator's refs. Each other ref is named under its
  own source: "[C2, C3] are the company's own traction statements", "[S4] is per Crunchbase", "[P1] is the profile". If none
  is the narrator's: "(not Pitch Deck Hunt's: …)".
- "<narrator> is the narrator/source of the X and Y claims" keeps only the kinds that narrator narrates, dropping a kind only
  when the context shows it is the company's own.
- **Kept as written:** correct attribution, company self-reports, a narrator named together with another ("Pitch Deck Hunt
  and Crunchbase list …"), possessives, questions and requests, kinds with no evidence either way.
- Only wording changes. No item, ownership, currency, period, score, tier or permission is touched; nothing reads source text.

**Memo 96, actual raw reply** ([output/memo96_replay.txt](output/memo96_replay.txt)): the recorded model reply, through the
pipeline's steps on the fix, equals stored memo 96 in 16 of 17 sections. Only `zelda_advantage` changes, and a second pass
changes nothing:

> …and the same figures as reported by the third-party aggregator Pitch Deck Hunt **[C1] ([C2, C3] are the company's own
> traction statements)**, correctly flagging that Pitch Deck Hunt is the narrator of the **funding claims** rather than an
> independent validator — …

Stored memo 96 is not regenerated or edited; the in-memory replay is the post-fix evidence.

**Earlier memos:** [memo95_probe.txt](output/memo95_probe.txt) is identical to every earlier memo-95 probe;
[memo94_probe.txt](output/memo94_probe.txt) is identical apart from the print order of one frozenset in its header line.

**One earlier assertion changed meaning.** `FigureIdentityTests.test_another_item_with_the_same_amount_keeps_its_own_source`
listed "Crunchbase reports $23.1M raised [S4]" (S4 = the company's own revenue item) as unchanged. It is still never Pitch
Deck Hunt's, but it now gains "(not Crunchbase's: [S4] is the company's own revenue statement)". That case moved to its own
assertion; the other six cases are unchanged.

**Regressions** (`zelda_api/tests_funding_fidelity.py`, `NarratorProvenanceTests` + one writer test):
- memo 96's sentence verbatim, both item orders, idempotent;
- memo 96's whole raw reply against the stored sections (fixture);
- paraphrases without an amount (whole group, one ref, citation before the narrator, kinds only, kinds in a list);
- mixed references (company + Crunchbase, profile);
- 15 unchanged controls (correct attribution, self-reports, co-narrators, possessive, questions, unknown kind);
- through `_generate_memo` to the stored memo, the staff full IC memo and the Markdown.

## FF-411 (P3)

The Markdown export is now `text/markdown; charset=utf-8` (the body was already UTF-8). Regressions: the header, the UTF-8
bytes of "•", "—" and "é", no double-encoding, and unchanged authorization (anonymous 302, stranger 404, non-Premium owner
redirected to the Lite page, staff 200). The existing content-type assertion was updated to the new header.

## Mutations ([output/mutations_output.txt](output/mutations_output.txt), harness [mutate_np.py.txt](output/mutate_np.py.txt))

18 mutations, all RED: N1–N16 on the rule, M1–M2 on the charset. N8 (drop a kind without company evidence) first survived;
the unknown-kind control was added, and N8 was then RED. Fingerprints unchanged after every group.

## Validation ([output/validation_output.txt](output/validation_output.txt))

249 + 430 + 87 = **766 tests OK** in three sequential batches under the memory watchdog; `check` clean; `makemigrations
--check`: no changes.

**Process note:** while preparing the first probe, a helper script was sourced with no arguments and started the full test
suite in this worktree. It was stopped after about two minutes (no process left), before any of the runs above; the tracked
`__pycache__` files it rewrote were restored before committing.

## Still open
- FF-406 ("as of April 2016"), FF-407 ("listed as Series A"), FF-413 (Truth Delta page renders as an unstyled fragment).
- RA-106 (until a newly generated memo is graded), RA-109/I1, RA-103, RA-108, PF-206/FF-311.
- Detection is lexical: a narrator credited across clauses, or by a pronoun, is not checked.
