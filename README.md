# Mazha Mav Operations — V1

Production-oriented foundation for Mazha Mav's operations platform. The Next.js frontend is deployable to Vercel; the FastAPI service and PostgreSQL database are deployable to Render.

## Local setup

1. Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env.local`.
2. Start PostgreSQL with `docker compose up -d db`.
3. In `backend/`, create a virtualenv, install `requirements.txt`, run `alembic upgrade head`, then `python -m app.seed` and `uvicorn app.main:app --reload`.
4. In `frontend/`, run `npm install` and `npm run dev`.

The development owner credentials come from `SEED_OWNER_PHONE` and `SEED_OWNER_PASSWORD`. Change them before seeding any shared development environment. Seeding refuses to run unless `ENVIRONMENT=development`.

`BUSINESS_TIMEZONE` defaults to `Asia/Kolkata` and must match the company operating timezone. Sale dates, Today/MTD metrics, and timestamp-based CSV date filters use this setting consistently even when the server runs in UTC.

## Schema

- `users`: identity, unique phone/email, Argon2 password hash, owner/manager/staff role, active status, timestamps.
- `products`: unique SKU, unit, non-negative decimal selling price, active status, timestamps.
- `retailers`: shop and optional contact/location fields, active status, timestamps.
- `stock_movements`: append-only inventory ledger with product, optional staff, movement type, signed non-zero quantity, references, author and posting time. PostgreSQL rejects UPDATE and DELETE; corrections are compensating entries.
- `stock_requests`: staff/product request with positive quantity, workflow status, review audit fields and notes.
- Phase 4 stock-request audit fields include explicit fulfilled quantity, fulfiller, fulfilment time, and separate review notes. A partial unique index allows only one pending/approved request per staff/product.
- `sales`: server-authored sale number, staff, retailer, date, authoritative monetary totals, payment state, notes, and a unique idempotency key.
- `sale_items`: product quantities with immutable unit-price snapshots and server-calculated line totals.

All identifiers are UUIDs. Foreign keys use `RESTRICT` to retain audit history.

## API routes

- `GET /health`
- `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`
- Owner only: `GET|POST /api/v1/admin/users`, `GET|POST /api/v1/admin/products`
- Owner/manager: `GET /api/v1/operations/status`
- Owner/manager inventory reads: `GET /api/v1/inventory/options`, `GET /api/v1/inventory/warehouse`, `GET /api/v1/inventory/staff-overview`
- Owner/manager ledger posting: `POST /api/v1/inventory/warehouse-in`, `POST /api/v1/inventory/issues`, `POST /api/v1/inventory/returns`, `POST /api/v1/inventory/adjustments`
- Staff only: `GET /api/v1/inventory/my-stock`
- Authenticated retailer search/create: `GET|POST /api/v1/retailers`
- Owner/manager retailer maintenance: `PATCH|DELETE /api/v1/retailers/{id}` (DELETE deactivates)
- Staff sale flow: `GET /api/v1/sales/options`, `POST /api/v1/sales`, `GET /api/v1/sales/staff-home`
- Role-scoped history: `GET /api/v1/sales` with `date_from`, `date_to`, `staff_id`, `retailer_id`, `product_id`, and `payment_status` filters
- Staff replenishment: `POST /api/v1/stock-requests`, `GET /api/v1/stock-requests/mine`
- Owner/manager replenishment: `GET /api/v1/stock-requests`, `POST /api/v1/stock-requests/{id}/approve`, `/reject`, and `/fulfil`
- Owner analytics: `GET /api/v1/dashboard/owner` with `today`, `last_7_days`, `last_30_days`, `this_month`, or bounded custom ranges.
- Owner CSV reports: `GET /api/v1/reports/{report}.csv` for sales, staff sales, product sales, retailer sales, inventory movements, stock requests, and pending payments.
- Payment settings: owner-only `GET|POST /api/v1/payments/settings`; authenticated `GET /api/v1/payments/qr-context` and `/qr-image`; staff-only `POST /api/v1/payments/sales/{sale_id}/received` for an audited manual receipt.

Authentication uses a signed, expiring JWT stored in an HttpOnly cookie. The frontend proxies `/api` through Next.js so the cookie remains first-party on Vercel. Backend role dependencies are authoritative; route hiding is only a UX layer.

## Movement formulas

Quantities are positive for warehouse receipts, issues, returns and sales. Adjustment quantities are signed and require a reason.

- Warehouse balance = `warehouse_in - issued_to_staff + staff_return + warehouse_adjustments`
- Staff balance = `issued_to_staff - staff_sale - staff_return + staff_adjustments`

Every posting records `created_by` and `created_at`. The service rejects any operation that would make warehouse or staff stock negative. Product-row locking serializes warehouse postings per product in PostgreSQL. Each write requires an idempotency key backed by a unique database constraint; an identical retry returns the original movement.

## UI screens

- `/admin/inventory/issue`: immutable warehouse-to-staff stock issue form.
- `/admin/inventory`: warehouse balances, staff/product balance overview and controlled signed adjustments.
- `/staff/my-stock`: read-only per-product received, sold, returned and emphasized current stock.
- `/staff/record-sale`: retailer selection or inline creation, multi-product sale, live indicative totals and payment capture.
- `/staff/history`: own filtered sales history.
- `/staff`: daily quantity/value, total stock, pending payment summary, recent sales, and quick actions.
- `/admin/sales`: all-sales history and filters.
- `/admin/retailers`: retailer creation, editing, searching and deactivation.
- `/staff/request-stock`: new requests with open-request warnings and complete status history.
- `/admin/stock-requests`: request queue, balances, low-stock/age indicators, approval, rejection, and explicit-quantity fulfilment.
- `/admin`: owner-only operational dashboard with source-backed KPIs, daily sales trend, product/staff performance, stock risks, retailer insights, payments, and CSV exports. Managers continue to `/admin/inventory`.
- `/admin/settings/payments`: owner-only central payment name, UPI/account reference, QR upload and activation settings.
- `/staff/payment-qr`: responsive payment display, optionally scoped to a sale, with an explicit audited “mark received” action and no automatic payment claim.

## Tests

Run `.venv/bin/pytest` from `backend/`. The 45-test suite covers authentication, authorization, ledger integrity, transactional sales and requests, dashboard/report reconciliation, QR access/upload validation, manual receipt auditing, login rate limiting, a deterministic V1 working day, and the India/UTC date boundary. From `frontend/`, run `npm test`, `npm run lint`, `npm run typecheck`, and `npm run build`.

## Phase 2 migration

Migration `0002_movement_idempotency.py` adds a nullable unique `idempotency_key` to `stock_movements`. It is nullable so historical Phase 1 rows remain valid; every new Phase 2 posting endpoint requires a key.

## Phase 3 migration

Migration `0003_sales.py` creates `sales`, `sale_items`, the payment enums, indexes, monetary/quantity constraints, and unique sale idempotency keys. Sale confirmation locks product rows in deterministic order, validates every staff balance, prices every item from `products.selling_price`, and commits the sale, items, and ledger movements in one transaction.

## Phase 4 migration

Migration `0004_stock_request_workflow.py` adds `fulfilled_quantity`, `fulfilled_by`, `fulfilled_at`, `review_notes`, a positive fulfilled-quantity constraint, and the partial unique open-request index. Fulfilment locks the request and product rows and commits its immutable `issued_to_staff` movement and request audit transition together.

## Phase 5 metric definitions

- Sales values use committed `sales.total`; quantities and product revenue use `sale_items.quantity` and `sale_items.line_total`.
- Today compares with yesterday. Month-to-date compares with the same numbered day span in the previous month.
- Staff and warehouse stock are derived from the immutable movement ledger using the documented Phase 2 formulas.
- Retailers served is distinct retailers with a committed sale in the selected range.
- Inactive-in-period means an active retailer with no committed sale in the selected range.
- Pending payment value is the sum of committed sales whose payment status remains pending.

The current schema is single-company and therefore has no tenant key. Dashboard and report APIs are owner-only and accept no caller-selected staff/company scope. When multi-company support is introduced, `tenant_id` must be added to source tables and every aggregate/report predicate before enabling cross-tenant deployment.

## Phase 5 migration

Migration `0005_reporting_indexes.py` adds bounded reporting indexes for sale date/payment/staff, movement date/product/staff/type, request status/time, and retailer geography.

## Phase 6 migration

Migration `0006_payment_settings.py` adds the centrally controlled payment-settings singleton and payment-receipt actor/timestamp fields on sales. Production QR objects are private in the configured S3-compatible store and are served only through authenticated API routes.

## Remaining work

Future work includes dynamic amount-specific QR generation, provider verification/reconciliation, owner UI for account/product management, notification delivery, configurable low-stock thresholds, explicit tenant keys before multi-company support, centralized rate limiting/password recovery, audit observability, PostgreSQL query-plan/concurrency integration tests, and deployment CI. Automated forecasting remains intentionally out of scope.
