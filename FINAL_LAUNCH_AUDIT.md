# Mazha Mav Operations — Final Pre-Launch Audit

Audit date: 12 August 2026  
Scope: V1 only; no V2 features were evaluated as release requirements.

## 1. Executive verdict

**READY FOR PILOT**

The critical inventory, sales, payment, authorization, migration, reporting and reconciliation checks pass after fixing two verified pre-launch defects. There are no open P0 or P1 findings.

Mazha Mav can safely begin using the system with real staff and real stock in a controlled pilot, provided the production environment checklist, opening-stock dual check, backups and first-week daily reconciliation in this report are followed. A broad unattended rollout should wait until the pilot has completed and the P2 operational limitations have been accepted.

## 2. Tests executed and exact results

| Gate | Result |
|---|---:|
| Backend full suite | 45 passed, 0 failed; 75 dependency deprecation warnings; 9.17 s |
| Deterministic launch-audit tests | 3 passed, 0 failed |
| Python compileall | Passed |
| Python `pip check` | No broken requirements |
| Frontend regression tests | 2 passed, 0 failed |
| ESLint | Passed, 0 errors |
| TypeScript `tsc --noEmit` | Passed |
| Next.js 16.3.0 production build | Passed; 17 routes generated |
| Production npm audit | 0 vulnerabilities |
| Clean backend environment | Pinned requirements installed; 45 passed; compile passed; `pip check` passed |
| Clean frontend environment | `npm ci` installed 393 packages; 2 tests passed; lint/typecheck/build passed |
| Browser workflow audit | Owner desktop and staff 390×844 mobile routes exercised; no horizontal overflow on audited staff screens |

The 75 backend warnings originate in FastAPI 0.116.1 calling a Python 3.14 API deprecated for future Python 3.16 removal. The production image uses Python 3.12, so this is not a current runtime blocker.

## 3. End-to-end scenario results

Deterministic fixture:

- 1 owner, 1 manager, 3 active sales staff.
- 3 products priced at ₹12.50, ₹20.00 and ₹7.25.
- 8 retailers across Kozhikode, Malappuram and Wayanad; retailer creation during a sale is covered by the existing suite.
- Warehouse receipts: 300 Classic, 200 Premium, 400 Mini.
- Six initial staff issues, six sales/eight sale items, one stock-request fulfilment, one return and two valid adjustments.

Verified workflow results:

- Warehouse receipt created only warehouse ledger entries and did not change staff balances.
- Issues decreased warehouse and increased only the selected staff/product balance.
- Single-item, multi-item, cash, UPI, pending/credit and same-product/different-staff sales used database prices and committed sale/items/movements atomically.
- An insufficient-stock sale returned 409 and created no partial sale or deduction.
- Reusing a sale idempotency key returned the original sale without another deduction in the existing regression suite.
- QR display retained pending status. Manual receipt recorded the owning staff actor and timestamp; another staff member received 403.
- Duplicate open replenishment request returned 409. A request for 40 fulfilled at 35 retained both quantities. Retry produced no second movement.
- Return, positive warehouse adjustment and negative staff adjustment reconciled. A below-zero adjustment returned 409.
- PostgreSQL’s immutability trigger remained present; historical movements were not edited.

## 4. Inventory reconciliation

Formula: warehouse = `warehouse_in − issued_to_staff + staff_return + warehouse_adjustments`. Staff = `issued_to_staff − staff_sale − staff_return + staff_adjustments`.

### Warehouse

| Product | In | Issued | Returned | Adjustment | Expected | API/dashboard/CSV |
|---|---:|---:|---:|---:|---:|---:|
| Mav Classic | 300 | 175 | 0 | 0 | 125 | 125 |
| Mav Premium | 200 | 80 | 0 | +5 | 125 | 125 |
| Mav Mini | 400 | 170 | 10 | 0 | 240 | 240 |
| **Total** | **900** | **425** | **10** | **+5** | **490** | **490** |

### Staff/product

| Staff | Product | Issued | Sold | Returned | Adjustment | Expected/API |
|---|---|---:|---:|---:|---:|---:|
| Staff A | Classic | 115 | 15 | 0 | 0 | 100 |
| Staff A | Premium | 30 | 4 | 0 | 0 | 26 |
| Staff B | Classic | 60 | 7 | 0 | 0 | 53 |
| Staff B | Mini | 100 | 20 | 10 | 0 | 70 |
| Staff C | Premium | 50 | 6 | 0 | 0 | 44 |
| Staff C | Mini | 70 | 13 | 0 | −2 | 55 |
| **Total with staff** |  |  |  |  |  | **348** |

The inventory APIs, Staff My Stock, admin overview, dashboard stock KPIs and 21-row movement CSV matched these independently calculated values.

## 5. Sales and payment reconciliation

| Measure | Expected | Application |
|---|---:|---:|
| Sales value | ₹714.25 | ₹714.25 |
| Quantity sold | 65 | 65 |
| Paid value after manual receipt | ₹626.75 | ₹626.75 |
| Pending value | ₹87.50 | ₹87.50 |
| Cash | ₹306.25 | ₹306.25 |
| UPI | ₹320.50 | ₹320.50 |
| Credit/pending | ₹87.50 | ₹87.50 |
| Today | ₹714.25 | ₹714.25 |
| Month to date | ₹714.25 | ₹714.25 |

Staff totals: A ₹267.50 / 19 units; B ₹232.50 / 27 units; C ₹214.25 / 19 units. Product totals: Classic ₹275.00 / 22, Premium ₹200.00 / 10, Mini ₹239.25 / 33. Decimal snapshots and line totals reconciled exactly to two monetary decimal places.

## 6. Dashboard reconciliation

| KPI/section | Expected | Result |
|---|---:|---|
| Sales Today | ₹714.25 | Match |
| Quantity Sold Today | 65 | Match |
| Month-to-Date | ₹714.25 | Match |
| Yesterday / previous comparable | ₹0.00 / ₹0.00 | Match |
| Stock With Staff | 348 | Match |
| Warehouse Stock | 490 | Match |
| Pending Stock Requests | 0 after fulfilment | Match |
| Pending Payment Value | ₹87.50 | Match |
| Active Sales Staff | 3 | Match |
| Product contribution | 38.50%, 28.00%, 33.50% | Match; sums to 100.00% |
| Staff performance | ₹714.25 and 65 units in aggregate | Match |
| Retailer ranking | Ordered by committed sale total | Match |
| District breakdown | 3 districts represented | Match |
| Payment-method breakdown | ₹714.25 in aggregate | Match |

Every metric was traced to `sales`, `sale_items`, `stock_movements`, `stock_requests`, `retailers` or active staff records. No display-only metric was accepted as evidence.

## 7. CSV report verification

| Report | Expected rows | Result |
|---|---:|---|
| Sales | 6 | Match |
| Staff Sales | 3 | Match |
| Product Sales | 3 | Match |
| Retailer Sales | 6 retailers with sales | Match |
| Inventory Movement | 21 | Match |
| Stock Request | 1 | Match |
| Pending Payment | 1 | Match |

All exports decoded as UTF-8, honored the business-date filter, had no password hash/secret columns, contained no unexpected duplicates, and reconciled to API/dashboard totals. A note beginning `=SUM(...)` was exported with a leading apostrophe, confirming spreadsheet formula-injection protection.

## 8. Authorization matrix

| Capability | Staff | Manager | Owner |
|---|---|---|---|
| Own stock/sales/request/payment receipt | Allowed | Not staff workflow | Not staff workflow |
| Owner dashboard and company CSV reports | 403 | 403 | Allowed |
| Warehouse/staff inventory overview | 403 | Allowed | Allowed |
| Warehouse receipt, issue, return, adjustment | 403 | Allowed | Allowed |
| Approve/reject/fulfil requests | 403 | Allowed | Allowed |
| Retailer maintenance | Search/create; edit/deactivate 403 | Allowed | Allowed |
| Staff/product administration | 403 | 403 | Allowed |
| Payment settings/QR replacement | 403 | 403 | Allowed |
| Another staff member’s payment receipt | 403 | 403/not applicable | 403/not applicable |
| No session | 401 on protected API | 401 | 401 |

Manager permission is intentionally operational: inventory and request operations plus retailer maintenance and all-sales history, but no owner dashboard/reports, user/product administration or payment settings.

## 9. Security findings

Passed checks:

- Argon2 password hashing and strong-password validation.
- Expiring JWT with issuer/audience validation in HttpOnly, SameSite=Lax cookies; Secure is mandatory in production.
- Backend role dependencies enforced direct API access.
- One-origin credentialed CORS with explicit methods/headers.
- Bound SQLAlchemy statements; no caller-interpolated SQL found.
- Production startup guards reject weak JWT secrets, HTTP frontend origin, insecure cookies and local media storage.
- Private authenticated QR retrieval; S3 server-side encryption; decoded content/type/dimension/size validation and PNG normalization.
- Generic 500 responses do not disclose exceptions.
- CSP, HSTS in production, frame denial, nosniff, permissions and referrer headers.
- Secret scan found only documented development defaults; no production token, private key, database credential or object-store secret was present in application/frontend source.

## 10. Migration and database verification

- Linear history verified: `0001 → 0002 → 0003 → 0004 → 0005 → 0006 (head)`.
- Generated PostgreSQL SQL for the full chain was applied with `ON_ERROR_STOP` to a newly created PostgreSQL 16.14 database.
- Result: revision `0006`, 36 public indexes, 13 foreign keys, all 5 application enums, stock-movement update/delete trigger, check constraints and the partial unique open-request index.
- The `0006 → 0005` downgrade was applied successfully, then `0005 → 0006` was reapplied successfully.
- The local sandbox prevented the Python driver from opening a local socket, so Alembic online mode could not be exercised directly here; Alembic generated the dialect-specific transactional SQL and PostgreSQL itself executed it successfully. Render pre-deploy must still run the documented online `alembic upgrade head` command against staging before production cutover.
- No corrective database migration was required. Business-timezone correction is application/configuration-only and explicitly sets `sales.sale_date`.

## 11. Deployment configuration review

- Vercel serves Next.js and proxies `/api/*` to `BACKEND_URL`, keeping the HttpOnly session first-party.
- Render runs the non-root FastAPI image; `/health` and container healthcheck are present.
- `FRONTEND_ORIGIN` must be the exact HTTPS Vercel origin; `SECURE_COOKIES=true` is enforced for production.
- Render PostgreSQL URL must use `postgresql+psycopg://`; migrations run as a pre-deploy/one-off step before application rollout.
- Private S3-compatible storage, credentials/region/bucket and optional endpoint are required in production.
- `BUSINESS_TIMEZONE=Asia/Kolkata` is now required in the release manifest.
- QR retrieval is authenticated through the backend; the bucket is not public.
- Backup, isolated restore, application rollback, migration rollback cautions, environment-manifest recovery and media-version recovery are documented in `PRODUCTION_READINESS.md`.

## 12. Findings by severity

### P0 — fixed; none open

1. **Business-date mismatch at India midnight.** Sales relied on database/server calendar date while dashboard Today/MTD used another local calendar. Between 00:00 and 05:30 IST, current sales and timestamp-filtered movement/request reports could fall on different dates. Fixed with one configured `BUSINESS_TIMEZONE`, explicit sale dates and business-day-to-UTC report boundaries. Regression coverage added.

### P1 — fixed; none open

1. **Blank staff Payment QR page when settings were absent/inactive.** The normal staff quick action produced HTTP 500 because the backend’s expected 404 was not handled. Fixed with an explicit responsive unavailable state and two frontend regression tests.

### P2 — accepted pilot limitations

- Login rate limiting is process-local; enforce an edge/WAF rule or one backend instance during pilot.
- `/health` is a process health check and does not prove database/S3 connectivity; use Render metrics and a post-deploy authenticated smoke test.
- CSV generation is synchronous for the entire selected range; avoid unbounded historical exports during pilot.
- Empty all-zero sales trend labels a visual peak of ₹1.00 for SVG scaling. Underlying metric remains zero; cosmetic only.
- No automated browser suite, distributed PostgreSQL concurrency harness, centralized structured audit search, MFA/password reset, tracing or automated restore drill.

### V2 — not blockers

Dynamic amount-specific QR, provider verification, reconciliation, notifications, configurable low-stock thresholds, multi-company tenancy, XLSX/async exports, forecasting and other explicitly excluded V2 features.

## 13. Fixes made during audit

1. Added deterministic full-working-day and authorization regression coverage.
2. Added a central business-timezone helper and used it for sale dates, sale numbers, staff-home Today, dashboard periods and timestamp-based CSV boundaries.
3. Added `BUSINESS_TIMEZONE=Asia/Kolkata` to environment/setup documentation.
4. Added a safe staff Payment QR unavailable state and two frontend regression tests.
5. Expanded restore and environment-secret recovery documentation.

## 14. Known limitations

Static QR display is manually acknowledged and does not prove settlement. The system is single-company, has no MFA/password recovery, uses a fixed low-stock threshold, and relies on synchronous CSV exports. These are documented limitations, not failed V1 business rules.

## 15. Recommended pilot procedure

1. Provision production-like staging with Render PostgreSQL and private S3 storage; run online `alembic upgrade head` and verify revision `0006`.
2. Configure all secrets plus `BUSINESS_TIMEZONE=Asia/Kolkata`; verify Secure/HttpOnly cookie attributes, exact CORS origin and HTTPS proxy behavior.
3. Restore-test the pre-launch database backup and confirm bucket versioning before entering stock.
4. Owner and a second person dual-count opening warehouse stock. Post opening movements once and reconcile every product before issuing stock.
5. Pilot with one manager and one or two staff for 3–5 working days. Do not import historical transactions during the pilot.
6. At each day end compare physical warehouse/staff counts, ledger API balances, daily sales, pending payments and all seven CSV reports. Record sign-off.
7. Test one request with a different fulfilment quantity, one return, one compensating adjustment and one pending sale manually marked received.
8. Monitor 401/403/409/422/500 rates, Render database connections, disk/storage errors and login throttling. Stop writes and investigate any unexplained stock or sales variance.
9. Expand to all staff only after zero unexplained variances for the pilot period and a successful backup restore drill.

## Final answer

**Can Mazha Mav safely start using this system with real staff and real stock? Yes—for a controlled pilot under the procedure above.** The audited critical paths reconcile and no P0/P1 finding remains open. Do not treat this as approval for an unmonitored company-wide rollout before the pilot and staging migration smoke test are complete.
