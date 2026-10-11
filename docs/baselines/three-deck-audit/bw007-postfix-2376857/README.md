# BW-007 post-fix staff browser walks at `2376857` (Ben & Jerry's 3132, ManyChat 3133)

**Separate, post-fix evidence.** The baseline browser walks are recorded at `1ea6f06` on
`docs/two-deck-rerun-458bdc9` (`PASS_A_BROWSER_WALKS_458bdc9.md`). There, the staff result stays
**blocked by BW-007**. This folder does not edit that record, the protocol, the answer keys or any ledger.

**Status: ungraded by the owner. Zelda hardening stays pending.** This evidence closes only the staff
browser-walk gap that BW-007 left open.

Data: [16_staff_browser_walks.json](16_staff_browser_walks.json). Screenshots are in `browser/`, and
server-side probe logs and the after-walk check are in `logs/`.

## Run record

| Item | Value |
|---|---|
| Date | 2026-10-10 PDT, 20:14–20:31 local |
| Unfixed code | `458bdc9` (origin/main), in the worktree `C:\Users\jonathan\Desktop\KCV-bw007` before the change |
| Fixed code | `2376857` on `fix/staff-mfa-referrer-policy` |
| Server | Pass A wrapper. Six paid keys `False`, ANTHROPIC `True`. Broker, result backend and cache all `redis://localhost`. `pending=0`. Eager `False`. **No worker.** `tools/memwatch.ps1` ran throughout |
| Instrumentation | A scratchpad-only middleware, [logs/origin_probe.py.txt](logs/origin_probe.py.txt), not repo code. On `/accounts/staff-mfa/` and `/accounts/logout/` it logs the request's `Origin` and `Referer`, the status and the response's `Referrer-Policy`. It logs no bodies, cookies, tokens or codes |
| Browser | Chrome via the Claude in Chrome extension. Positive control: `GET /?probe=bw007-control` appears in the server log |
| Principals | `ramc_staff` (317), `rabj_staff` (313) |
| Documents | 3132 and 3133 as they were: no upload, regeneration or verification |

### Deviations

| # | Deviation | Why |
|---|---|---|
| PF-1 | Both staff fixtures got a new test password, generated this session and kept in the scratchpad. MFA enrolment was not reset. TOTP codes were computed per attempt from the stored credential. No setup key or recovery code was shown or recorded | Credential handling |
| PF-2 | As in the baseline (BW-3), forms were filled through `form.elements` and sent with `requestSubmit()`. Sign-outs used the nav button's own `click()` | Tooling. The server sees an ordinary same-origin form POST, and the probe log shows the browser's real headers |
| PF-3 | The unfixed reproduction stranded `ramc_staff` again. It was freed by deleting user 317's single DB session row, as in baseline BW-4 | No in-browser way out, which is the defect |
| PF-4 | `rabj_staff` viewing the owner profile sent one `POST /matchmaking/profile/rabj_owner/duration/`, the page's view-time beacon (baseline BW-5) | Side effect of a protocol surface |

## 1. Reproduction on `458bdc9`

The test fixed what the real request carried, as recorded in [logs/unfixed_458bdc9_origin_probe.log](logs/unfixed_458bdc9_origin_probe.log):

| Request | Response `Referrer-Policy` | Request `Origin` | `Referer` | Result |
|---|---|---|---|---|
| `GET /accounts/staff-mfa/verify/` | `no-referrer` | — | login page | 200 |
| `POST …/verify/`, valid fresh TOTP | — | **`null`** | absent | **403** "Origin checking failed - null does not match any trusted origins." (`browser/p00`) |
| `POST /accounts/logout/` from the MFA page | — | **`null`** | absent | **403**, same reason |

The page has no `<meta name="referrer">`, and the template and middleware set nothing else. The
header comes only from `accounts/staff_mfa.py` `response_page()`. Its CSP `default-src 'none'`
blocks in-page fetches, so the effective policy was read from the server side. Django's 403 page
carried `same-origin`, the site-wide `SECURE_REFERRER_POLICY` default. The MFA view was the only
override.

## 2. The fix (`2376857`)

`response_page()` now sends `Referrer-Policy: same-origin` instead of `no-referrer`. The CSRF
middleware, tokens, origin checking, `CSRF_TRUSTED_ORIGINS`, MFA requirements, CSP, `no-store` and
the template are unchanged. No route is exempted and `null` is not trusted. The referrer still never
leaves the site, and the MFA pages hold no secret in their URLs.

## 3. Post-fix in Chrome

From [logs/fixed_2376857_origin_probe.log](logs/fixed_2376857_origin_probe.log):

| Step | Principal | Request `Origin` | Result |
|---|---|---|---|
| MFA page `GET` | both | — | 200, `Referrer-Policy: same-origin` |
| Sign out **before** MFA | ramc_staff | `http://127.0.0.1:8000` | 302; the 3133 page then redirects to login |
| Invalid code `000000` | ramc_staff | `http://127.0.0.1:8000` | 200 with "Invalid or already-used code"; not verified |
| Valid TOTP | ramc_staff | `http://127.0.0.1:8000` | 302 to `/api/v1/zelda/documents/3133/verification/` |
| Valid TOTP | rabj_staff | `http://127.0.0.1:8000` | 302 to `/api/v1/zelda/documents/3132/verification/` |
| Nav Sign out | both | `http://127.0.0.1:8000` | 302; the private page then redirects to login |

## 4. Staff walk results (observations only, ungraded)

| Surface | ManyChat 3133 (`ramc_staff`) | Ben & Jerry's 3132 (`rabj_staff`) |
|---|---|---|
| Truth Delta page | 200, "Zelda AI — Full Verification", N/A /100 "NOT SCORED · LIMITED PUBLIC EVIDENCE". The cards say "2 CLAIMS ANALYZED" and the text says "none of the 2 claims", above **3** rows (FUNDING RAISED, USAGE, USAGE). "No external data was found for this claim." appears 6 times. Empty and loading placeholders are hidden (`p01`) | 200, "— /100 NOT SCORED · NO VERIFIABLE CLAIMS", no "no public data" wording, placeholders hidden (`p03`) |
| IC memo (staff full memo) | 200, "Zelda AI — Full Memo". **3 list sections render as Python list repr**; the third is a list of questions. Shows "has raised $23.1M to date [S3]" (`p02`) | 200. **Questions for Management renders as one raw list literal** `["…", "…"]`. Raw token "(verification status: no_claims)". 5 Unilever mentions, all asking to separate B&J figures from Unilever or about Unilever's control (`p04`, `p05`) |
| Company overview | 500 `MultipleObjectsReturned` | 500, "returned 4!" |
| Owner profile canary | rendered and in HTML. Staff see the private field, as the HTTP matrix recorded | rendered and in HTML, same as the HTTP matrix |
| Reconciliation panel | absent from the DOM on the Truth Delta page and the memo | absent (0 claims) |
| Canary on Truth Delta page and memo | none | none |
| Ops dashboard | `/ops/` 200 once MFA was complete | — |

How these relate to existing findings (for the owner to grade, nothing re-graded here):

- The ManyChat staff page shows the same "2 analyzed / 3 rows" as owner, Lite and paid (RA-104 / BW-002).
- Raw lists reach the staff memo on both decks: ManyChat RA-107 / BW-004, and B&J RA-002, which the
  baseline could not walk.
- The $23.1M "to date" sentence (RA-106) was not observed in the baseline. It **is** observed on the
  staff full memo.
- The overview 500s (RA-010 / RA-112 / BW-005) reproduce for staff.
- B&J's empty credibility value ("—") differs from ManyChat's "N/A". It is recorded only.

## After-walk controls

- **Documents 3132 and 3133:** row counts, max ids and timestamps match the pre-walk snapshot
  ([logs/after_walk_postcheck.txt](logs/after_walk_postcheck.txt)).
- **Redis:** only the stale `high_priority` (18).
- **Sessions:** none live for users 313 and 317.
- **Fixed-server POSTs:** login 3, logout 3, staff-mfa verify 3, profile duration beacon 1. No
  verify, identity-check, valuation, analyze or ingest request.

## Still open

- Owner grading of the rerun ledgers, the baseline BW rows and this post-fix record.
- Not tested on Render. The same browser rule applies there over HTTPS: under `same-origin`, Chrome
  sends the real Origin on same-origin POSTs, and Django checks it against the request host.
- **Untested follow-up:** `matchmaking/admin.py` also sends `no-referrer` on the API-key-issued
  admin page. Its content has no form, but it extends `admin/base_site.html`, and the admin header's
  "Log out" is a POST form. That button probably gets the same Origin-null 403 on that one page. It
  is not a lockout: any other admin page can sign out. It was left out of this fix's scope.
