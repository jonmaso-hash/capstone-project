# Addendum: staff Truth Delta page in Chrome (document 3138, memo 96)

**Additive.** This file and its folder change nothing in [../RERUN_LEDGER.md](../RERUN_LEDGER.md) or any other run artifact.
It closes deviation D-6: during the run, the staff Truth Delta page was checked by in-page fetch, not by navigation.

| Item | Value |
|---|---|
| Date | 2026-10-13, 01:34–01:36 local (08:34–08:36 UTC) |
| Code | Same detached worktree `KCV-mc-ff3`, HEAD `95f6fa5` (evidence-only commit on `9b6d215`; no `.py` or template difference from 9b6d215) |
| Database | The same isolated run copy (`mcff3/db_ff3_copy.sqlite3`); server only (no worker); Redis 3/4/5; gates in [server_addendum.log.txt](server_addendum.log.txt): paid keys false, `is_copy=True`, `pending=0` |
| Uploads / generation | **None.** No upload, no report or memo regenerated, no model call |
| Memo 96 / document 3138 | Read-only snapshot before and after the walk: identical (`1f23b917…493a`) ([before](memo96_snapshot_before_addendum.txt), [after](memo96_snapshot_after_addendum.txt)) |
| Watchdog | `tools/memwatch.ps1` running; no process crossed 1,500 MB |

## Walk (Chrome, one new tab, closed afterwards)

1. Direct navigation to `http://127.0.0.1:8000/api/v1/zelda/documents/3138/verification/` while signed out: redirected to `/accounts/login/?next=/api/v1/zelda/documents/3138/verification/` (`signed_in=false`).
2. Real login as `ff3mc_staff` (form fields set, `form.requestSubmit()`), then the real staff-MFA page `/accounts/staff-mfa/verify/` with a current TOTP code; MFA POST then `GET …/verification/` 200.
3. **Direct navigation** to the same URL again (200, 59,260 bytes). Waited 3 s, then took two snapshots 2.5 s apart: identical text length and counts (`stable: true`), `readyState` `complete`, no loading text.

| Check | Result |
|---|---|
| Counts | **3 CLAIMS ANALYZED · 0 VERIFIED · 3 NOT ESTABLISHED**; "NOT SCORED · LIMITED PUBLIC EVIDENCE"; badge "Zelda AI — Full Verification"; 12 pages analysed |
| Claims shown | $23.1M, 500M and 140,000+ all present |
| Owner reconciliation | **Absent**: no "Profile and deck figures to review", no "Only you can see this" |
| Canary | **Absent** from the rendered text and from the raw HTML |
| Positive control | The page rendered staff-only full verification (anonymous gets 302); the page itself has no nav, so identity was confirmed by fetching `/` in the same session: "Account menu for ff3mc_staff" |
| Screenshot | [staff_truth_delta_page.jpg](staff_truth_delta_page.jpg) |

4. Sign out: navigated to `/` (account menu for `ff3mc_staff`), clicked the nav **Sign Out** (`POST /accounts/logout/` 302 → `/home/`).
5. Direct navigation to the Truth Delta URL again: redirected to `/accounts/login/?next=/api/v1/zelda/documents/3138/verification/`, title "Log in", `signed_in=false`.

## New observation (not fixed; outside this run's scope)

| ID | Layer | Principal | Observation | Bucket | Sev |
|---|---|---|---|---|---|
| FF-413 | 10 | every principal who opens the page directly | `templates/truth_delta_dashboard.html` is a standalone fragment (no doctype, no `{% extends %}`; a single inline `<style>` and no site stylesheet). Navigated directly, it renders in quirks mode with default serif type and no site navigation ([screenshot](staff_truth_delta_page.jpg)). The assistant panel also requests this URL (`zelda_ai_assistant_enhanced.html`), which may be why it is a fragment; not investigated. Content, counts and privacy are correct | PRODUCT-UI | P3 |
