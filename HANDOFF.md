# Riwayat Oils and Fats ERP — handoff for a new chat

Paste this whole file at the start of a new chat (or keep it in the Claude Project "TEHZEEB ERP"). It is the single source of truth for where the project stands.

## Who and what
- Owner: Usman Khalid. Oil mill in Bahawalpur, Pakistan; company name **Riwayat Oils and Fats** (formerly "Tehzeeb" — the internal repo, services and some filenames still say tehzeeb).
- Plants: cooking-oil refining, hydrogenation (ghee), detergent soap, packaging. Business lines: own-brand oil, ghee, soap, and toll/job-work refining on commission.
- ERP scope: procurement, inventory, production, toll processing, sales & distribution, finance, HR & payroll, BI dashboards.
- Usman has been working from a phone; he is moving to a MacBook (new to macOS). Explain terminal steps simply.

## Stack
- Backend: Python 3.11, FastAPI 0.115, SQLAlchemy 2.0, Pydantic 2, uvicorn, openpyxl (Excel exports), psycopg2-binary. SQLite locally (`tehzeeb_erp.db`), PostgreSQL on Railway.
- Frontend: React 19 + Vite 8 + Tailwind v4 + Recharts. No router library/TypeScript.
- Hosting: Railway project "tehzeeb-erp" (id 6eced06a-36b3-44db-9296-a7a8b8b10c44), production environment b946a3bd-b6fe-4c86-8ad4-23d7e5b98de3. Services: tehzeeb-erp-api (eee329d9-d9be-4fd5-85fa-57070ea9a7c6), tehzeeb-erp-frontend (eb45020b-7b6a-44b2-b1dd-efd1019ac3ca), Postgres (06f604fc-2239-4873-9c07-4694b9c20d73). The API has a persistent volume for bill photos (`UPLOADS_DIR`, /data/uploads). A separate project "chuckys-erp" exists — never touch it from this project.
- Repo: github.com/iusmaann-cell/tehzeeb-erp, branch `master`. Railway auto-deploys on push.
- API env vars (names): DATABASE_URL, ADMIN_USERNAME, ADMIN_PASSWORD, UPLOADS_DIR, Google Drive/OAuth vars (legacy, unused since bill photos moved to the volume), optional SECRET_KEY, ENABLE_DOCS, ADMIN_FORCE_RESET. Frontend: VITE_API_URL.

## Repository layout
- `backend/app/`: `main.py`, `models.py`, `schemas.py`, `database.py` (includes additive auto-migrations `run_lightweight_migrations()` — new columns are added on startup, no Alembic), `security.py` (roles/permissions, `require_action`), `reporting.py`, `file_storage.py`, `one_time_cleanup.py` (temporary), `routers/*` (accounts, auth, vendors, items, warehouses, purchase_orders, grn, stock, stock_transfers, stock_adjustments, production, toll, sales, distributors, customers, finance, expenses, employees, attendance, payroll, salary_advances, bi, settings, admin).
- `frontend/src/`: `App.jsx`, `nav.jsx`, `api.js`, `auth.jsx`, `permissions.js`, `printInvoice.js`, `printReport.js`, `docNumbers.js`, `components/` (ui.jsx has SearchSelect, DetailRow, Table…), `pages/*`.
- `README.md` documents every phase; `render.yaml` is a leftover from the old Render host.

## Locked decisions (don't revisit without being told to)
FIFO automatic batch consumption; toll stock segregated per customer (never cross-consumed); byproduct-first costing; no mixed-SKU primary outputs in one production order; additive startup migrations only; bill photos on the Railway volume; document numbers `PREFIX-YYMMDD-HHMMSS`; customers `CUST-NNNN`, distributors `DIST-NNNN`; payments tracked as cash / cheque / online; custom roles with per-module none/view/edit permissions; first admin created from ADMIN_USERNAME/ADMIN_PASSWORD env vars; user accounts separate from HR employees; back-dated expenses admin-only; stock ledger is append-only (transfers/adjustments aren't edited, they're reversed).

## What exists (latest = Phase 23)
Phases 1–8 core modules; improvement phases 1–17 (nav/search, numbering, payment tracking and printable invoices, dashboard filters, recipe-driven production, stock adjustments with approval, mobile UI, expenses, units CRUD, Railway storage, vendor items & bank accounts, accounts & roles, stock transfers, back-dated expenses and Excel reports, Riwayat UI redesign, receiving/batches/freight/advances, payroll edit/delete).
- Phase 18: PO / GRN / vendor detail panels; PO editing admin-only (`edit_purchase_orders`); cancel blocked for completed/paid POs; searchable item/vendor dropdowns.
- Phase 19: partial payments on POs (several payments, ledger-linked).
- Phase 20: GST on POs/SOs; Expense Report (expenses + PO payments by day, freight lines, Excel); Advance Salary module; payroll advance recovery, auto absence deduction (4 free days, then salary/30), payment method per payslip.
- Phase 21: Items list print/Excel; full stock report print/Excel across all warehouses/tanks.
- Phase 22: PO-261003-190121 was purged from production (backup on volume `purge_backups/`). POs with received goods can't be deleted (server refuses, UI hides Delete).
- Phase 23: orphan-payment cleanup code + "PO #N (deleted)" label in the expense report.

## OPEN ITEMS — pick up here
1. **Orphan payment**: the Expense Report showed "PO #2", amount Rs. 14,346,000 — a PO_PAYMENT/PO_ADVANCE vendor-ledger entry whose PO (id 2) was deleted by an older version. Usman said "delete the entry". Plan: make sure Phase 23 is on GitHub/Railway → set `PURGE_ORPHAN_PO_ID=2` (dry run is default) on tehzeeb-erp-api → read `[purge]` lines in deploy logs (vendor, date, amount) → confirm with Usman → set `PURGE_PO_DRY_RUN=0` → verify "DONE" → blank/remove `PURGE_ORPHAN_PO_ID`, `PURGE_PO_NUMBER`, `PURGE_PO_DRY_RUN`. Check afterward for other orphans (the report now flags them). Whether the Phase 23 zip was pushed was not yet confirmed.
2. The purge variables on Railway are currently blank/`PURGE_PO_DRY_RUN=1` (the Railway MCP can set but not delete variables; delete them in the Railway dashboard when convenient). `one_time_cleanup.py` and its two lines in `main.py` can be removed in a later release.
3. The user's new PO to replace the purged one is his to create.
4. Tighten CORS (`allow_origins=["*"]`) to the frontend domain at some point.

## Working notes for the assistant
- Railway DB values are not readable through the MCP (credentials redacted, no TCP proxy), so data fixes go through env-var-driven, dry-run-first code in the deployed app, with a JSON backup written first.
- Always show a dry-run report and get Usman's confirmation before any destructive production change.
- Test pattern: uvicorn with `DATABASE_URL=sqlite:////tmp/x.db UPLOADS_DIR=/tmp/up ADMIN_USERNAME=admin ADMIN_PASSWORD=Admin12345`, build frontend, Playwright for UI checks. Use `fuser -k <port>/tcp` rather than `pkill -f`.
- Push: with a connected repo push directly; otherwise give `git init` / `git remote add` / `git fetch` / `git reset --soft origin/master` / commit / push commands (see MAC_SETUP.md).
- Money fields are PKR (Rs.), dates are Pakistan time for reporting.
