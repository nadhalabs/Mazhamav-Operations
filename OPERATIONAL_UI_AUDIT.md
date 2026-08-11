# Mazha Mav Operations — Operational UI Audit

Audit date: 12 August 2026  
Scope: every route in `backend/app/api/routes/`, plus the complete V1 owner/manager/staff browser workflow.

## Outcome

All normal human V1 operations are available in the web application. Authentication/session checks, the deployment readiness probe, and direct QR-image delivery remain internal or browser-consumed endpoints by design. No sales, ledger movements, payment receipts, or request history can be edited or deleted from the UI.

## Endpoint-to-UI coverage matrix

| API capability | Method | Role | Business purpose | UI surface | Status |
|---|---:|---|---|---|---|
| `/auth/login` | POST | Public | Start a secure session | `/login` | Covered by UI |
| `/auth/logout` | POST | Authenticated | End the session | App header/mobile menu | Covered by UI |
| `/auth/me` | GET | Authenticated | Session and route guard | All protected layouts/pages | Internal-only: consumed by route protection |
| `/admin/users` | GET | Owner | Legacy account directory | `/admin/staff` | Covered by richer staff UI |
| `/admin/users` | POST | Owner | Add staff or manager | `/admin/staff` | Covered by UI |
| `/admin/users/{id}` | PATCH | Owner | Edit/enable/disable account | `/admin/staff`, `/admin/staff/{id}` | Covered by UI |
| `/admin/users/{id}/password` | POST | Owner | Reset password | `/admin/staff/{id}` | Covered by UI |
| `/admin/staff` | GET | Owner | Search/filter staff with live measures | `/admin/staff` | Covered by UI |
| `/admin/staff/{id}` | GET | Owner | Profile, performance, stock, sales, retailers, requests | `/admin/staff/{id}` | Covered by UI |
| `/admin/products` | GET | Owner | Product/SKU directory | `/admin/products` | Covered by UI |
| `/admin/products` | POST | Owner | Add product/SKU | `/admin/products` | Covered by UI |
| `/admin/products/{id}` | PATCH | Owner | Edit/activate/deactivate product | `/admin/products` | Covered by UI |
| `/dashboard/owner` | GET | Owner | Live KPI and dashboard aggregates | `/admin` | Covered by UI |
| `/reports/{report}.csv` | GET | Owner | Authenticated CSV exports | `/admin/reports` and dashboard | Covered by UI |
| `/inventory/options` | GET | Owner/Manager | Staff/product selectors | Inventory, issue and sales screens | Internal-only: UI option feed |
| `/inventory/issues` | POST | Owner/Manager | Issue warehouse stock to staff | `/admin/inventory/issue` | Covered by UI |
| `/inventory/returns` | POST | Owner/Manager | Record physical staff return | `/admin/inventory` | Covered by UI |
| `/inventory/warehouse-in` | POST | Owner/Manager | Receive warehouse stock | `/admin/inventory` | Covered by UI |
| `/inventory/adjustments` | POST | Owner/Manager | Audited correction | `/admin/inventory` | Covered by UI |
| `/inventory/staff-overview` | GET | Owner/Manager | Ledger-derived staff balances | `/admin/inventory` and issue flow | Covered by UI |
| `/inventory/warehouse` | GET | Owner/Manager | Ledger-derived warehouse balances | `/admin/inventory`, issue/request flows | Covered by UI |
| `/inventory/my-stock` | GET | Staff | Personal SKU-level stock | `/staff/my-stock` | Covered by UI |
| `/inventory/movements` | GET | Owner/Manager | Filtered immutable ledger history | `/admin/inventory` | Covered by UI |
| `/retailers` | GET | Authenticated (staff receives active operational data) | Search/filter retailer directory | `/admin/retailers`, record-sale selector | Covered by UI |
| `/retailers` | POST | Authenticated subject to staff setting | Add retailer | `/admin/retailers`, record-sale flow | Covered by UI |
| `/retailers/{id}` | GET | Owner/Manager | Retailer profile and purchase history | `/admin/retailers/{id}` | Covered by UI |
| `/retailers/{id}` | PATCH | Owner/Manager | Edit/reactivate retailer | `/admin/retailers` | Covered by UI |
| `/retailers/{id}` | DELETE | Owner/Manager | Soft-deactivate retailer | `/admin/retailers` | Covered by UI; historical data preserved |
| `/sales/options` | GET | Staff | Authoritative products/prices/stock and retailer options | `/staff/record-sale` | Internal-only: UI option feed |
| `/sales` | POST | Staff | Transactional multi-item sale | `/staff/record-sale` | Covered by UI |
| `/sales` | GET | Authenticated, staff scoped to self | Filtered sales register/history | `/admin/sales`, `/staff/history` | Covered by UI |
| `/sales/staff-home` | GET | Staff | Daily staff KPIs/recent sales | `/staff` | Covered by UI |
| `/sales/{id}` | GET | Authenticated, staff scoped to self | Sale line-item/audit detail | `/admin/sales/{id}`, `/staff/history/{id}` | Covered by UI |
| `/stock-requests` | POST | Staff | Request exact SKU replenishment | `/staff/request-stock` | Covered by UI |
| `/stock-requests/mine` | GET | Staff | Request history/open requests | `/staff`, `/staff/request-stock` | Covered by UI |
| `/stock-requests` | GET | Owner/Manager | Search/filter operational queue | `/admin/stock-requests` | Covered by UI |
| `/stock-requests/{id}/approve` | POST | Owner/Manager | Accept request without issuing stock | `/admin/stock-requests` | Covered by UI |
| `/stock-requests/{id}/reject` | POST | Owner/Manager | Reject with reason | `/admin/stock-requests` | Covered by UI |
| `/stock-requests/{id}/fulfil` | POST | Owner/Manager | Transactionally issue and fulfil | `/admin/stock-requests` | Covered by UI |
| `/payments/settings` | GET | Owner | Read central payment configuration | `/admin/settings/payments` | Covered by UI; missing config has an empty state |
| `/payments/settings` | POST | Owner | Save business/UPI/bank/QR settings | `/admin/settings/payments` | Covered by UI |
| `/payments/qr-context` | GET | Authenticated | Safe staff QR/sale display context | `/staff/payment-qr` | Internal-only: UI data feed |
| `/payments/qr-image` | GET | Authenticated | Secure QR media response | `/staff/payment-qr`, payment settings preview | Internal-only: image resource |
| `/payments/sales/{id}/received` | POST | Authorized staff assigned to sale | Manually record payment receipt | Sale-aware `/staff/payment-qr` | Covered by UI; QR display alone never marks paid |
| `/operations/status` | GET | Deployment platform | Liveness/readiness and migration status | Render health check | Intentionally API-only: technical operations endpoint |

## Navigation and role behavior

- Owner navigation: Dashboard, Staff, Products, Inventory, Sales, Retailers, Stock Requests, Reports, Payment Settings, Settings.
- Manager navigation: Inventory, Sales, Retailers, Stock Requests (API authorization remains authoritative; owner-only pages are not shown).
- Staff navigation: Home, Record Sale, My Stock, Request Stock, Payment QR, History.
- Desktop navigation collapses to a mobile menu below the large-screen breakpoint.
- Direct navigation remains protected server-side. Staff cannot access owner-only endpoints; managers cannot manage accounts/products/payment settings.

## Operational acceptance coverage

The browser workflow supports: product creation/edit/deactivation; warehouse receipt; staff/manager account management; issue/return/adjustment ledger posting; retailer create/edit/deactivate/reactivate/profile; transactional multi-product sales with server prices; pending/paid workflows and QR display; replenishment request approval/rejection/fulfilment; staff performance and stock profiles; dashboards; and authenticated CSV export.

All stock quantities displayed as authoritative balances originate from the ledger APIs. Historical sales retain `unit_price_snapshot`; historical ledger entries are immutable. Important posting/status actions use confirmation and duplicate-submit controls.

## Responsive and failure-state audit

Browser checks were performed at 375, 430, 768, 1024 and 1440 CSS pixels across the principal admin surfaces. Mobile overflow found in dashboard/inventory table grids was corrected with constrained grid children and local horizontal table scrolling. The shared client converts JSON and non-JSON failures into business-facing messages, with explicit session-expired and permission-denied messages. Empty tables/cards contain actionable or informative states.

## Verification

Final automated result: 56 backend tests passed; 6 frontend tests passed; ESLint passed; TypeScript/production Next.js build passed; and `npm audit --omit=dev` reported 0 vulnerabilities. Browser acceptance covered ten primary owner routes at 375, 430, 768, 1024 and 1440 CSS pixels with no document overflow, server error screen, or browser console error. This pass adds backend regression coverage for product lifecycle/authorization, retailer profile/reactivation/history preservation, filtered actor-attributed movement history, and sale detail/search/scope. It also adds frontend regression coverage for non-JSON API failures and expired-session messaging.

## Deliberate V1 boundaries

No GPS, attendance, payroll, commissions, forecasts, sales targets, surveillance, distributor hierarchy, WhatsApp automation, automatic bank verification, reconciliation, or other V2 features were added.
