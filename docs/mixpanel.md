# Product analytics

Configure `MIXPANEL_TOKEN` and `MIXPANEL_ID_NAMESPACE=production` on both the
web service and Celery worker. Leave the token empty in tests and development,
or use a separate development project. Never commit the project token.
`MIXPANEL_TRACK_URL` defaults to the US ingestion endpoint; EU/India projects
must use their corresponding regional endpoint.

| Event | Trigger | Properties |
| --- | --- | --- |
| `signup_completed` | Password signup or allauth signup succeeds | role (password signup), method |
| `zelda_reports_ready` | Paid report set reaches ready, or standalone memo/valuation completes | product, reports |
| `purchase_completed` | Validated paid Zelda order, credit pack, valuation unlock, or positive paid subscription invoice | product, amount_minor, currency, payment_kind |

Amounts are integer minor currency units (9900 = USD 99.00). Subscription
payments are measured from invoices, not checkout redirects or subscription
activation. Zero-charge credit redemptions are not purchases. A paid bundle
produces one ready event with its report types, not one event per report.
Standalone Entity Integrity and Profile Analysis are not covered by these
initial hooks. No historical events are backfilled.

Delivery runs after database commit through Celery, with up to three retries.
Broker publish failures are logged and dropped; this is best-effort analytics,
not an accounting ledger. Occurrence timestamps and hashed insert IDs stay
stable on retries. Internal user IDs use an environment prefix. Browser session
IDs are not currently linked to this server identity.

No emails, names, deck contents, filenames, messages, URLs, or card data are
sent. IP enrichment is disabled. Staff impersonation does not emit events.
Verify new events in Mixpanel using a real test account after deployment;
avoid synthetic signup/purchase events in the production project.
