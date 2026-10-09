# Profile Architecture 2.0 — Design specification

Status: Design proposal (no production model or template changes)
Branch: `design/profile-architecture-v2`

## Existing system to preserve

- `matchmaking.Application` is the active founder marketplace record with discovery, privacy, vectors, revenue period, pitch uploads, and visibility controls.
- `matchmaking.InvestorApplication`, `SellerApplication`, and `BuyerApplication` are role-specific records used by current forms.
- `accounts.FounderApplication` and `accounts.InvestorApplication` also exist; do not assume they are interchangeable with the matchmaking models.
- `accounts/forms.py` defines current onboarding/edit fields. Existing revenue period validation and vector-edit locking must remain.
- Existing milestones, dashboards, CRM, data rooms, matchmaking, billing, reports, and permission gates must not be rerouted or reset.

## Product principles

1. Account creation stays short; optional enrichment happens later.
2. Separate people, organizations, and their relationships. Do not overwrite role-specific applications.
3. One person may hold multiple roles, with a primary role for navigation.
4. Every field has a clear owner, visibility classification, and optional source.
5. No new financial disclosure is public by default; preserve current field-level visibility authority.
6. Unverified self-reported information must not be presented as verified.
7. Drafts never change live profiles until explicitly published.
8. No paid intelligence generation, external enrichment, or report refresh occurs without explicit confirmation.

## Proposed additive data model (subject to implementation audit)

- `PersonProfile`: user OneToOne, display_name, headline, biography, photo, primary_location, website, linkedin_url, other_social_links, optional preferred_name; do not require gender.
- `Organization`: canonical company record with name, domain, location, description, sector, website, normalized aliases; initially link existing application records rather than migrating their financial fields.
- `OrganizationRelationship`: person, organization, relationship_type (founder/owner/employee/advisor/investor), title, start/end dates, claim_status, visibility, source. Unique constraints should allow historical and concurrent relationships while preventing exact duplicates.
- `EducationRecord`: person, institution, credential, field_of_study, start/end years, visibility.
- `ProfileRole`: user, role (founder/investor/seller/buyer), enabled, primary; one primary role, multiple enabled roles. Preserve existing role authorization rules.
- `ProfileDraft`: user, target, JSON payload, base revision, updated_at; validate through existing forms/services on publish; detect conflicts rather than silently overwriting.
- `ProfileFieldEvidence` (later): subject, field key, source, observed_at, status (self-reported/grounded/verified/contradicted/insufficient), access scope. Never expose private sources via public API.

## Editor layout

Desktop: left navigation (Overview, Career & Education, Organizations, Marketplace Roles, Verification, Visibility); central editable form; right-side Zelda profile progress and suggested next task.
Mobile: stacked navigation and form, sticky Save draft / Review changes actions.

Overview: image, name, headline, biography, location, links.
Career: jobs, education, credentials, founded organizations.
Organizations: linked company, relationship and authority claim; no automatic ownership verification.
Roles: role-specific panels reusing current founder/investor/seller/buyer fields.
Verification: source status and provenance; no invented trust score.
Visibility: field-level audience preview with owner/member/connection/public semantics backed by existing permission checks.

## Delivery plan

### PR A — foundation
- Audit active URL/view/template routes, both accounts and matchmaking models, signals and authorization.
- Add additive PersonProfile, OrganizationRelationship and education models with safe migrations.
- Backfill only unambiguous data; no external calls and no guessed associations.
- Tests for migrations, role coexistence, ownership, private-field leakage, and legacy route behavior.

### PR B — editor
- Add sectioned profile editor, draft/review/publish workflow, responsive layout and accessibility labels.
- Preserve old endpoints until compatibility tests pass.
- Keep signup simple and optional profile sections skippable.

### PR C — role and Zelda integration
- Reuse existing forms and field visibility, retain revenue period/as-of constraints and vector edit locks.
- Enrich Zelda suggestions from authorized, explicitly published fields only.
- No paid report or verification triggers without consent.

## Acceptance criteria

- Existing users retain all current applications, purchases, uploaded decks, matches, milestones, and privacy settings.
- A person can link to several organizations without copying financial data.
- Founder/investor/seller/buyer forms continue to validate and save.
- Private, archived, internal, and unauthorized profiles remain excluded from discovery.
- Editing a draft does not change matchmaking vectors or published content.
- All migrations are reversible where practical; run test suite and migration checks before merging.
