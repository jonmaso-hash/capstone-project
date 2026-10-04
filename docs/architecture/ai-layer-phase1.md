# The AI layer, Phase 1: architecture

**Status: frozen** at `main` @ `ea81470` (PRs #135–#147). The Nike FY2026 rerun was its acceptance test; results are in [`docs/baselines/nike-fy2026/RERUN_LEDGER.md`](../baselines/nike-fy2026/RERUN_LEDGER.md). A change to any boundary below starts a new phase with its own audit and baseline. It is not a patch to this one.

## The rule

**The AI layer is not an authority.**
- Every decision about who may see what, and what a source may establish, already belongs to an existing rule. The AI layer consumes those rules; it never re-decides them, and nothing it retrieves can bypass them.
- A model writes prose *about* evidence. It never sets the state *of* evidence.

```
request / task / command
  → Principal                       who is asking (no user, no principal)
  → authorize(principal)            what they may use, decided before retrieval
  → retrieval / GroundedContext     only what was authorized, with provenance and state
  → model                           writes from that, and nothing else
```

## Components

| Concern | Module | Contract | Held by |
|---|---|---|---|
| Who is asking | `zelda_api/principal.py` | `Principal` wraps an active, saved user. There is no anonymous, system or internal principal. Scheduled work runs *as* the user it is for. A missing user refuses (`PrincipalRequired`); it is never read as "unrestricted" | `tests_principal` |
| What they may use | `zelda_api/authorization.py` | `authorize(principal)` is a resolver over existing rules: `document_visible`, `text_documents`, `finding_tier`, `ic_memo_visible`, `entity_report_visible`, `field_visible`. Each answer equals the rule it wraps | parity tests in `tests_authorization`, `tests_dashboard_authorization` |
| Retrieval | `zelda_api/retrieval.py` | Candidate chunks are restricted by `authorize(principal)` *before* anything is loaded, scored or matched. There is no unscoped retrieval. A document outside scope refuses; it does not return empty | `tests_retrieval` |
| The text boundary | `zelda_api/chunk_boundary.py` | An AST scan of first-party code finds every way to reach chunk text. Any read outside an allowlist fails CI. Entries are keyed by file and function, each has a written reason, and a stale entry also fails | `tests_chunk_boundary` |
| What a source may establish | `zelda_api/source_capabilities.py` | Each (source, category) has a role: `can_establish` (may decide a state), `can_corroborate` (stored and attached, never decides), `informational_only` (shown as context, never compared), `unavailable`. `ObservedDatapoint` stores `role`, `evidence_origin` and `provenance` | `tests_source_capabilities` |
| What Zelda knows when it writes | `zelda_api/grounded_context.py` | The memo generator receives a `GroundedContext` and nothing else: no raw text, chunks or profile rows. Every item carries its source (document, page, chunk) and a state: SELF_REPORTED / VERIFIED / CONTRADICTED / INSUFFICIENT, with a reason | `tests_grounded_context` |

## The evidence path

```
upload → extract (slide/page markers) → chunks (page_number = slide)
       → insights → claims (page, bounded excerpt)
       → Truth Delta: observations by role → category state + reason
       → verification_finished → memo from GroundedContext
```

- **Extraction.** `utils.extract_text_from_file` returns `(text, pages)` with `[[zelda:slide N]]` / `[[zelda:page N]]` markers. A failure raises `ExtractionError` (`dependency_missing` / `unreadable_file` / `unsupported_format`) and is never stored as document text. Previews strip the markers. A page that cannot be known is `null`, never guessed.
- **States.** `TruthDeltaReport.category_states()` returns `verified` / `contradicted` / `no_data`, and `grounding_reasons()` qualifies `no_data` (`period_unknown`, `no_external_evidence`, …). Only an establishing row can move a claim to `verified` or `contradicted`.
- **Corroboration never decides.** A deck claim plus agreeing corroborating evidence stays INSUFFICIENT (`corroboration_only`).
- **Presentation reads the state.** Icons, counts, the rollup, `per_claim_rows`, `ic_memo.coverage_sentence` and the "What Zelda noticed" lines all read `category_states()`/`grounding_reasons()`. They never read the model's verdict.
- **Ordering.** The memo is generated on `truth_delta_tasks.verification_finished`, after verification. That includes the failure path, where the memo states the verification failed.
- **Idempotence.** Re-verifying replaces that source's observations for the document. A source that did not answer keeps its earlier rows, and other providers' rows are untouched. Reports are appended as history, and readers take the latest.

## Providers

| Provider | Role | Boundary |
|---|---|---|
| SEC EDGAR | `can_establish` revenue (`sec_filing`) | Registrant attribution is stated, and is not identity |
| DataForB2B | `linkedin_derived`: `funding_raised` may corroborate; `employees` is informational only (LinkedIn profiles are not headcount); revenue and customers unavailable | `dataforb2b_adapter.observe` targets the role boundary directly. Domain search is candidate generation only; an ambiguous domain spends no credits. Typed outcomes go to `details.provider_outcomes` |
| Filed | Entity Integrity business registration | State-scoped only (`filed._search` raises without a state; `NO_JURISDICTION` sends nothing). The registrar is judged from the detail record's `meta.source`, never from the query |
| NewsAPI | context | Headlines reach the judgment prompt; never an observation |
| CompanyEnrich | Entity Integrity commercial footprint | Corroborates a public footprint; never establishes legal identity |

## Known gaps carried out of Phase 1

These were measured by the rerun and are deliberately **not** part of this freeze.

1. **The Truth Delta judgment narrative** (`TruthDeltaEngine._call_claude_for_verification`) is model prose written beside the canonical state, not from it. On Nike it calls an INSUFFICIENT/`period_unknown` revenue claim "materially overstated… a red flag". It is shown on the Truth Delta page and inside the IC memo page. This is the next presentation item (L-005 residual, R-003). It needs the narrative to be generated from, or checked against, `category_states()`, as the memo already is through GroundedContext.
2. **Claim periods** (L-007). Claims carry no period, so comparable figures stay `period_unknown`.
3. **Retrieval quality** (L-002, L-013). Vectors are stored as strings, cosine is always 0, and retrieval is effectively keyword-only. `no_relevant_evidence` exists but rarely fires.
4. **Claim coverage** (L-010, L-024). Insights and claims are regex-derived (2 of about 25 checkable claims on Nike), and excerpts are capture fragments.
5. **Deck-vs-record and internal consistency** (L-011, L-012).
6. **Claim → chunk link** (L-014 remainder). `ClaimedDatapoint.source_chunk` is a label string with no chunk id.

## Operating notes for local runs

Run `manage.py preflight --local` before starting a local worker or server for any controlled run. It prints the broker, result backend and cache the processes will actually use, and exits non-zero on anything remote or on pending migrations. The test runner pins Celery to an in-process broker and refuses to run otherwise (`config/test_runner.isolate_celery`).

From the rerun's errata:
- **Broker.** `.env` points Celery and the cache at a shared cloud Redis. Local workers must override the broker, the result backend and `CACHE_URL` to `localhost` and print the effective values (E-2).
- **Schema.** The local database must have no unapplied migrations; the gate's fresh test database cannot see this (E-3).
- **Allowance.** A free founder's allowance is 3 credits per 30 days, and one upload spends 2 of them (E-4, R-004).
