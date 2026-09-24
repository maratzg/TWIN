# Logistics Intelligence Platform

Milestone 2 turns the import foundation into an exception-focused review workbench for converting inconsistent logistics spreadsheets into trusted, tenant-scoped canonical records.

The implemented workflow is:

`Excel / CSV → automatic mapping → validation → exception review → correction → revalidation → selective commit → canonical persistence`

The product is a modular monolith: FastAPI and SQLAlchemy provide the backend, PostgreSQL is the target database, and Next.js provides the browser application. It has no cloud-provider dependency and can run on a laptop, private server, or cloud infrastructure.

## What works

- CSV and XLSX upload with a 20 MB limit
- worksheet discovery and best-sheet selection for workbooks
- header-row detection, including title rows above a table
- data-driven known aliases, cautious fuzzy fallback, and unresolved ambiguous headers
- persisted, company-specific confirmed mappings with highest future priority
- source samples, confidence, and mapping method in the review UI
- structured row validation with `INFO`, `WARNING`, and `ERROR` support
- numeric, date, currency, non-negative value, container-shape, chronology, and duplicate checks
- paginated import history, filename/status filtering, import detail, and row-state filters
- data-quality counts for ready, review, invalid, completed, failed, and attention-required imports
- cell-level review showing source header, immutable raw value, system interpretation, effective value, and issues
- value corrections that overlay normalized values without overwriting raw input
- mapping corrections that safely reprocess uncommitted rows and persist company-specific learning
- row/import revalidation, issue navigation, approval, and safe bulk actions
- selective or all-ready commit with per-row skip reasons and repeat-safe behavior
- auditable import jobs retaining raw values, system/effective normalized values, corrections, issues, approval, and canonical lineage
- canonical shipments, customers, containers, bills of lading, ports, vessels, and voyages
- shipment search and pagination
- tenant-scoped imports, rows, issues, mappings, corrections, commits, and shipment repositories

## Repository layout

```text
backend/
  alembic/                 Database migrations
  app/
    api/                   Thin FastAPI routes and identity dependency
    input_engine/          Parsing, mapping, normalization, validation
    models/                Canonical SQLAlchemy entities
    repositories/          Tenant-scoped persistence queries
    schemas/               Pydantic API contracts
    services/              Import, review, and shipment orchestration
  tests/                   Focused unit/integration tests
frontend/
  app/                     Next.js routes and global styling
  components/              Import wizard, quality dashboard, review workbench, shipments
  lib/                     Typed API client and shared contracts
demo-data/                 Synthetic, deliberately messy input files
docs/                      Architecture, data-model, and review-workflow decisions
```

## Local setup

Requirements: Python 3.11+, Node.js 20.9+, npm, and Docker for PostgreSQL.

1. Create local configuration and start PostgreSQL:

   ```bash
   cp .env.example .env
   docker compose up -d db
   ```

2. Install the backend and run the migration:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -e '.[dev]'
   .venv/bin/alembic upgrade head
   ```

3. Start the API from the repository root:

   ```bash
   .venv/bin/uvicorn app.main:app --app-dir backend --reload
   ```

   OpenAPI is at [http://localhost:8000/docs](http://localhost:8000/docs).

4. In a second terminal, start the frontend:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   Open [http://localhost:3000](http://localhost:3000).

For a no-Docker smoke run, omit `.env`; the backend defaults to `sqlite:///./logistics.db`. PostgreSQL remains the intended deployed database.

## Database migrations

Apply migrations:

```bash
.venv/bin/alembic upgrade head
```

Create a migration after changing models:

```bash
.venv/bin/alembic revision --autogenerate -m "describe change"
```

Demo mode creates missing tables for first-run convenience and seeds one configured demo company. Deployed environments should set `DEMO_MODE=false`, run migrations explicitly, and provide a real authentication/company-membership adapter.

## Tests and verification

Backend:

```bash
.venv/bin/pytest
```

Frontend production build:

```bash
cd frontend
npm run build
```

Regenerate the synthetic XLSX fixture if needed:

```bash
.venv/bin/python scripts/generate_demo_data.py
```

## Demo workflow

1. Open **Data**.
2. Upload `demo-data/company_a_shipments.xlsx`.
3. Observe the selected sheet, detected header row, 15 columns, source samples, proposed mappings, confidence, and methods.
4. Review the mappings and choose **Save mapping & validate**. `REF` is deliberately unresolved.
5. Open **Review exceptions**. Filter rows by ready, review, invalid, or committed state.
6. Open the row containing `GWT = 18,4t`. Its raw value remains visible; correct its interpreted gross weight to `18400` with unit `kg`, then revalidate.
7. In **Column mapping**, change `REF` to `booking_reference` and apply it to all uncommitted rows. The rows are reprocessed and this mapping is learned for the company.
8. Select ready rows and commit them. Invalid and duplicate rows are skipped and remain reviewable; repeat commit does not duplicate shipments.
9. Open **Shipments** to inspect the committed canonical records, then return to **Data** to inspect history and data-quality counts.
10. Upload `demo-data/company_b_shipments.csv`, or another file containing `REF`. The company-confirmed mapping is proposed at 100% confidence.

All demo records are synthetic.

## Development identity shortcut

Demo mode binds every request to the single company configured by `DEMO_COMPANY_SLUG`. An optional `X-Company-ID` header is only accepted when it matches that demo company; it cannot select another tenant. This is deliberately not production authentication. With demo mode disabled, protected endpoints fail closed until a real authentication and company-membership provider is configured.

See [Architecture](docs/ARCHITECTURE.md), [Data model](docs/DATA_MODEL.md), and [Import review](docs/IMPORT_REVIEW.md) for decisions, state transitions, correction semantics, API behavior, and current limitations.
