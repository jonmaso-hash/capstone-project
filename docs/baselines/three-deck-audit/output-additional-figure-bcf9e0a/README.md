# Review of ed29f3b addressed: additional figures kept at `bcf9e0a`

**Separate, additive evidence.** It edits nothing in `output-parenthetical-ed29f3b/`, any earlier review or grade, the memo-99 run evidence, any historical memo, frozen fixture or ledger. The review itself is recorded in [`../output-parenthetical-review-ed29f3b/`](../output-parenthetical-review-ed29f3b/README.md). No live model run was made.

**Status:** branch `fix/basis-label-source-context`, **unmerged**, with no PR. Main is still `64f9db5`.
- RA-109 live output acceptance stays open.
- RA-106's scoped acceptance is unchanged.
- RA-108 and overall hardening are out of scope and still open.

| Commit | What |
|---|---|
| `1bb993b` / `ed29f3b` / `b38bb22` | Asides checked like the rest of the clause, citation-check reachability, evidence (reviewed: changes required) |
| `bcf9e0a` | **This correction:** a figure must be one the cited statements hold (`zelda_api/basis_fidelity.py`); regressions in `zelda_api/tests_output_fidelity.py` |

## The finding and what changed

At `ed29f3b`, `_plain_words()` accepted any token starting with a digit or `$`, so an extra figure passed the word check and the restatement then discarded it. Now:
- **A figure passes only when its value is one the cited statements hold**, with nothing after it but those statements' own words. "250M" is not held, so it keeps the sentence. "500M/day" has the held value but another interval, and "$500M" another currency, so both keep it too. A lone "$" is never a held value.
- **Digit grouping:** a statement's space-grouped digits are joined before its values are read. The source writes "140 000+" where memo 99 writes "140,000+". Without this, the first version of the fix broke memo 99's accepted repairs (seven module tests failed), so the join is part of `bcf9e0a`.
- **Anything else uncertain** still keeps the sentence. A figure written another way (for example "500 million" for "500M", or a space-grouped figure in the memo's own text) does not match, so the sentence is left as written.

| Input | Output at `bcf9e0a` |
|---|---|
| "The company states the message figures (250M messages/month) on the same slide [S2, S3]." (**exact review probe; full sequence**, memo-99 payload, and helper) | unchanged |
| "The company states the message figures ((250M messages/month)) on the same slide [S2, S3]." (**nested; full sequence** and helper) | unchanged |
| "… (500M (250M messages/month)) …" | unchanged |
| "The company states 250M messages/month on the same slide [S2, S3]." (outside parentheses) | unchanged |
| "The figures (250M and 500M) appear on the same slide [S2, S3]." | unchanged |
| "The company states 500M/day on the same slide [S2, S3]." | unchanged |
| "… ($500M) …" and "… ($ 500M) …" | unchanged |
| "The company states the message figures (500M, 500M/month) on the same slide [S2, S3]." | **still restated** (accepted positive control) |
| Memo 99's "… 140,000+ bots and 500M messages (measurement basis questioned; see open concerns) on a slide headed 'Traction by Apr-16' [S1, S2, S3] …" and "… either 500M total or 500M/month (measurement basis unresolved; see open concerns) on the same traction slide [S2, S3]." | **still restated**, as accepted |

All emitted text is in [output/emitted_text_probes.json](output/emitted_text_probes.json): 45 cases at `bcf9e0a`. The 35 carried from `ed29f3b`'s probes emit **identical** text and changes. All 10 new cases are unchanged with no change recorded.

## Replay of the actual memo replies

[output/replay_memos_96_97_98_99_bcf9e0a.json](output/replay_memos_96_97_98_99_bcf9e0a.json): memos 96, 97, 98 and 99 are **identical** to `ed29f3b`'s replay, which was itself identical to the accepted replay. Memo 99 still changes only `open_concerns`, `supported_points` and `business_model_analysis`, with the same repaired text. Memo 98's accepted corrections are unchanged.

## Evidence

### Red ([output/red_run_on_ed29f3b.txt](output/red_run_on_ed29f3b.txt))

The new test was run against the application code at `ed29f3b` (blob `c55af9f…`): **10 failures**, every case:
- the exact probe and the nested probe through the full sequence;
- all eight helper cases.

The file was restored and its SHA-256 checked afterwards. A first red run used "500M messages/day", which passed on the old code because "day" was already a rejected word. It was replaced with "500M/day", which tests the words after a figure, before this record's red run.

### Green

**`bcf9e0a`:** 103 OK ([output/green_module_bcf9e0a.txt](output/green_module_bcf9e0a.txt)).

### Mutations

Labels: `tests_output_fidelity`, `tests_funding_fidelity` and `tests_usage_basis` (247 tests). The 60 from `ed29f3b` are carried unchanged; no anchor moved. New:

| ID | Mutation |
|---|---|
| P22 | Any figure is accepted (only the words after it are checked) |
| P23 | A held figure's interval or unit is not checked ("500M/day" passes as 500M) |
| P24 | The cited figures' values are not known (no figure is ever placed: the positive controls and memo 99 fail) |
| P25 | The currency sign is dropped from a value ("$500M" passes as 500M) |
| P26 | A statement's space-grouped digits are not joined ("140 000+" is not "140,000+") |
| P27 | No guard for a lone "$" (the helper raises) |

**Result: 66 of 66 caught.** Each new mutant was also run alone first, and all were caught.

| Part | Mutants | Free RAM before |
|---|---|---|
| [1](output/mutations_bcf9e0a_part1.txt) | O1–C7 (22) | 1.37 GB |
| [2, interrupted](output/mutations_bcf9e0a_part2_interrupted.txt) | C8–L2 (9 of 22) | 1.51 GB |
| [3a](output/mutations_bcf9e0a_part3a.txt), [3b](output/mutations_bcf9e0a_part3b.txt), [3c](output/mutations_bcf9e0a_part3c.txt), [3d](output/mutations_bcf9e0a_part3d.txt), [3e](output/mutations_bcf9e0a_part3e.txt) | L3–P27 (35) | 0.58, 2.15, 2.20, 2.22, 2.19 GB |

**Interruption:** during part 2, Claude Code stopped the run and the watchdog for low memory while the session was idle. The run stopped after L2, *between* mutants. The worktree was clean and the three guard/pipeline files matched their pre-run hashes. Nothing was restarted until the owner approved. After that, the watchdog was restarted and the remaining 35 mutants ran in foreground chunks. Each chunk refuses to start unless the hashes match.

Every restore was SHA-256 checked. The three files are identical before and after the whole campaign: [output/pre_mutation_hashes_bcf9e0a.txt](output/pre_mutation_hashes_bcf9e0a.txt), [output/post_mutation_hashes_bcf9e0a.txt](output/post_mutation_hashes_bcf9e0a.txt).

### Validation at `bcf9e0a`

`manage.py check`: no issues. `makemigrations --check --dry-run`: no changes ([output/check_and_migrations.txt](output/check_and_migrations.txt)).

The four established batches ran sequentially in the foreground, with the watchdog running and a 1.2 GB gate:

| Batch | Free RAM before | Result |
|---|---|---|
| A | 2.18 GB | 362 OK (361 + the new test) |
| B | 2.21 GB | 415 OK |
| C | 2.10 GB | 430 OK |
| D | 2.07 GB | 186 OK |

**1,393 tests OK.** The watchdog logged nothing over 1,500 MB in either session ([output/memwatch_f.log.txt](output/memwatch_f.log.txt)).

**Commands** are in `output/scripts/`:
- **Mutation runner:** `mutate_e29.py.txt`, which carries `mutate_p.py.txt` → `mutate_b54.py.txt` → `mutate_review.py.txt` → `mutate_bridge.py.txt` → `mutate_ra109_review.py.txt`. It is driven by `mut_chunk.sh.txt`.
- **Batches:** `batch_one.sh.txt` and `t.sh.txt` (CI env, memory broker, `--parallel 1`).
- **Probes and replay:** `probe_f.py.txt` and `replay_memos.py.txt`, run through `shell.sh.txt`.

## Isolation and limits

- **Isolation:** test databases only. No network, provider or model call; no memo regenerated; no frozen artifact edited; no deployment; no paid-source Pass B. No credentials in this folder (leak-checked).
- **Bounded and lexical:** figures are matched by value text, not by meaning. A held figure written differently ("500 million", "0.5B") is treated as unknown and keeps the sentence. That is the conservative fallback the review asked for.
- **Not proven live:** live behaviour still needs a post-merge sample after review.
