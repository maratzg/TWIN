# Canonical Data Model v0.4.0

## Identity conventions

- Internal primary keys are UUIDs and are never confused with business references.
- `external_reference` stores identifiers meaningful to a source/business process.
- `source_system_reference` is reserved for the originating system’s identity when it differs.
- Tenant-owned records carry `company_id` and are queried through a company-scoped repository.
- Monetary values use `NUMERIC`/`Decimal`, never binary floating point.
- Business entities carry creation and update timestamps. Immutable import children use their parent job timestamp and source row identity.

## Entities and relationships

### Company

Tenant boundary with a stable slug, display name, default currency, and optional legal registration/VAT identity. Invoice direction is derived only when an extracted supplier/customer matches this configured identity.

### Customer and Supplier

Separate counterparty roles with tenant-relative external references, legal/tax identifiers, country, and currency. They remain separate because operational customer behavior and accounts-payable supplier behavior evolve differently.

### Shipment

The operational aggregate root. It belongs to a company and can reference a customer, voyage, origin/destination ports, and the import job/source row that created it. It stores shipment and booking references, dates, status, gross weight, revenue, and currency. Shipment and booking references are unique within a company when present.

Shipment does not absorb container, bill of lading, vessel, voyage, or port attributes. This avoids conflating distinct reusable or one-to-many concepts.

### Container

Belongs to a shipment and company. Stores container number, size/type, seal, packages, TEU, weight, and status. The row represents a shipment-scoped occurrence, not an eternal physical-container master. The same number can therefore appear on later shipments; uniqueness includes shipment. Document-created occurrences retain source document and candidate-group provenance.

### BillOfLading

Belongs to a shipment and company. Stores the B/L number, document/party attributes, cargo totals, and optional canonical party matches. The number is unique within a company. `source_document_id` is unique, providing provenance and repeated-commit idempotency.

### Vessel and Voyage

A vessel represents the physical ship; a voyage represents a numbered movement by a vessel. This permits a vessel to appear on many voyages and shipments to share one voyage.

### Port

Reusable tenant-scoped location with an optional UN/LOCODE, name, and country. Tenant scoping permits private aliases now; a shared reference catalog can be added later without changing shipment relationships.

### Invoice, Payment, and Cost

The finance foundation is consumed by deterministic analytics and exposed through typed management views.

- Invoice supports `receivable` and `payable` direction, optional customer/supplier/shipment relationships, Decimal totals, dates, currency, and status. `source_document_id` uniquely links a document-created invoice to retained provenance and makes repeated document commit idempotent.
- Payment has an optional invoice relationship, allowing unmatched payments and multiple payments per invoice.
- Cost can be shipment-specific or general and may reference a supplier.

### ImportJob, ImportColumn, ImportRow, ImportIssue, and ImportCorrection

Together these form the audit model.

- `ImportJob` stores file/detection metadata, workflow status, ready/review/invalid/committed counts, and the mapping snapshot.
- `ImportColumn` stores source header, normalized form, samples, canonical proposal, confidence, method, and confirmation state.
- `ImportRow` preserves raw JSON, system-normalized JSON, effective normalized JSON, original row number, disposition, validation/approval/commit timestamps, reviewer reference, and canonical shipment link.
- `ImportIssue` stores row, field, severity, stable code, and human-readable message.
- `ImportCorrection` is an append-only audit record for either a row value or a column mapping change. It records tenant/import/row scope, source column, canonical field, previous and corrected values, unit, reason, reviewer reference, and timestamp.

`raw_data` is source history and is never edited. `system_normalized_data` is the deterministic engine result before a reviewer overlay. `normalized_data` is the effective candidate after applying the latest corrections and is the only candidate considered for commit.

### LearnedMapping

Unique by company and normalized header. It stores the latest confirmed canonical target, original source header, confirmation count, origin, and last import job. Because company mappings are checked first, repeat imports become more deterministic.

### SourceDocument, DocumentPage, DocumentFieldCandidate, DocumentIssue, and DocumentCorrection

These tables form the reusable document audit aggregate.

- `SourceDocument` stores tenant, safe original filename, content type, byte size, SHA-256, opaque storage key, workflow state, classification/extraction metadata, counts, and approval/commit timestamps.
- `DocumentPage` stores page-numbered text, positional text blocks, extraction method, and character count.
- `DocumentFieldCandidate` stores canonical field, reusable `group_type`/`group_index`, raw value, immutable system-normalized value, effective value, confidence/method, page/evidence/bounding box, review state, and an optional canonical entity match. Scalar fields use `document:0`; repeating B/L containers use `container:n`.
- `DocumentIssue` stores stable validation code, severity, field/candidate association, and message.
- `DocumentCorrection` is an append-only tenant-scoped record of previous/effective values, reason, reviewer reference, and time.

The database stores document metadata and evidence, not PDF bytes. `storage_key` is interpreted only by the configured storage adapter.

## Important constraints

- Tenant-relative shipment external references are unique.
- Tenant-relative booking references are unique.
- Tenant-relative B/L numbers are unique.
- Customers and suppliers may retain a tenant-relative external reference.
- A learned normalized header has one current target per company.
- One import row number and one import source column are unique inside a job.
- One candidate per document/group/index/canonical field and one page number per document are unique.
- A storage key is unique, and canonical invoices/Bills of Lading can each reference at most one source document.
- Finance amounts are stored with two decimal places; weights use three.

## Analytical access model

Milestone 4A does not add materialized KPI entities. Metrics are derived from canonical rows so one transactional fact remains the source of truth. Composite indexes were added for the bounded query paths used by period and dimension analysis:

- shipment company + ETD, customer, canonical route, and voyage;
- invoice company + direction/currency/date, customer, and due date;
- payment company + invoice/payment date;
- cost company + shipment/currency/cost date.

Route identity is the stable origin/destination port UUID pair, not a display string. Time-series flow metrics use shipment ETD or invoice date according to the metric registry; outstanding balances use an as-of period end. Provenance continues through the existing shipment import and source-document relationships rather than an analytics-specific copy.

## Assumptions

- Imported row-level revenue is shipment revenue, not an invoice.
- A source row without a shipment, B/L, or container identifier is invalid.
- When shipment reference is absent, commit derives a visible shipment reference from the B/L or container identifier while preserving those values in their own entities.
- `ready` means no warning or error. Any warning routes a row to review; any error makes it invalid.
- Document `needs_review` may contain warnings or errors. Warnings can be explicitly approved; errors cannot. Only an `approved` document can commit.

## Planned extensions

- user, company membership, role, and permission entities
- encrypted production object storage, retention, and malware scanning policy
- shared ISO port/currency catalogs and a physical-container master, if operational use later requires one
- multiple containers and B/Ls from one source row or related sheets
- authenticated user IDs and richer reviewer attribution (demo mode currently stores a reviewer reference)
- canonical supersession/reversal for correcting rows after commit
- accounting allocations for a payment spanning invoices
- exchange rates and explicit money/currency conversion policy
- import profiles keyed by source system/file family in addition to normalized headers
- soft-delete or supersession strategy for canonical corrections
