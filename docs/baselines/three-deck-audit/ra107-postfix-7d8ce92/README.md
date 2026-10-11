# RA-002 / RA-107 / BW-004 post-fix memo list rendering at `7d8ce92` (memos 90 and 91)

**Separate, post-fix evidence.** This folder edits none of the earlier records, the saved memos,
the protocol or any ledger:
- Ben & Jerry's RA-002 and ManyChat RA-107 in the rerun ledgers;
- BW-004 in `PASS_A_BROWSER_WALKS_458bdc9.md` (`1ea6f06`);
- the staff observation in `bw007-postfix-2376857/`.

**Status: ungraded by the owner. Zelda hardening stays pending.** Not deployed.

## Run record

| Item | Value |
|---|---|
| Date | 2026-10-11 PDT: unfixed reproduction 00:10–00:12, fixed walks 00:37–00:41 local (server log) |
| Unfixed code | `140032c` (origin/main, saved-summary follow-up #275 merged), worktree `KCV-ra107` before the change |
| Fixed code | `7d8ce92` on `fix/memo-list-rendering` |
| Server | Pass A wrapper. Six paid keys `False`, ANTHROPIC `True`. Broker, result backend and cache all `redis://localhost`. `pending=0`. Eager `False`. Same dev DB. **No worker.** `tools/memwatch.ps1` logged no spike |
| Browser | Chrome (INVENTOROFTUES) via the Claude in Chrome extension. Positive controls `/?probe=ra107-unfixed-control` and `/?probe=ra107-fixed-control` appear in the logs, and the page rendered signed out |
| Sessions | One principal at a time through the real login form; staff completed TOTP MFA. Each signed out with the nav button, confirmed by the memo URL redirecting to `/accounts/login/` |
| Markdown export | Read with a same-origin `fetch()` from the signed-in page. No file was downloaded |
| Documents | 3132 and 3133 / memos 90 and 91 as they were: no upload, regeneration or verification |

## 1. Cause (traced)

- `IntelligenceMemo` stores every section in a `TextField`. When the memo model answers a section
  with a JSON array, `_generate_memo` passes the Python list through, and the TextField saves its
  `repr`.
- **Memo 91 (ManyChat)** therefore holds Python list literals in `supported_points` (2 items),
  `open_concerns` (4) and `questions_for_management` (10). Items containing apostrophes are
  double-quoted by `repr`.
- **Memo 90 (Ben & Jerry's)** holds the model's own JSON list text in `questions_for_management`
  (7 items).
- **Consumers** that printed the value as-is:
  - `ic_memo.html` (`<p>{{ section.text }}</p>`);
  - `render_ic_memo_markdown`;
  - the memo API (`DocumentMemoView` `sections` / `lite_sections`), which the assistant panel
    prints with `pre-line`;
  - the overview's `_first_points(memo.open_concerns)`.

## 2. Reproduction on `140032c` (Chrome)

[logs/unfixed_140032c_requests.log](logs/unfixed_140032c_requests.log)

| Principal | Surface | Observed |
|---|---|---|
| `ramc_owner` | IC memo 3133 (Lite) | Supported Points and Open Concerns in `<p>`, beginning `['The company states…` / `['The two primary scale metrics…`, 0 `<li>` (`browser/m00`) |
| `ramc_staff` (MFA) | IC memo 3133 (full) | Supported Points, Open Concerns and Questions for Management all Python list reprs, 0 `<li>` |
| `ramc_staff` | Markdown export, memo API | 3 raw `['…` lines in the Markdown; `sections.*` begin `['…` |
| `rabj_staff` (MFA) | IC memo 3132 (full) | Questions for Management begins `["What are Ben & Jerry's…`, 0 `<li>` (`browser/m01`). Supported Points and Open Concerns are prose bulleted with "•" |
| `rabj_staff` | Markdown export, memo API | 1 raw `["…` line; `sections.questions_for_management` begins `["…` |

## 3. The fix (`7d8ce92`)

`zelda_api/memo_lists.py` reads a section as a list **only** when the whole value is one of these:
- a native list or tuple of strings;
- a JSON list of strings;
- a Python list literal of strings, parsed with `ast.literal_eval` (never `eval`) and capped at
  50,000 characters;
- text whose every non-empty line is a `- ` bullet.

Anything else is shown **exactly as stored**:
- prose, including `[S1]` and `[S1, S2]` citations;
- "•"-bulleted prose;
- a value that is only a citation (`[S1]`);
- malformed or truncated literals;
- lists of numbers, nested lists and dicts.

Brackets are never stripped.

| Consumer | After the fix |
|---|---|
| IC memo HTML | `<ul><li>{{ item }}</li></ul>` (autoescaped); other sections unchanged; a stored `[]` is an empty section |
| Markdown export | `- item` lines |
| Memo API `sections` / `lite_sections` | `- item` lines (the assistant panel already renders `pre-line`) |
| Overview "worth investigating" | reads the concerns as text, not a repr |
| Future memos (`_generate_memo`) | lists and JSON-list text stored as `- item` lines; any other structure as JSON, never a repr |
| Saved rows | read at display time, never rewritten |

## 4. Post-fix walks (Chrome, `7d8ce92`)

[logs/fixed_7d8ce92_requests.log](logs/fixed_7d8ce92_requests.log)

| Principal | IC memo | List sections rendered | Markdown / API | Prose controls |
|---|---|---|---|---|
| `ramc_owner` (314) | 3133 200, Zelda Lite Memo | Supported Points `<ul>` **2** items, 2 citations; Open Concerns `<ul>` **4** items, 4 citations (`browser/m02`) | memo API: locked, owner gets no sections (unchanged) | Information Readiness and What Would Change the Picture still `<p>` |
| `ramc_lite` (315) | 3133 **404** (unchanged) | — | API locked, `lite_sections` only; `supported_points` = 2 `- ` lines, `open_concerns` 4 lines, no `[` | — |
| `ramc_paid` (316) | 3133 **404** (unchanged) | — | same as Lite | — |
| `ramc_staff` (317) | 3133 200, Zelda AI — Full Memo | Supported Points 2 / Open Concerns 4 / Questions for Management **10** `<li>`. The `'140,000+ bots'` apostrophe item survives; em dashes and citations survive (`browser/m03`) | Markdown: 0 raw-list lines, 10 question bullets. API: questions = 10 `- ` lines | What Would Change the Picture and Zelda Advantage still `<p>` |
| `rabj_owner` (310) | 3132 200, Lite | no list-valued Lite section; Questions for Management not in the Lite tier (unchanged) | — | Supported Points and Open Concerns ("•" prose) still `<p>`, unchanged |
| `rabj_lite` (311) | 3132 **404** (unchanged) | — | API locked, `lite_sections` only, no questions; supported points still "•" prose | — |
| `rabj_paid` (312) | 3132 **404** (unchanged) | — | same as Lite | — |
| `rabj_staff` (313) | 3132 200, Zelda AI — Full Memo | Questions for Management **7** `<li>`. "Ben & Jerry's" apostrophes, em dashes and 3 citations survive; the last item still ends `[S3]` (`browser/m04`) | Markdown: 0 raw-list lines, 7 question bullets; "## Supported Points" still opens with "•" prose. API: 7 `- ` lines | Supported Points, Open Concerns and Zelda Advantage still `<p>` |

**Item counts match the stored lists:** memo 91 has 2 / 4 / 10 and memo 90 has 7.

**Canaries:**
- `CANARY-MANYCHAT-4417` and `CANARY-BJ-2084` were absent from every memo page and API response
  checked.
- The raw "(verification status: no_claims)" token (RA-013) still shows on the B&J staff memo; it
  is out of scope.

## 5. Validation

[logs/validation_output.txt](logs/validation_output.txt), runner output:
- `check` clean; `makemigrations --check` reports no changes.
- 10 new tests pass (`zelda_api.tests_memo_list_rendering`, wired into the blocking CI list).
- Together with `tests_memo_persistence` and the CI-manifest test, 38 tests pass.
- Full `matchmaking` 884 and `pages` 517 pass.
- Full `zelda_api` (1448 tests): the only failures are the 3 pre-existing, order-dependent
  `tests_grounded_context` errors. Main has the same three, and the module passes 34/34 in
  isolation.
- `tests_memo_persistence` had pinned `str(list)` storage; it now expects `- ` lines, and JSON for a
  dict.

[logs/mutations_output.txt](logs/mutations_output.txt): seven mutations, all red:
- the template ignoring bullets;
- Markdown/HTML from the raw value;
- the API returning the raw value;
- the writer storing the repr;
- `eval` in place of `literal_eval`;
- global bracket stripping;
- `|safe` on items.

## After-walk controls

- **Memos 90 and 91:** the sha256 of every stored field is identical before and after
  ([logs/memo_rows_sha256_before_after.txt](logs/memo_rows_sha256_before_after.txt)).
- **Documents 3132 and 3133:** row counts, max ids and timestamps are unchanged
  ([logs/after_walk_postcheck.txt](logs/after_walk_postcheck.txt)).
- **Redis:** only the stale `high_priority` (18).
- **Server POSTs:** login, logout and staff-mfa verify only. No verify, identity-check, valuation,
  analyze or ingest request. No 5xx on either server.

## Still open

- Owner grading.
- RA-013 (raw state token) and BW-003 (duplicated "No external data" line) are separate items.
- The admin change form still shows the stored text as saved; it is a raw-data view.
- The assistant panel interpolates section text into `innerHTML` without escaping. That is
  pre-existing and not in this change; worth its own item.
