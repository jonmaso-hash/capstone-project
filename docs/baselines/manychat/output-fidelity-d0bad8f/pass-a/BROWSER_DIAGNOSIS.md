# Browser blocker (D-9 / OF-1015): diagnosis

**Additive.** This file changes nothing in [RERUN_LEDGER.md](RERUN_LEDGER.md), [15_browser_walks.json](15_browser_walks.json), [OWNER_GRADING.md](OWNER_GRADING.md), memo 102 or any captured artifact. No model call, no run server and no fixture was involved. The memo-102 walks remain **blocked**, and nothing here counts as a browser check of memo 102.

## Finding

**The connected Chrome ("Browser 1") is not running on the computer that runs the isolated run server.** Its own 127.0.0.1 is another machine's loopback, so `http://127.0.0.1:8000` and `http://localhost:8000` were refused, and no browser request reached the run server's log.

## Observation (2026-10-22 03:51 local)

1. **The machine:** this computer's Wi-Fi IPv4 address is `192.168.0.64` (`ipconfig`).
2. **The probe server:** a static page with the marker `KCV-LOOPBACK-PROBE-OK` ([browser_diagnosis/probe_page.html.txt](browser_diagnosis/probe_page.html.txt)), served with `python -m http.server 8765 --bind 0.0.0.0` from an empty scratch directory. Locally, `curl` returned 200 for `http://127.0.0.1:8765/`, `http://localhost:8765/` and `http://192.168.0.64:8765/`.
3. **The connected browser:** `list_connected_browsers` showed one browser, "Browser 1" (Windows; `isLocal: true`, which is only a hint from matching OS; `inUse: true`).
4. **Positive control:** `https://example.com/` loaded ("Example Domain"; Windows, Chrome 155, time zone America/Los_Angeles).
5. **Loopback:** `http://127.0.0.1:8765/` gave "127.0.0.1 refused to connect" (`chrome-error://chromewebdata/`). The probe server logged no request from the browser.
6. **LAN:** `http://192.168.0.64:8765/` loaded the page ("kcv-loopback-probe", text `KCV-LOOPBACK-PROBE-OK`).
7. **The request's origin:** the probe server logged that request, and its favicon request, from client **`192.168.0.111`** ([browser_diagnosis/probe_server_log.txt](browser_diagnosis/probe_server_log.txt)).
   - The three earlier `127.0.0.1` / `192.168.0.64` lines in that log are my own `curl` checks from this computer.

The browser reached this computer only through the LAN, from another address, so it runs on another device (192.168.0.111). The probe server was then stopped (port 8765 closed) and the probe tab closed.

## What the next live run needs (owner action)

Pick one before any model call:

- **Recommended:** connect Claude in Chrome on **this** computer (192.168.0.64), the one that runs the isolated server, and select it with `/chrome`. The protocol's server stays on `127.0.0.1:8000`, unchanged.
- **Alternative (a protocol deviation that needs the owner's approval):** bind the run server to `192.168.0.64` and add it to `ALLOWED_HOSTS` and the CSRF trusted origins, then walk from 192.168.0.111. This exposes the dev server, with disposable test credentials, to the LAN for the duration of the walks.

Before the next run's single model call, the run should confirm that the selected browser can load a loopback probe (`http://127.0.0.1:<port>/`) and that the server logs that request from `127.0.0.1`.
