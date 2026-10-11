# BW-005 / RA-010 / RA-112 post-fix company-overview walks at `f329697` (Ben & Jerry's 3132, ManyChat 3133)

**Separate, post-fix evidence.** The original failures stay where they were recorded. This folder
edits none of them, nor the protocol, the answer keys or any ledger:
- B&J RA-010 and ManyChat RA-112 in the rerun ledgers;
- BW-005 in `PASS_A_BROWSER_WALKS_458bdc9.md` (`1ea6f06`);
- the staff observations in `bw007-postfix-2376857/`.

**Status: ungraded by the owner. Zelda hardening stays pending.** Not deployed.

## Run record

| Item | Value |
|---|---|
| Date | 2026-10-10 PDT, 21:02–21:19 local |
| Unfixed code | `1f8c9fa`, origin/main with BW-007 merged (#272); worktree `C:\Users\jonathan\Desktop\KCV-bw005` before the change |
| Fixed code | `f329697` on `fix/company-overview-identity` |
| Server | Pass A wrapper. Six paid keys `False`, ANTHROPIC `True`. Broker, result backend and cache all `redis://localhost`. `pending=0`. Eager `False`. Same dev DB. **No worker.** `tools/memwatch.ps1` ran and logged no spike |
| Browser | Chrome via the Claude in Chrome extension. Positive controls: `GET /?probe=bw005-control` (unfixed) and `/?probe=bw005-fixed-control` (fixed) appear in the server log, and the page rendered signed out |
| Sessions | One principal at a time, each signed in through the real login form and signed out with the nav Sign out button. Every sign-out was confirmed by a private page redirecting to `/accounts/login/` |
| Credentials | The eight fixture principals (310–317) got a fresh test password generated this session, kept in the scratchpad. Staff TOTP codes were computed per attempt; no secret was recorded |
| Documents | 3132 and 3133 as they were: no upload, regeneration or verification |

## 1. Cause (traced)

- The "Company overview →" item on every report comes from `zelda_api/report_nav.py`. It built the
  URL from the company **name**: `/matchmaking/memo/<company_name lowered, spaces → hyphens>/`.
- `matchmaking.views.standalone_memo_view` turned that back into a name and called
  `get_object_or_404(Application, company_name__iexact=…)`.
- Company names are not unique. The dev DB holds 4 discoverable "Ben & Jerry's" profiles
  (39, 41, 44, 46) and 3 "ManyChat" (42, 45, 47), so `get()` raised `MultipleObjectsReturned`.
- Document 3132 is uploaded by `rabj_owner` (310), whose profile is **46**. Document 3133 is uploaded
  by `ramc_owner` (314), whose profile is **47**. `Application.user` is one-to-one, so the profile id
  is the stable identity.

## 2. Reproduction on `1f8c9fa` (Chrome)

[logs/unfixed_1f8c9fa_requests.log](logs/unfixed_1f8c9fa_requests.log):

| Principal | Start | Overview link on the page | Result |
|---|---|---|---|
| `ramc_paid` | `/api/v1/zelda/documents/3133/verification/` (200) | `/matchmaking/memo/manychat/` | **500** `MultipleObjectsReturned` "returned 3!" (`browser/q00`) |
| `rabj_paid` | `/api/v1/zelda/documents/3132/verification/` (200) | `/matchmaking/memo/ben-&-jerry's/` | **500** "returned 4!" |

## 3. The fix (`f329697`)

- **Canonical route** `memo/profile/<application_id>/` (`matchmaking:company_overview`). The report strip
  links it with the document owner's own profile id.
- **Legacy name URL** `memo/<name>/`: serves the page only when exactly one company **this viewer may
  see** has the name. Otherwise it returns 404. It never picks one of several. Hidden namesakes
  neither count nor leak.
- **Unchanged view body:** the same visibility rule (private, archived or denied profiles get 404),
  the same investor-or-staff rule (403 otherwise), and the same per-field visibility.
- No profiles were deleted or renamed. No fixture changed except the test passwords.

## 4. Post-fix walks (Chrome, `f329697`)

[logs/fixed_f329697_requests.log](logs/fixed_f329697_requests.log). "Evidence link" is the overview
page's own "Check the evidence" link, an independent check that the page shows the right company.

| Principal | Report page | Overview item on it | Overview page | Evidence link on overview | Tier | Canary | Legacy name URL |
|---|---|---|---|---|---|---|---|
| anonymous | — | — | `/matchmaking/memo/profile/47/` and `/46/` → 302 to login | — | — | — | — |
| `ramc_paid` (316) | 3133 Truth Delta, 200 | link `/matchmaking/memo/profile/47/` | **200**, h1 "ManyChat" (`q01`) | `…/documents/3133/verification/` | Zelda Lite Report | none (text and HTML) | `/matchmaking/memo/manychat/` **404** |
| `ramc_lite` (315) | 3133, 200 | link `/memo/profile/47/` | **200**, "ManyChat" | `…/3133/verification/` | Zelda Lite Report | none | 404 |
| `ramc_owner` (314) | 3133, 200 | locked, "Investor accounts only", no link | own `/47/` **403**; other `/46/` **403**, no B&J content | — | — | — | 404 |
| `ramc_staff` (317), MFA completed | 3133, 200 | link `/memo/profile/47/` | **200**, "ManyChat" (`q02`) | `…/3133/verification/`; IC memo link `…/3133/ic-memo/` | Zelda AI — Full Report | none | 404 |
| `rabj_paid` (312) | 3132, 200 | link `/memo/profile/46/` | **200**, "Ben & Jerry's" (`q03`) | `…/3132/verification/` | Zelda Lite Report | none | `/matchmaking/memo/ben-%26-jerry's/` **404** |
| `rabj_lite` (311) | 3132, 200 | link `/memo/profile/46/` | **200**, "Ben & Jerry's" | `…/3132/verification/` | Zelda Lite Report | none | 404 |
| `rabj_owner` (310) | 3132, 200 | locked, "Investor accounts only", no link | own `/46/` **403**; other `/47/` **403**, no ManyChat content | — | — | — | 404 |
| `rabj_staff` (313), MFA completed | 3132, 200 | link `/memo/profile/46/` | **200**, "Ben & Jerry's" (`q04`) | `…/3132/verification/`; IC memo link `…/3132/ic-memo/` | Zelda AI — Full Report | none | 404 |

**Privacy boundaries:**
- No overview page carried either deck's canary, in rendered text or in the HTML.
- No error page carried content from the other company.
- Investors see the same Lite tier as before (the founders are not Premium), and staff see the full
  tier.
- The ManyChat owner's Truth Delta page still renders the reconciliation panel. This run did not
  re-check that the panel stays absent for other principals.

**Owners get 403 on their own overview.** This is the existing access rule: the overview is "investor
profile or staff". The report strip already shows owners a locked item rather than a link. This fix
does not widen access. Whether owners should see their own overview is a product decision for the
owner.

## 5. Validation

[logs/validation_output.txt](logs/validation_output.txt):
- `check` and `makemigrations --check` are clean.
- 11 new regressions pass, and an overview-related batch of 111 tests passes.
- Full `matchmaking` (884), `pages` (517) and `zelda_api.tests` (428) pass.
- Three mutations each turn the new tests red.
- The full CI blocking job was not run locally because of RAM limits; CI gates it.

## After-walk controls

- **Documents 3132 and 3133:** row counts, max ids and timestamps match the pre-walk snapshot
  ([logs/after_walk_postcheck.txt](logs/after_walk_postcheck.txt)).
- **Redis:** only the stale `high_priority` (18).
- **Fixed-server POSTs:** login 8, logout 8, staff-mfa verify 2. No verify, identity-check, valuation,
  analyze or ingest request. No 500s.
- **Sessions:**
  - This browser's sessions all ended; each sign-out was confirmed.
  - The dev DB still holds one live session each for `rabj_owner` (310) and `ramc_owner` (314). These
    are not attributable to this walk: no session snapshot was taken before it, and this browser's
    sign-outs were confirmed. They were left in place.

## Still open

- Owner grading of all rerun, BW and post-fix records.
- The owner-access question above.
- Other name-keyed lookups were not audited in this change.
