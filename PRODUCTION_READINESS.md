# Mazha Mav Operations — V1 Production Readiness

Date: 12 August 2026

## Release scope

V1 includes authentication and owner/manager/staff authorization; user, product and retailer management; immutable warehouse/staff inventory; stock requests and fulfilment; server-authoritative multi-item sales; staff and owner sales history; owner analytics and CSV reports; and a centrally managed company payment QR with audited manual payment receipt.

The QR is informational. Opening it never marks a sale paid and does not confirm a bank transaction.

## Database migrations

1. `0001_phase1_schema.py` — users, products, retailers, immutable movement ledger and stock requests.
2. `0002_movement_idempotency.py` — movement idempotency.
3. `0003_sales.py` — sales, items and payment enums.
4. `0004_stock_request_workflow.py` — fulfilment audit and open-request uniqueness.
5. `0005_reporting_indexes.py` — dashboard/reporting indexes.
6. `0006_payment_settings.py` — singleton payment configuration and sale payment-receipt audit.

## Security review

- Passwords use Argon2 through `pwdlib`; new accounts require upper/lowercase, number and symbol.
- JWT cookies are HttpOnly, expiring, issuer/audience checked, SameSite=Lax and Secure in production.
- Production startup rejects weak JWT secrets, non-HTTPS frontend origins, insecure cookies and local media storage.
- Backend roles remain authoritative. Staff cannot mutate the company QR or access owner APIs.
- Login failures are rate-limited by IP. The built-in limiter is per application process; deploy behind an edge/WAF or shared Redis limiter when horizontally scaling.
- CORS allows one configured frontend origin, credentials, explicit methods and explicit headers.
- ORM-bound parameters prevent direct SQL interpolation. Request schemas validate lengths, UUIDs, enums, quantities, dates and payment methods.
- QR uploads require owner authorization, an allowed MIME type, valid decoded PNG/JPEG/WebP content, safe dimensions and a 5 MB default maximum. Images are decoded and normalized to metadata-free PNG.
- Production media uses a private S3-compatible bucket. Objects are server-side encrypted and streamed through authenticated API routes rather than exposed as public bucket URLs.
- API responses set nosniff, frame denial, restrictive referrer/permissions/CSP headers, plus HSTS in production.
- The backend container runs as a non-root user and exposes a health check.

## Data-integrity review

- Stock balances are derived from immutable movements; PostgreSQL rejects movement updates/deletes.
- Product-row locks and database transactions prevent negative warehouse/staff stock during issues, fulfilments and sales.
- Sales calculate prices and totals only from database product prices and commit sale, items and movements together.
- Unique idempotency keys protect sales and stock posting; stock-request fulfilment is request-idempotent.
- Every stock movement, request review/fulfilment and received-payment transition records its authenticated actor and timestamp.
- QR display does not modify sales. Only the owning staff account can manually transition its pending sale to paid, with an explicit payment method.

## Performance review

- Sales, retailer and stock-request history APIs use bounded `limit`/`offset` pagination.
- Sales list relationships use select-in loading rather than per-row lookups.
- Dashboard sections use grouped database aggregates and bounded result sets; stock totals are aggregated by ledger dimensions.
- Reporting indexes cover sale dates/staff/payment status, movement dates/products/staff/types, request status/time and retailer geography.
- CSV exports intentionally return full matching reports and may become large. Add streamed server-side export jobs before datasets regularly exceed hundreds of thousands of rows.

## Required production environment

Backend:

- `ENVIRONMENT=production`
- `DATABASE_URL` — Render PostgreSQL connection string using `postgresql+psycopg://`
- `JWT_SECRET` — randomly generated secret, at least 32 characters
- `ACCESS_TOKEN_MINUTES` — approved session duration
- `BUSINESS_TIMEZONE=Asia/Kolkata` — authoritative operating date for sales, dashboards and report filters
- `FRONTEND_ORIGIN=https://<vercel-domain>`
- `SECURE_COOKIES=true`
- `MEDIA_STORAGE_BACKEND=s3`
- `S3_BUCKET`, `S3_REGION` and optional `S3_ENDPOINT_URL`
- `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` or workload credentials
- `LOGIN_RATE_LIMIT_ATTEMPTS`, `LOGIN_RATE_LIMIT_WINDOW_SECONDS`

Frontend:

- `BACKEND_URL=https://<render-api-domain>`
- `NEXT_PUBLIC_API_URL=/api/v1`

Never commit `.env`, Vercel secrets, Render secrets, database URLs or S3 credentials.

## Deployment procedure

1. Create private PostgreSQL and private S3-compatible object storage with versioning enabled.
2. Configure Render backend secrets and Vercel frontend variables.
3. Take/verify a database backup before the release.
4. Run `cd backend && alembic upgrade head` as a one-off/pre-deploy command.
5. Deploy the backend Docker image and verify `/health`, authentication and migration revision.
6. Deploy `frontend/` to Vercel. Next.js rewrites `/api/*` to `BACKEND_URL`, keeping the session cookie first-party.
7. Log in as owner, configure the payment QR, then validate owner, manager and staff smoke paths.
8. Verify CORS, Secure/HttpOnly cookie attributes, upload/download, CSV export and a reversible test sale in production.

Do not run development seeding in production; `app.seed` refuses when `ENVIRONMENT` is not `development`.

## Backups and recovery

- Enable managed PostgreSQL daily backups and point-in-time recovery where the selected plan supports it.
- Take an encrypted `pg_dump --format=custom` before every schema migration and retain copies outside the primary Render account according to company retention policy.
- Restore only into an isolated database first: create the target, run `pg_restore --clean --if-exists --no-owner --dbname=<restore_target> <backup.dump>`, verify the Alembic revision, then reconcile inventory and sales before cutover.
- Enable bucket versioning/lifecycle rules for QR media. Keep the bucket private.
- Quarterly, restore both PostgreSQL and QR media into an isolated environment and test authentication, stock reconciliation and sale lookup.
- Record backup time, migration revision, application image identifier and restoration result in the release log.
- Keep versioned Render/Vercel/S3 environment-variable manifests in the approved password/secret manager. Recovery must restore the manifest matching the selected application release; never copy secrets into source control or release notes.

## Rollback procedure

1. Stop writes or place the API in maintenance mode.
2. Roll the frontend and backend back to the previous immutable deployment.
3. Prefer forward-fix migrations. Use `alembic downgrade <revision>` only after reviewing whether newer application writes rely on the new schema.
4. For destructive/incompatible migration failure, restore the pre-deploy PostgreSQL backup and matching media version.
5. Run reconciliation checks for movement counts, negative stock, sales totals and payment statuses before reopening writes.

Never edit or delete posted stock movements as part of rollback.

## Test evidence

- Backend: 52 tests passing, including auth, owner-only staff management, direct password reset/deactivation, authorization, constraints, ledger operations, stock requests, sales transactions, deterministic full-system reconciliation, business-timezone boundaries, dashboard/staff metrics, CSV reports, QR upload/access, manual payment receipt and login rate limiting.
- Python bytecode compilation and installed-package consistency (`pip check`): passing.
- Frontend ESLint and standalone TypeScript checks: passing.
- Frontend regression tests: 4 passing, including staff directory filtering and payment QR failure handling.
- Next.js production build with TypeScript validation: passing on Next.js 16.3.0.
- Production npm dependency audit: 0 known vulnerabilities.

## Known limitations

- QR payments are static and manually acknowledged; no bank/payment-provider verification exists.
- Rate limiting is process-local; multi-instance deployment needs a shared limiter or managed edge policy.
- The schema is single-company and has no tenant key. Tenant predicates are mandatory before multi-company use.
- Password reset, MFA, centralized audit-event search, alerting and notification delivery are not implemented.
- CSV exports are synchronous, and there is no XLSX export or background report job.
- Low-stock threshold remains a fixed five units.
- Automated browser E2E, PostgreSQL concurrency/load tests, observability dashboards and automated restore drills remain operational follow-ups.

## Post-V1 ideas

Amount-specific UPI QR generation, provider adapters, payment webhooks with signed verification, reconciliation, MFA, password recovery, notifications, configurable thresholds, tenant isolation, async exports, XLSX, audit tooling, tracing/metrics, automated PostgreSQL concurrency tests and restore automation. These are not part of this release.
