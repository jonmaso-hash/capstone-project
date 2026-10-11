# RA-104 / BW-002 post-fix claim-count walks at `b455fe6` (ManyChat 3133 / report 87, Ben & Jerry's 3132)

**Separate, post-fix evidence.** This folder edits none of the earlier records, the protocol, the
answer keys or any ledger:
- ManyChat RA-104 in the rerun ledger;
- BW-002 in `PASS_A_BROWSER_WALKS_458bdc9.md` (`1ea6f06`);
- the staff observation in `bw007-postfix-2376857/`.

**Status: ungraded by the owner. Zelda hardening stays pending.** Not deployed.

## Run record

| Item | Value |
|---|---|
| Date | 2026-10-10 PDT: unfixed reproduction 21:56–22:00, fixed walks 22:41–22:48 local |
| Unfixed code | `59295b9` (origin/main with #273 merged), served from the `KCV-bw005` worktree, whose `.py`/`.html` are identical to main |
| Fixed code | `b455fe6` on `fix/claim-count-consistency`, worktree `KCV-ra104` |
| Server | Pass A wrapper. Six paid keys `False`, ANTHROPIC `True`. Broker, result backend and cache all `redis://localhost`. `pending=0`. Eager `False`. Same dev DB. **No worker.** `tools/memwatch.ps1` ran and logged no spike |
| Browser | Chrome via the Claude in Chrome extension. Positive controls `/?probe=ra104-unfixed-control` and `/?probe=ra104-fixed-control` appear in the server logs, and the page rendered signed out |
| Sessions | One principal at a time, each signed in through the real login form; staff completed TOTP MFA. Each signed out with the nav button, confirmed by a private page redirecting to `/accounts/login/` |
| Credentials | The same session-generated test password as the BW-005 walk (scratchpad only). TOTP computed per attempt |
| Documents | 3132 and 3133 as they were. Report 87 was read at display time: no upload, regeneration, verification or rewrite |

**Deviation (RC-1).** On the fixed code, Chrome's screenshot capture timed out on every attempt
(`Page.captureScreenshot` timed out after 30 s; the window was likely minimized). The post-fix
record therefore rests on:
- rendered-text and DOM probes, run after each page's JavaScript settled;
- same-origin API reads from the page;
- the server request log.

The two screenshots in `browser/` are from the **unfixed** reproduction only.

## 1. Cause (traced)

- `TruthDeltaReport.verifiability_stats()` counted `category_states()`, which has **one entry per
  category**.
- Every label that says "claims" read those counts:
  - the Truth Delta cards and "Claims Analyzed";
  - the page script total;
  - `coverage_sentence` ("none of the N claims");
  - the API counts;
  - the memo/overview signal;
  - "External data backs N of M claims";
  - the profile history line.
- The memo's "Claims checked" instead counted extracted `ClaimedDatapoint` rows.
- Report 87 holds **three** claims (funding_raised, usage, usage) in **two** categories. It is stored
  at `td.5`, with score `None` and risk `unknown`, and its stored summary contains no count.

## 2. Reproduction on `59295b9` (Chrome)

[logs/unfixed_59295b9_requests.log](logs/unfixed_59295b9_requests.log)

| Principal | Surface | Observed |
|---|---|---|
| `ramc_owner` | `/api/v1/zelda/documents/3133/verification/` | Cards: **2** Claims Analyzed, 0 Verified, **2** Not Established. Coverage: "none of the **2** claims". Claim list: **3** rows (FUNDING RAISED, USAGE, USAGE). Score "N/A /100 · NOT SCORED · LIMITED PUBLIC EVIDENCE". Owner reconciliation panel present |
| `ramc_owner` | `GET /api/v1/zelda/documents/3133/truth-delta/` | `verified_count 0`, `unverified_count 2`, coverage "none of the 2 claims", 3 `per_claim` rows, `category_states` = 2 keys, score `null` |
| `ramc_staff` (MFA) | `/api/v1/zelda/documents/3133/ic-memo/` | "**Claims checked: 3** · Verified 0 · Contradicted 0 · Not established 2 **(of 2)**" (`browser/r00`) |
| `ramc_staff` | Truth Delta page | "2 CLAIMS ANALYZED", caption "Of the claim categories Zelda cross-checked…" (`browser/r01`) |

## 3. The fix (`b455fe6`)

- `TruthDeltaReport.claim_stats()` counts **one per claim row**, in the state that row already
  shows (`per_claim_rows`). For older shapes it falls back first to comparison rows, then to
  `details['claims']`. It reads stored reports at display time.
- **Now read from claim counts:**
  - Truth Delta cards, script total, coverage sentence and chart;
  - API counts, plus a new `claims_analyzed` field;
  - memo/overview signal, where `claims_checked` is the same total;
  - "External data backs N of M claims";
  - profile history coverage line.
- **New reports:** the engine composes the summary's count sentence from per-claim counts.
- **Unchanged:**
  - `category_states()`, verification states and grounding;
  - `verifiability_stats()`;
  - `canonical_score`, which still reads the category counts;
  - the no-claims state;
  - `report.stats` on profile history.
- **Wording:** the coverage caption and chart label now say "claims", not "claim categories".
  `category_states` stays in the API as the separately labelled category view.

## 4. Post-fix walks (Chrome, `b455fe6`)

[logs/fixed_b455fe6_requests.log](logs/fixed_b455fe6_requests.log). "API" is
`GET /api/v1/zelda/documents/<id>/truth-delta/`, fetched same-origin from the page.

### ManyChat 3133 (report 87)

| Principal | Truth Delta cards (Analyzed / Verified / Not established) | Rows | Coverage sentence | Score box | API | Memo / overview | Reconciliation panel | Canary |
|---|---|---|---|---|---|---|---|---|
| `ramc_owner` | **3 / 0 / 3** | 3 | "none of the **3** claims" | N/A · NOT SCORED · LIMITED PUBLIC EVIDENCE | `claims_analyzed 3`, unverified 3, score `null`, tier lite, `category_states` 2 keys | owner memo is Lite, with no counter section | **visible** | none |
| `ramc_lite` | 3 / 0 / 3 | 3 | "none of the 3 claims" | same | 3, unverified 3, `null` | overview `/matchmaking/memo/profile/47/` 200: "none of the 3 claims"; IC memo 404 (unchanged) | absent | none |
| `ramc_paid` | 3 / 0 / 3 | 3 | "none of the 3 claims" | same | 3, unverified 3, `null` | overview 200: "none of the 3 claims" | absent | none |
| `ramc_staff` (MFA) | 3 / 0 / 3, "Zelda AI — Full Verification" | 3 | "none of the 3 claims" | same | 3, unverified 3, `null`, tier full | IC memo: "**Claims checked: 3** · Verified 0 · Contradicted 0 · Not established 3 **(of 3)**", "Evidence Credibility: not scored". Overview bar "Not established — 3 (of 3)" | absent | none |

On every principal, the coverage caption reads "Of the claims Zelda cross-checked…".

### Ben & Jerry's 3132 (no claims, no report)

| Principal | Truth Delta page | Script total | API | Memo / overview | Reconciliation panel | Canary |
|---|---|---|---|---|---|---|
| `rabj_owner` | "— /100 · NOT SCORED · NO VERIFIABLE CLAIMS", no stat cards, no "no public data" wording | 0 | `status no_claims`, score `null` | — | absent (0 claims) | none |
| `rabj_lite` | same | 0 | same | overview `/46/` 200, no count line (no report) | absent | none |
| `rabj_paid` | same | 0 | same | overview 200, no count line | absent | none |
| `rabj_staff` (MFA) | same, "Zelda AI — Full Verification" | 0 | same | IC memo 200: no "Claims checked" line; raw "(verification status: no_claims)" still shown (RA-013, not in scope) | absent | none |

**Access rules are unchanged:**
- Only the ManyChat owner sees the reconciliation panel.
- Investors' IC memo access is unchanged (404 for `ramc_lite`).
- Overviews are still for investors and staff only.

## 5. Validation

[logs/validation_output.txt](logs/validation_output.txt) holds the captured runner output and notes:
- `check` and `makemigrations --check` are clean.
- 12 new tests pass (`zelda_api.tests_claim_counts_per_claim`, now in the blocking CI list).
- Full `accounts` 293, `matchmaking` 884, and `pages` 517 pass. `pages` passed once the CI manifest
  was fixed.
- Full `zelda_api` (1426 tests): the only errors are 3 pre-existing, order-dependent
  `tests_grounded_context` errors, identical on main.
- One existing test pinned the defect ("claims checked 3" beside "(of 2)"). Its expectation is now 2.
- Six mutations each turn the new tests red. The score mutation needed a verified-plus-contradicted
  fixture: category score 100 vs claim score 50.

## After-walk controls

- **Documents 3132 and 3133:** row counts, max ids and timestamps match the pre-walk snapshot
  ([logs/after_walk_postcheck.txt](logs/after_walk_postcheck.txt)).
- **Report 87:** still `td.5`, score `None`, risk `unknown`, created 2026-10-11T00:55:58Z. It is the
  only report for 3133; 3132 has none.
- **Redis:** only the stale `high_priority` (18).
- **Fixed-server POSTs:** login 8, logout 8, staff-mfa verify 2. No verify, identity-check, valuation,
  analyze or ingest request. No 5xx.

## Still open

- Owner grading of all rerun, BW and post-fix records.
- BW-003 (the duplicated "No external data…" line per row) and RA-013 (raw state token) are not in
  this change.
- The full CI blocking job was not run in one local process because of RAM limits; CI gates it.
