# Logistics Intelligence Platform

Milestone 4A turns the canonical logistics graph into deterministic, auditable management analytics while preserving spreadsheet, invoice, and Bill of Lading ingestion.

The implemented workflow is:

`Excel / CSV → mapping → validation → row review → canonical shipments`

`Invoice PDF → text extraction → classification → field candidates → validation → document review → approval → canonical invoice`

`Bill of Lading PDF → classification → repeating container candidates → matching/validation → review → approval → connected canonical logistics graph`

`Canonical records → governed metric engine → comparisons/baselines → structured insights → drill-down/provenance`

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
- PDF upload validation, checksum-backed local source retention, safe retrieval, and explicit failure states
- embedded-text extraction with page/block evidence plus an OCR provider boundary for scanned documents
- deterministic `INVOICE`/`UNKNOWN` classification with confidence and supporting signals
- invoice candidate extraction for identity, parties, dates, amounts, VAT, and operational/payment references
- European date/amount normalization using `Decimal` semantics and country prefixes retained on VAT identifiers
- conservative party/reference matching, duplicate detection, and tolerance-aware arithmetic validation
- split PDF/evidence review with corrections, revalidation, approval, idempotent commit, and source lineage
- paginated Documents and canonical Invoices modules plus document-health metrics in Data Quality
- deterministic Bill of Lading classification and extraction for parties, transport, ports, cargo, and one or many containers
- reusable candidate groups that retain per-container confidence, evidence, page, corrections, and matches
- ISO 6346 check-digit validation, logistics normalization, weight consistency, and TEU derivation
- conservative port, vessel, voyage, party, and shipment matching with fail-closed canonical conflict detection
- transactional, idempotent B/L commitment linking or creating Shipment, Container, Vessel, Voyage, and Port records
- canonical Bills of Lading and connected Shipment detail views with source-document provenance
- a central registry for financial, profitability, volume, utilization, invoice, payment, and concentration metrics
- backend-authoritative time series, dimensional breakdowns, period comparisons, coverage reporting, and pagination
- strict selected-currency calculations with explicit mixed-currency exclusions and no implicit FX conversion
- deterministic management insights for margin, cost, revenue, volume, concentration, payment, receivable, and anomaly signals
- Overview KPI cards and trends plus an Analytics workspace with date, currency, metric, grain, and canonical dimension filters
- record-level drill-down from KPIs, insights, and breakdowns to shipment/import or document provenance
- a seeded 12-month `Baltic Freight Demo SIA` dataset with known management stories and controlled data-quality gaps

## Repository layout

```text
backend/
  alembic/                 Database migrations
  app/
    api/                   Thin FastAPI routes and identity dependency
    input_engine/          Tabular parsing, mapping, normalization, validation
    document_engine/       PDF parsing, OCR boundary, classification, extraction, validation
    models/                Canonical and audit SQLAlchemy entities
    repositories/          Tenant-scoped persistence queries
    schemas/               Pydantic API contracts
    services/              Import, review, and shipment orchestration
    analytics/             Metric registry, query facts, calculations, comparisons, insights
  tests/                   Focused unit/integration tests
frontend/
  app/                     Next.js routes and global styling
  components/              Operational workflows plus Overview and Analytics workspaces
  lib/                     Typed API client and shared contracts
demo-data/                 Synthetic spreadsheet, invoice, and Bill of Lading PDF fixtures
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

Regenerate the synthetic invoice PDFs:

```bash
.venv/bin/python scripts/generate_demo_invoices.py
```

Regenerate the synthetic Bill of Lading PDFs:

```bash
.venv/bin/python scripts/generate_demo_bills_of_lading.py
```

Reset and generate the deterministic 12-month analytics company:

```bash
.venv/bin/python scripts/generate_demo_company.py --reset
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

### Invoice PDF demo

1. Open **Data** and upload `demo-data/invoices/invoice-a-clean.pdf`.
2. Follow **Review document** to compare the retained PDF with extracted/system values, confidence, page evidence, matches, and issues.
3. Correct any field if needed, then revalidate. Corrections preserve the system-extracted baseline.
4. Warnings require explicit human approval; errors block approval and commit.
5. Approve and commit, then open **Invoices** to see the canonical record and its source-document link.
6. Upload `invoice-d-arithmetic-mismatch.pdf` to see totals fail closed, or `invoice-e-duplicate.pdf` after invoice A to see duplicate prevention.

Scanned/image-only PDFs currently return the structured `OCR_REQUIRED` failure because no local OCR adapter is configured. No document or extracted text is sent to a third party.

### Bill of Lading PDF demo

1. Open **Data** and upload `demo-data/bills-of-lading/bill-of-lading-b-multiple-containers.pdf`.
2. Confirm the `BILL_OF_LADING` classification, transport/party fields, and three separate container groups.
3. Select a container to inspect its source value, normalized value, page evidence, confidence, and canonical match.
4. Correct any candidate if needed and revalidate. Errors block approval; warnings require explicit approval.
5. Approve and commit. The transaction creates or links the B/L, shipment, containers, vessel, voyage, and ports together.
6. Open **Bills of Lading**, then follow the shipment link to see documents, containers, and financial records on one operational record.
7. Try the invalid-check-digit, weight-mismatch, partial, and duplicate fixtures to see fail-closed review behavior.

### Management analytics demo

1. Run `.venv/bin/python scripts/generate_demo_company.py --reset`, then open **Overview**.
2. Inspect the eight KPI cards, previous-period comparisons, coverage indicators, financial/volume trends, and ranked deterministic insights.
3. Open the Riga → Rotterdam margin signal to see rising cost/TEU, near-flat revenue/TEU, and its canonical shipment contributors.
4. Follow a KPI or insight drill-down to a shipment, source document, or synthetic import row.
5. Open **Analytics** and change the period, currency, metric, grain, dimension, or operational filters.
6. Sort a server-calculated breakdown and open a row to reconcile it to the contributing canonical records.

The generated company intentionally includes mixed USD records, incomplete finance coverage, missing TEU/weight, partial/unpaid invoices, seasonal volume, concentration, late payment, and expensive-shipment cases. Coverage and exclusions are therefore part of the demo rather than hidden noise.

## Development identity shortcut

Demo mode binds every request to the single company configured by `DEMO_COMPANY_SLUG`. An optional `X-Company-ID` header is only accepted when it matches that demo company; it cannot select another tenant. This is deliberately not production authentication. With demo mode disabled, protected endpoints fail closed until a real authentication and company-membership provider is configured.

See [Analytics semantics](docs/ANALYTICS.md), [Architecture](docs/ARCHITECTURE.md), [Data model](docs/DATA_MODEL.md), [Import review](docs/IMPORT_REVIEW.md), [Document engine](docs/DOCUMENT_ENGINE.md), and [Bill of Lading intelligence](docs/BILL_OF_LADING.md) for definitions, decisions, state transitions, correction semantics, API behavior, and current limitations.
