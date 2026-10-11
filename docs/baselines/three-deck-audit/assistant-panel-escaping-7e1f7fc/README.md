# Assistant-panel HTML escaping at `7e1f7fc`

**Separate evidence** for `fix/assistant-panel-escaping`. It edits no earlier record. Documents
3132/3133 and memos 90/91 were not touched; their before/after hashes are below.

**Status: ungraded. Not deployed. Zelda hardening stays pending.**

**Method:** inert markers only. Payloads were `<b>bold-marker</b>`, `<b>cat-marker</b>` and
`<i>q-marker</i>`. No script, event-handler attribute or executable content was used anywhere: not
in fixtures, tests or the browser.

## Run record

| Item | Value |
|---|---|
| Date | 2026-10-11 PDT: unfixed 01:57–02:00, fixed 02:05–02:08 local (server log) |
| Unfixed code | `140032c` (origin/main), detached worktree `KCV-main-ro` |
| Fixed code | `7e1f7fc` on `fix/assistant-panel-escaping`, worktree `KCV-xss` |
| Server | Pass A wrapper. Paid keys `False`, broker/cache `redis://localhost`, `pending=0`, no worker. `tools/memwatch.ps1` logged no spike |
| Browser | Chrome (INVENTOROFTUES) via the Claude in Chrome extension. Positive controls `/?probe=xss-unfixed-control` and `/?probe=xss-fixed-control` |
| Fixtures | Disposable users `xssfix_premium` (318, premium founder), `xssfix_basic` (319, non-premium founder) and `xssfix_investor` (320); documents 3134/3135, each with a memo and one cited insight; a session-generated test password. Created by [logs/fixtures.py.txt](logs/fixtures.py.txt) and removed afterwards |
| Views driven | The panel's own global entry points, `loadMemoById(id)` (Memo tab) and `openZeldaIntelligence(id, 'intelligence')` (Intelligence tab), on a real signed-in page |

### Deviations

| # | Deviation |
|---|---|
| XD-1 | The fixtures were created with the founder profiles **private**. The memo API then returned 404 to the investor: the existing visibility rule, working as designed. The two disposable profiles were made non-private for the check. They have since been deleted |
| XD-2 | The Chrome extension disconnected during the first fixed-code batch, which had already signed in `xssfix_investor` and loaded both memos (02:00, fixed log). After reconnecting, that session was signed out with the nav button, and the fixed-code checks were re-run from a fresh login. Only the re-run is reported |

## Enforced CSP (captured; unchanged by the fix)

From [logs/csp_headers_enforced_and_report_only.txt](logs/csp_headers_enforced_and_report_only.txt):
- **Enforced:** `script-src 'self' 'nonce-…' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; script-src-attr 'unsafe-inline'`.
- **Report-only:** `script-src-attr 'none'`.

The enforced policy does **not** block inline event-handler attributes, so escaping at the sink is
the effective control. The fixed server sent a byte-identical enforced header.

## Results (rendered DOM, after the panel's fetch settled)

"Injected" means `<b>` or `<i>` elements created from API text. "Literal" means the marker shown as
visible text.

| View | Fixture | Unfixed `140032c` | Fixed `7e1f7fc` |
|---|---|---|---|
| Memo tab, full | 3134 as investor | **6 `<b>` + 1 `<i>` injected**; the name rendered as "Name **bold-marker** & Co" | **0 injected**; 5 literal `<b>bold-marker</b>` + `<b>cat-marker</b>` + `<i>q-marker</i>`; name shows `Name <b>bold-marker</b> & Co (premium)` |
| Memo tab, Lite | 3135 as investor | **4 `<b>` injected** | **0 injected**; 4 literal; no "Executive Summary" (Lite redaction kept) |
| Intelligence, full | 3134 as investor | **3 `<b>` + 1 `<i>` injected** (`browser/x00`) | **0 injected**; 3 literal + `<i>q-marker</i>` (`browser/x01`) |
| Intelligence, Lite | 3135 as investor | **4 `<b>` injected** | **0 injected**; 4 literal; Lite list keeps its line breaks (`browser/x02`) |
| Memo + Intelligence, locked | 3135 as owner `xssfix_basic` | — | "Unlock Your Intelligence Memo" card with the billing CTA, 0 sections, 0 injected (`browser/x03`); activity log has no injected markup |

**What the fix kept:**
- **Citations:** counts identical before and after the fix (full memo 8, Lite 3, Intelligence full
  5, Lite 3).
- **Newlines:** `white-space: pre-line` paragraphs keep their newlines (full memo 3, Lite 1).
- **Locked card for a non-owner:** this card prints the document name, but the server always sends
  Lite sections to a non-owner, so the browser cannot reach it. It is covered by the Node harness
  tests, along with the failed and bad-JSON states.

## Tests and validation

[logs/validation_output.txt](logs/validation_output.txt):
- `check` clean; `makemigrations --check` reports no changes.
- `zelda_api.tests_assistant_panel_escaping`: 8 tests OK, Node v25.1.0. It is in the blocking CI
  list.
- `zelda_api.tests` + `pages`: 945 OK.

[logs/mutations_output.txt](logs/mutations_output.txt): un-escaping each sink, and the whole unfixed
template from main, all go red (9 checks; the unfixed template gives 28 failures).

## Cleanup and frozen data

[logs/fixture_cleanup.txt](logs/fixture_cleanup.txt):
- **Inventory first.** Every row pointing at the fixtures through any foreign key: 52 rows. That
  covers the fixtures themselves, 12 investor interest events, 3 page events, 2 Data Room links and
  2 user settings rows.
- **Deletion.** Referencing rows were deleted explicitly first, then the fixture
  memos/insights/documents/profiles/users. The inventory afterwards reads **0**.
- **Queued task.** The fixture investor's save signal had queued one
  `matchmaking.tasks.refresh_matches_for_investor_task(71)` on the local broker. No worker ran, so it
  never executed. That one message was removed by task id, and the Redis lists are back to the
  pre-walk state (`high_priority` 18 only).

[logs/frozen_rows_before_after.txt](logs/frozen_rows_before_after.txt):
- memos 90/91 have the same sha256 of every stored field before and after;
- documents 3132/3133 have identical row counts, ids and timestamps.

## Out of scope, noted

- Other `innerHTML` sites in the same template were not changed. One example is the analyze flow's
  `${data.score}`, a number. Worth a separate sweep.
- The enforced CSP still allows inline handler attributes (`script-src-attr 'unsafe-inline'`). It
  was not changed here, as instructed. Tightening it is tracked by the report-only policy.
